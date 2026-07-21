"""Telefona bildirim — uygulama gerektirmez.

Kanallar:
  1) Telegram bot (onerilen, ucretsiz)
  2) SMS — Netgsm (Turkiye) veya Twilio
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

from core.push_notifier import format_push_message

logger = logging.getLogger('api')


def phone_status() -> dict:
    tg_token = (os.getenv('TELEGRAM_BOT_TOKEN') or '').strip()
    tg_chat = (os.getenv('TELEGRAM_CHAT_ID') or '').strip()
    sms_provider = (os.getenv('SMS_PROVIDER') or '').strip().lower()
    netgsm_ok = all([
        os.getenv('NETGSM_USER', '').strip(),
        os.getenv('NETGSM_PASS', '').strip(),
        os.getenv('NETGSM_HEADER', '').strip(),
        os.getenv('SMS_TO', '').strip(),
    ])
    twilio_ok = all([
        os.getenv('TWILIO_ACCOUNT_SID', '').strip(),
        os.getenv('TWILIO_AUTH_TOKEN', '').strip(),
        os.getenv('TWILIO_FROM', '').strip(),
        os.getenv('SMS_TO', '').strip(),
    ])
    telegram_on = os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'
    sms_on = os.getenv('SMS_ENABLED', 'false').lower() == 'true'
    return {
        'telegram': {
            'enabled': telegram_on,
            'ready': telegram_on and bool(tg_token) and bool(tg_chat),
            'has_token': bool(tg_token),
            'has_chat_id': bool(tg_chat),
        },
        'sms': {
            'enabled': sms_on,
            'provider': sms_provider or None,
            'ready': sms_on and (
                (sms_provider == 'netgsm' and netgsm_ok)
                or (sms_provider == 'twilio' and twilio_ok)
            ),
            'to': (os.getenv('SMS_TO') or '').strip() or None,
        },
    }


def send_telegram(title: str, body: str) -> dict:
    if os.getenv('TELEGRAM_ENABLED', 'false').lower() != 'true':
        return {'sent': False, 'skipped': True, 'reason': 'TELEGRAM_ENABLED=false'}
    token = (os.getenv('TELEGRAM_BOT_TOKEN') or '').strip()
    chat_id = (os.getenv('TELEGRAM_CHAT_ID') or '').strip()
    if not token or not chat_id:
        return {'sent': False, 'error': 'TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID eksik'}

    # Duz metin — Markdown ozel karakterleri ( _ * ) yuzunden 400 hatasi olmasin
    text = f"🚨 {title}\n\n{body}"
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(url, json={
                'chat_id': chat_id,
                'text': text,
                'disable_web_page_preview': True,
            })
        data = {}
        try:
            data = resp.json()
        except Exception:
            pass
        if resp.status_code == 200 and data.get('ok'):
            logger.info(f"Telegram gonderildi | chat={chat_id}")
            return {'sent': True, 'channel': 'telegram'}
        err = data.get('description') or resp.text[:200]
        logger.warning(f"Telegram basarisiz | HTTP {resp.status_code} | {err}")
        return {
            'sent': False,
            'channel': 'telegram',
            'error': f'HTTP {resp.status_code}: {err}',
        }
    except Exception as e:
        logger.warning(f"Telegram hatasi: {e}")
        return {'sent': False, 'channel': 'telegram', 'error': str(e)}


def _send_netgsm(message: str) -> dict:
    user = os.getenv('NETGSM_USER', '').strip()
    password = os.getenv('NETGSM_PASS', '').strip()
    header = os.getenv('NETGSM_HEADER', '').strip()
    gsm = os.getenv('SMS_TO', '').strip().replace(' ', '').replace('+90', '0')
    if gsm.startswith('90') and len(gsm) == 12:
        gsm = '0' + gsm[2:]
    if not all([user, password, header, gsm]):
        return {'sent': False, 'error': 'Netgsm bilgileri eksik'}

    # Netgsm GET API
    url = (
        'https://api.netgsm.com.tr/sms/send/get/'
        f'?usercode={quote(user)}&password={quote(password)}'
        f'&gsmno={quote(gsm)}&message={quote(message[:300])}'
        f'&msgheader={quote(header)}'
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
        code = (resp.text or '').strip().split()[0] if resp.text else ''
        # 00 / 01 / 02 basarili donus kodlari
        if code in ('00', '01', '02'):
            logger.info(f"Netgsm SMS gonderildi | {gsm}")
            return {'sent': True, 'channel': 'netgsm', 'code': code}
        return {'sent': False, 'channel': 'netgsm', 'error': resp.text[:200]}
    except Exception as e:
        return {'sent': False, 'channel': 'netgsm', 'error': str(e)}


def _send_twilio(message: str) -> dict:
    sid = os.getenv('TWILIO_ACCOUNT_SID', '').strip()
    token = os.getenv('TWILIO_AUTH_TOKEN', '').strip()
    from_no = os.getenv('TWILIO_FROM', '').strip()
    to_no = os.getenv('SMS_TO', '').strip()
    if not all([sid, token, from_no, to_no]):
        return {'sent': False, 'error': 'Twilio bilgileri eksik'}
    url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                url,
                data={'From': from_no, 'To': to_no, 'Body': message[:300]},
                auth=(sid, token),
            )
        if resp.status_code in (200, 201):
            logger.info(f"Twilio SMS gonderildi | {to_no}")
            return {'sent': True, 'channel': 'twilio'}
        return {'sent': False, 'channel': 'twilio', 'error': resp.text[:200]}
    except Exception as e:
        return {'sent': False, 'channel': 'twilio', 'error': str(e)}


def send_sms(title: str, body: str) -> dict:
    if os.getenv('SMS_ENABLED', 'false').lower() != 'true':
        return {'sent': False, 'skipped': True, 'reason': 'SMS_ENABLED=false'}
    provider = (os.getenv('SMS_PROVIDER') or 'netgsm').strip().lower()
    message = f'{title}\n{body}'[:300]
    if provider == 'twilio':
        return _send_twilio(message)
    if provider == 'netgsm':
        return _send_netgsm(message)
    return {'sent': False, 'error': f'Bilinmeyen SMS_PROVIDER={provider}'}


def send_phone_alert(payload: dict) -> dict:
    """Anomali sonrasi telefona Telegram ve/veya SMS."""
    title, body = format_push_message(payload)
    out = {
        'title': title,
        'body': body,
        'telegram': send_telegram(title, body),
        'sms': send_sms(title, body),
        'status': phone_status(),
    }
    any_sent = bool(out['telegram'].get('sent') or out['sms'].get('sent'))
    out['sent'] = any_sent
    if not any_sent:
        reasons = []
        for ch in ('telegram', 'sms'):
            r = out[ch]
            if r.get('skipped'):
                continue
            if r.get('error'):
                reasons.append(f"{ch}: {r['error']}")
        if not reasons:
            reasons.append('Telegram/SMS kapali veya yapilandirilmamis')
        out['error'] = '; '.join(reasons)
    return out
