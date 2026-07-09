import os
import json
import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager
from config import load_env
load_env()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaConsumer

from api.websocket_manager import manager
from database.postgres import PostgresRepository
from database.mongo import MongoRepository
from llm.reporter import LLMReporter

logger = logging.getLogger('api')
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

postgres_repo = PostgresRepository()
mongo_repo = MongoRepository()
llm_reporter = LLMReporter()

_consumer_thread = None
_stop_event = threading.Event()
_main_loop = None


def _kafka_consumer_loop():
    bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
    topics = [
        os.getenv('KAFKA_VERIFIED_TOPIC', 'verified-anomalies'),
        os.getenv('KAFKA_ANOMALY_TOPIC', 'anomaly-events'),
    ]
    if int(os.getenv('SPARK_MIN_EVENTS', '1')) > 1:
        topics = [topics[0]]

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

            for msg in consumer:
                if _stop_event.is_set():
                    break
                _handle_verified_anomaly(msg.value)

            consumer.close()
        except Exception as e:
            logger.error(f"Kafka consumer hatasi: {e}")
            if not _stop_event.is_set():
                time.sleep(5)


def _handle_verified_anomaly(event: dict):
    report = llm_reporter.generate_report(event)
    event['ai_generated_report'] = report

    try:
        pg_id = postgres_repo.save_anomaly(event, report)
        mongo_repo.save_raw_metrics(event, pg_id)
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
        'report': report,
        'timestamp': event.get('timestamp')
    }

    global _main_loop
    if _main_loop and _main_loop.is_running():
        asyncio.run_coroutine_threadsafe(manager.broadcast(payload), _main_loop)
    else:
        logger.warning("WebSocket yayini icin event loop hazir degil")

    logger.info(f"Anomali islendi ve yayinlandi | {event['anomaly_type']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_thread, _main_loop
    _main_loop = asyncio.get_running_loop()
    _consumer_thread = threading.Thread(target=_kafka_consumer_loop, daemon=True)
    _consumer_thread.start()
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
    return {'status': 'ok'}


@app.get('/api/anomalies')
def list_anomalies(limit: int = 50):
    return {'items': postgres_repo.list_recent(limit)}


@app.get('/api/test-alert')
@app.post('/api/test-alert')
async def test_alert():
    """Dashboard baglantisini test etmek icin — tarayicidan acilabilir."""
    payload = {
        'type': 'anomaly_alert',
        'id': 0,
        'camera_id': 'cam_01',
        'track_id': 99,
        'anomaly_type': 'RUN',
        'confidence_score': 0.95,
        'report': 'Test bildirimi — sistem calisiyor.',
        'timestamp': time.time()
    }
    client_count = len(manager.active)
    await manager.broadcast(payload)
    return {
        'ok': True,
        'message': 'Test bildirimi gonderildi',
        'connected_clients': client_count
    }


@app.websocket('/ws/alerts')
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def main():
    import uvicorn
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', 8000))
    uvicorn.run('api.main:app', host=host, port=port, reload=False)


if __name__ == '__main__':
    main()
