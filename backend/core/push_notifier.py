"""Firebase Cloud Messaging (FCM) mobil bildirim."""

from __future__ import annotations

import os
import logging
import httpx

logger = logging.getLogger('api')

FCM_URL = 'https://fcm.googleapis.com/fcm/send'


def push_enabled() -> bool:
    return (
        os.getenv('FCM_ENABLED', 'false').lower() == 'true'
        and bool(os.getenv('FCM_SERVER_KEY', '').strip())
    )


def send_push_alert(payload: dict) -> bool:
    """Anomali olayini FCM topic veya cihaz tokenlarina gonderir."""
    if not push_enabled():
        return False

    server_key = os.getenv('FCM_SERVER_KEY', '').strip()
    topic = os.getenv('FCM_TOPIC', 'anomalies')
    tokens_raw = os.getenv('FCM_DEVICE_TOKENS', '').strip()

    title = payload.get('anomaly_type', 'Anomali')
    body = payload.get('report') or f"Kamera {payload.get('camera_id')} — guven {payload.get('confidence_score')}"

    message: dict = {
        'notification': {'title': f'MCBU: {title}', 'body': body[:200]},
        'data': {
            'camera_id': str(payload.get('camera_id', '')),
            'anomaly_type': str(payload.get('anomaly_type', '')),
            'track_id': str(payload.get('track_id', '')),
        },
        'priority': 'high',
    }

    if tokens_raw:
        tokens = [t.strip() for t in tokens_raw.split(',') if t.strip()]
        message['registration_ids'] = tokens
    else:
        message['to'] = f'/topics/{topic}'

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                FCM_URL,
                headers={
                    'Authorization': f'key={server_key}',
                    'Content-Type': 'application/json',
                },
                json=message,
            )
            if resp.status_code == 200:
                logger.info(f"FCM bildirimi gonderildi | {title}")
                return True
            logger.warning(f"FCM hatasi | status={resp.status_code} | {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"FCM ulasilamadi: {e}")
    return False
