import os
import json
import asyncio
import threading
import time
from contextlib import asynccontextmanager
from config import load_env
load_env()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaConsumer
from pydantic import BaseModel

from api.websocket_manager import manager
from api.auth import (
    authenticate_user, create_access_token, get_current_user, require_role, auth_enabled,
)
from api.training import get_training_status, start_training_async, latest_model_info
from database.postgres import PostgresRepository
from database.mongo import MongoRepository
from llm.reporter import LLMReporter
from core.logging_config import setup_logging
from core.push_notifier import send_push_alert, status as fcm_status, format_push_message
from core.camera_config import load_cameras_config

logger = setup_logging('api', 'api.log')

postgres_repo = PostgresRepository()
mongo_repo = MongoRepository()
llm_reporter = LLMReporter()


async def _push_alert(event: dict) -> dict:
    """DB kaydi + WebSocket yayini (LLM/FCM event loop'u bloklamasin)."""
    # Gemini senkron HTTP — thread'de calistir ki panel donmasin
    report = await asyncio.to_thread(llm_reporter.generate_report, event)
    event['ai_generated_report'] = report

    try:
        pg_id = await asyncio.to_thread(postgres_repo.save_anomaly, event, report)
        await asyncio.to_thread(mongo_repo.save_raw_metrics, event, pg_id)
    except Exception as e:
        logger.error(f"Veritabani kayit hatasi: {e}")
        pg_id = None

    payload = {
        'type': 'anomaly_alert',
        'id': pg_id,
        'camera_id': event['camera_id'],
        'track_id': event['track_id'],
        'anomaly_type': event['anomaly_type'],
        'confidence_score': event['confidence_score'],
        'motion': event.get('motion') or event.get('motion_confirmed'),
        'in_zone': event.get('in_zone'),
        'report': report,
        'timestamp': event.get('timestamp')
    }

    global _main_loop
    if _main_loop and _main_loop.is_running():
        await manager.broadcast(payload)
    else:
        logger.warning("WebSocket loop hazir degil")

    logger.info(f"Bildirim yayinlandi | {event['anomaly_type']} | track={event.get('track_id')}")
    fcm_result = await asyncio.to_thread(send_push_alert, payload)
    payload['fcm'] = fcm_result
    return payload


class LoginRequest(BaseModel):
    username: str
    password: str

_consumer_thread = None
_stop_event = threading.Event()
_main_loop = None


def _kafka_consumer_loop():
    bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
    topics = [
        os.getenv('KAFKA_VERIFIED_TOPIC', 'verified-anomalies'),
    ]
    # Ham anomaly-events sadece Spark dogrulama zinciri kullaniliyorsa dinlenir
    if os.getenv('ANOMALY_KAFKA_PUBLISH', 'false').lower() == 'true':
        topics.append(os.getenv('KAFKA_ANOMALY_TOPIC', 'anomaly-events'))
    if int(os.getenv('SPARK_MIN_EVENTS', '1')) > 1:
        topics = [os.getenv('KAFKA_VERIFIED_TOPIC', 'verified-anomalies')]

    while not _stop_event.is_set():
        try:
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=[bootstrap],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='anomaly-api-consumer-v2',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=1000
            )
            logger.info(f"Kafka consumer basladi | topics={topics}")

            # Idle timeout for dongusunu bitirmesin — poll ile bekle
            while not _stop_event.is_set():
                batch = consumer.poll(timeout_ms=1000)
                for _tp, messages in batch.items():
                    for msg in messages:
                        _handle_verified_anomaly(msg.value)

            consumer.close()
            break
        except Exception as e:
            logger.error(f"Kafka consumer hatasi: {e}")
            if not _stop_event.is_set():
                time.sleep(5)


