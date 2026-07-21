"""Firebase Cloud Messaging — HTTP v1 (servis hesabi) + Legacy yedek."""

from __future__ import annotations

import os
import logging
from pathlib import Path

import httpx

logger = logging.getLogger('api')

FCM_LEGACY_URL = 'https://fcm.googleapis.com/fcm/send'
FCM_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'

ANOMALY_TR = {
    'FALL': 'düşme',
    'RUN': 'koşma',
    'ZONE_VIOLATION': 'yasaklı alan ihlali',
    'RUN_ZONE': 'koşarak alan ihlali',
    'PERSON_ENTERED': 'alana giriş',
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _credentials_path() -> Path | None:
    raw = (os.getenv('FCM_CREDENTIALS_PATH') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS') or '').strip()
    if not raw:
        candidate = _project_root() / 'config' / 'firebase-service-account.json'
        return candidate if candidate.exists() else None
    path = Path(raw)
    if not path.is_abs():
        path = _project_root() / path
    return path if path.exists() else None


def format_push_message(payload: dict) -> tuple[str, str]:
    """Telefonda gorunecek Turkce baslik + govde."""
    atype = str(payload.get('anomaly_type', 'Anomali'))
    track_id = payload.get('track_id', '?')
    camera_id = payload.get('camera_id', 'cam')
    conf = payload.get('confidence_score', 0)
    label = ANOMALY_TR.get(atype, atype.lower())
    motion = payload.get('motion') or payload.get('motion_confirmed')

    title = f'MCBU Alarm: {label.upper()}'

    if atype == 'RUN_ZONE' or (atype == 'ZONE_VIOLATION' and motion in ('RUNNING', 'RUN')):
        body = f'Varlık ID:{track_id} koşarak yasaklı alana giriş yaptı ({camera_id}).'
    elif atype == 'ZONE_VIOLATION':
        body = f'Varlık ID:{track_id} yasaklı alana giriş yaptı ({camera_id}).'
    elif atype == 'RUN' and payload.get('in_zone'):
        body = f'Varlık ID:{track_id} koşarak yasaklı alana giriş yaptı ({camera_id}).'
    elif atype == 'RUN':
        body = f'Varlık ID:{track_id} koşma hareketi sergiledi ({camera_id}).'
    elif atype == 'FALL':
        body = f'Varlık ID:{track_id} düşme hareketi tespit edildi ({camera_id}).'
    elif atype == 'PERSON_ENTERED':
        body = f'Varlık ID:{track_id} kamera görüş alanına girdi ({camera_id}).'
    else:
        report = (payload.get('report') or payload.get('ai_generated_report') or '').strip()
        body = report[:180] if report else f'Varlık ID:{track_id} — {label} ({camera_id}).'

    try:
        body = f'{body} Güven: %{int(round(float(conf) * 100))}.'
    except (TypeError, ValueError):
        pass

    return title, body[:200]


def status() -> dict:
    enabled = os.getenv('FCM_ENABLED', 'false').lower() == 'true'
    creds = _credentials_path()
    has_legacy = bool(os.getenv('FCM_SERVER_KEY', '').strip())
    tokens = [t.strip() for t in os.getenv('FCM_DEVICE_TOKENS', '').split(',') if t.strip()]
    mode = 'http_v1' if creds else ('legacy' if has_legacy else 'none')
    return {
        'enabled_flag': enabled,
        'has_credentials_json': bool(creds),
        'credentials_path': str(creds) if creds else None,
        'has_server_key': has_legacy,
        'ready': enabled and (bool(creds) or has_legacy),
        'api_mode': mode,
        'topic': os.getenv('FCM_TOPIC', 'anomalies'),
        'device_token_count': len(tokens),
        'send_mode': 'device_tokens' if tokens else 'topic',
    }


def push_enabled() -> bool:
    st = status()
    return st['ready']


def _access_token_and_project(creds_path: Path) -> tuple[str, str]:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request

    credentials = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=[FCM_SCOPE]
    )
    credentials.refresh(Request())
    project_id = credentials.project_id or os.getenv('FCM_PROJECT_ID', '').strip()
    if not project_id:
        raise RuntimeError('Service account JSON icinde project_id yok')
    return credentials.token, project_id


def _send_http_v1(title: str, body: str, payload: dict) -> dict:
    creds_path = _credentials_path()
    if not creds_path:
        return {'sent': False, 'error': 'firebase-service-account.json bulunamadi'}

    token, project_id = _access_token_and_project(creds_path)
    topic = os.getenv('FCM_TOPIC', 'anomalies')
    tokens_raw = os.getenv('FCM_DEVICE_TOKENS', '').strip()

    data_fields = {
        'camera_id': str(payload.get('camera_id', '')),
        'anomaly_type': str(payload.get('anomaly_type', '')),
        'track_id': str(payload.get('track_id', '')),
        'title': title,
        'body': body,
    }

    message: dict = {
        'notification': {'title': title, 'body': body},
        'data': data_fields,
    }

    if tokens_raw:
        # Tek token gonder (ilk); coklu icin dongu
        tokens = [t.strip() for t in tokens_raw.split(',') if t.strip()]
        message['token'] = tokens[0]
        targets = tokens
    else:
        message['topic'] = topic
        targets = [f'topic:{topic}']

    url = f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    last_error = None
    sent_any = False
    if 'token' in message:
        for device_token in targets:
            msg = {
                'message': {
                    'token': device_token,
                    'notification': message['notification'],
                    'data': data_fields,
                }
            }
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, headers=headers, json=msg)
            if resp.status_code == 200:
                sent_any = True
            else:
                last_error = f'HTTP {resp.status_code}: {resp.text[:240]}'
    else:
        msg = {'message': message}
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, headers=headers, json=msg)
        if resp.status_code == 200:
            sent_any = True
        else:
            last_error = f'HTTP {resp.status_code}: {resp.text[:240]}'

    if sent_any:
        logger.info(f"FCM v1 gonderildi | {title} | {body}")
        return {'sent': True, 'api': 'http_v1', 'project_id': project_id}
    return {'sent': False, 'api': 'http_v1', 'error': last_error or 'gonderilemedi', 'project_id': project_id}


