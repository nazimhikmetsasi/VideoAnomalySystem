import os
import json
import logging
import httpx

logger = logging.getLogger('video_pipeline')

API_URL = os.getenv('API_NOTIFY_URL', 'http://127.0.0.1:8000/api/internal/alert')


def notify_api(anomaly: dict, landmarks: list | None = None):
    """Anomali bildirimini dogrudan API'ye gonderir (Kafka'ya bagli degil)."""
    payload = {**anomaly}
    if landmarks:
        payload['landmarks'] = landmarks
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.post(API_URL, json=payload)
            if resp.status_code == 200:
                logger.info(f"API bildirimi gonderildi | {anomaly['anomaly_type']}")
            else:
                logger.warning(f"API bildirimi basarisiz | status={resp.status_code}")
    except Exception as e:
        logger.warning(f"API'ye ulasilamadi (run_api.bat acik mi?): {e}")
