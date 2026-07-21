import os
import logging
import threading
import httpx

logger = logging.getLogger('video_pipeline')

API_URL = os.getenv('API_NOTIFY_URL', 'http://127.0.0.1:8000/api/internal/alert')
NOTIFY_RETRIES = int(os.getenv('API_NOTIFY_RETRIES', 2))
NOTIFY_TIMEOUT = float(os.getenv('API_NOTIFY_TIMEOUT_SEC', 8))


def _post_alert(anomaly: dict, landmarks: list | None = None) -> bool:
    payload = {**anomaly}
    if landmarks:
        payload['landmarks'] = landmarks

    # JSON uyumu: numpy/ozel tipleri basitlestir
    safe = {}
    for k, v in payload.items():
        if k == 'metrics' and isinstance(v, dict):
            safe[k] = {mk: (float(mv) if hasattr(mv, 'item') else mv) for mk, mv in v.items()}
        elif hasattr(v, 'item'):
            safe[k] = v.item()
        else:
            safe[k] = v

    for attempt in range(1, NOTIFY_RETRIES + 1):
        try:
            with httpx.Client(timeout=NOTIFY_TIMEOUT) as client:
                resp = client.post(API_URL, json=safe)
                if resp.status_code == 200:
                    logger.info(
                        f"API bildirimi OK | {anomaly.get('anomaly_type')} | "
                        f"track={anomaly.get('track_id')}"
                    )
                    return True
                logger.warning(
                    f"API yanit hatasi | status={resp.status_code} | "
                    f"deneme={attempt} | body={resp.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"API ulasilamadi | deneme={attempt}/{NOTIFY_RETRIES} | {e}")
    return False


def notify_api(anomaly: dict, landmarks: list | None = None) -> bool:
    """Anomali bildirimini API'ye gonderir (video thread'i bloklamaz)."""
    t = threading.Thread(
        target=_post_alert,
        args=(anomaly, landmarks),
        daemon=True,
        name='api-notify',
    )
    t.start()
    return True