def _send_legacy(title: str, body: str, payload: dict) -> dict:
    server_key = os.getenv('FCM_SERVER_KEY', '').strip()
    if not server_key:
        return {'sent': False, 'error': 'FCM_SERVER_KEY yok'}

    topic = os.getenv('FCM_TOPIC', 'anomalies')
    tokens_raw = os.getenv('FCM_DEVICE_TOKENS', '').strip()
    message: dict = {
        'notification': {'title': title, 'body': body},
        'data': {
            'camera_id': str(payload.get('camera_id', '')),
            'anomaly_type': str(payload.get('anomaly_type', '')),
            'track_id': str(payload.get('track_id', '')),
        },
        'priority': 'high',
    }
    if tokens_raw:
        message['registration_ids'] = [t.strip() for t in tokens_raw.split(',') if t.strip()]
    else:
        message['to'] = f'/topics/{topic}'

    with httpx.Client(timeout=5.0) as client:
        resp = client.post(
            FCM_LEGACY_URL,
            headers={'Authorization': f'key={server_key}', 'Content-Type': 'application/json'},
            json=message,
        )
    if resp.status_code == 200:
        logger.info(f"FCM legacy gonderildi | {title}")
        return {'sent': True, 'api': 'legacy'}
    return {'sent': False, 'api': 'legacy', 'error': f'HTTP {resp.status_code}: {resp.text[:200]}'}


def send_push_alert(payload: dict) -> dict:
    title, body = format_push_message(payload)
    result = {
        'attempted': False,
        'sent': False,
        'title': title,
        'body': body,
        'error': None,
        'status': status(),
    }

    if not push_enabled():
        result['error'] = (
            'FCM kapali veya kimlik yok. '
            'config/firebase-service-account.json koy + FCM_ENABLED=true'
        )
        return result

    result['attempted'] = True
    try:
        if _credentials_path():
            out = _send_http_v1(title, body, payload)
        else:
            out = _send_legacy(title, body, payload)
        result.update(out)
        if not out.get('sent'):
            result['error'] = out.get('error')
    except Exception as e:
        result['error'] = str(e)
        logger.warning(f"FCM ulasilamadi: {e}")
    return result