def _handle_verified_anomaly(event: dict):
    global _main_loop
    if _main_loop and _main_loop.is_running():
        asyncio.run_coroutine_threadsafe(_push_alert(event), _main_loop)
    else:
        logger.warning("Event loop hazir degil — anomali atlandi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_thread, _main_loop
    _main_loop = asyncio.get_running_loop()
    kafka_enabled = os.getenv('KAFKA_ENABLED', 'true').lower() == 'true'
    if kafka_enabled:
        _consumer_thread = threading.Thread(target=_kafka_consumer_loop, daemon=True)
        _consumer_thread.start()
        logger.info("Kafka consumer thread baslatildi")
    else:
        logger.info("Kafka devre disi — sadece /api/internal/alert modu")
    yield
    _stop_event.set()


app = FastAPI(
    title='Video Anomaly Detection API',
    description='MCBU Guvenlik Gozetim Sistemi',
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/health')
def health():
    llm = llm_reporter.status()
    return {
        'status': 'ok',
        'llm': llm,
        'auth_enabled': auth_enabled(),
    }


@app.post('/api/auth/login')
def login(body: LoginRequest):
    user = authenticate_user(body.username, body.password)
    if not user:
        return {'ok': False, 'message': 'Kullanici adi veya sifre hatali'}
    token = create_access_token(user)
    return {'ok': True, 'token': token, 'username': user['username'], 'role': user['role']}


@app.get('/api/auth/me')
def auth_me(user: dict = Depends(get_current_user)):
    return {'username': user['username'], 'role': user['role']}


@app.get('/api/cameras')
def list_cameras(user: dict = Depends(get_current_user)):
    return {'cameras': load_cameras_config()}


@app.get('/api/training/status')
def training_status(user: dict = Depends(require_role('admin'))):
    return {**get_training_status(), **latest_model_info()}


@app.post('/api/training/start')
def training_start(user: dict = Depends(require_role('admin'))):
    return start_training_async()


@app.get('/api/llm/status')
def llm_status(user: dict = Depends(get_current_user)):
    return llm_reporter.status()


@app.get('/api/llm/test')
@app.post('/api/llm/test')
def llm_test(user: dict = Depends(require_role('admin'))):
    return llm_reporter.test_connection()


@app.get('/api/evaluation/latest')
def evaluation_latest(user: dict = Depends(get_current_user)):
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    latest = os.path.normpath(os.path.join(root, 'results', 'latest.json'))
    if not os.path.exists(latest):
        return {'available': False, 'message': 'Henuz pilot degerlendirme calistirilmadi. run_pilot_eval.bat kullanin.'}
    with open(latest, encoding='utf-8') as f:
        data = json.load(f)
    return {'available': True, 'results': data}


@app.get('/api/anomalies')
def list_anomalies(limit: int = 50, user: dict = Depends(get_current_user)):
    return {'items': postgres_repo.list_recent(limit)}


@app.post('/api/internal/alert')
async def internal_alert(event: dict):
    """Kamera pipeline'dan dogrudan bildirim alir."""
    try:
        payload = await _push_alert(event)
        return {'ok': True, 'alert': payload}
    except Exception as e:
        logger.error(f"internal/alert hatasi: {e}")
        # Panel yine de bir sey gorsun — minimal yayin
        fallback = {
            'type': 'anomaly_alert',
            'id': None,
            'camera_id': event.get('camera_id'),
            'track_id': event.get('track_id'),
            'anomaly_type': event.get('anomaly_type'),
            'confidence_score': event.get('confidence_score'),
            'report': f"Alarm: {event.get('anomaly_type')} (track {event.get('track_id')})",
            'timestamp': event.get('timestamp'),
        }
        try:
            await manager.broadcast(fallback)
        except Exception:
            pass
        return {'ok': True, 'alert': fallback, 'warning': str(e)}


@app.get('/api/push/status')
def push_status(user: dict = Depends(get_current_user)):
    """FCM hazir mi? Android olmadan da kontrol edilir."""
    st = fcm_status()
    sample = {
        'camera_id': 'cam_01',
        'track_id': 2,
        'anomaly_type': 'ZONE_VIOLATION',
        'confidence_score': 0.9,
        'motion': 'RUNNING',
    }
    title, body = format_push_message(sample)
    return {
        'fcm': st,
        'ornek_bildirim': {'title': title, 'body': body},
        'test_ipucu': (
            'Android yoksa: Chrome masaustu + FCM_KURULUM.txt '
            'veya panelden Test Bildirimi + /api/push/status ile metni dogrula.'
        ),
    }


@app.get('/api/test-alert')
@app.post('/api/test-alert')
async def test_alert(user: dict = Depends(require_role('admin'))):
    event = {
        'camera_id': 'cam_01',
        'track_id': 2,
        'anomaly_type': 'ZONE_VIOLATION',
        'confidence_score': 0.95,
        'motion': 'RUNNING',
        'metrics': {
            'horizontal_velocity': 102.5,
            'vertical_velocity': 8.0,
            'spine_angle': 15.0,
        },
        'timestamp': time.time()
    }
    payload = await _push_alert(event)
    return {
        'ok': True,
        'message': 'Test bildirimi gonderildi',
        'connected_clients': len(manager.active),
        'alert': payload,
        'fcm': payload.get('fcm'),
    }


@app.websocket('/ws/alerts')
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    await websocket.send_json({'type': 'connected', 'message': 'MCBU Anomali WS'})
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == 'ping':
                await websocket.send_json({'type': 'pong'})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def main():
    import uvicorn
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', 8000))
    uvicorn.run('api.main:app', host=host, port=port, reload=False)


if __name__ == '__main__':
    main()
