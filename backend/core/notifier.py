import os
import logging
import httpx

logger = logging.getLogger('video_pipeline')

API_URL = os.getenv('API_NOTIFY_URL', 'http://127.0.0.1:8000/api/internal/alert')
NOTIFY_RETRIES = int(os.getenv('API_NOTIFY_RETRIES', 2))


def notify_api(anomaly: dict, landmarks: list | None = None) -> bool:
    """Anomali bildirimini dogrudan API'ye gonderir."""
    payload = {**anomaly}
    if landmarks:
        payload['landmarks'] = landmarks

    for attempt in range(1, NOTIFY_RETRIES + 1):
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(API_URL, json=payload)
                if resp.status_code == 200:
                    logger.info(f"API bildirimi OK | {anomaly['anomaly_type']}")
                    return True
                logger.warning(f"API yanit hatasi | status={resp.status_code} | deneme={attempt}")
        except Exception as e:
            logger.warning(f"API ulasilamadi | deneme={attempt}/{NOTIFY_RETRIES} | {e}")
    return False
