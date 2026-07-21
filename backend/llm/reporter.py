import os
import logging
import time
import httpx

logger = logging.getLogger('api')

ANOMALY_LABELS = {
    'FALL': 'yere dusme',
    'PERSON_ENTERED': 'kisi kareye girdi',
    'RUN': 'hizli kosma',
    'ZONE_VIOLATION': 'yasakli alan ihlali',
    'RUN_ZONE': 'kosarak yasakli alan ihlali',
}


class LLMReporter:
    """Teknik anomali verilerini Turkce rapora donusturur."""

    def __init__(self):
        self._refresh_config()
        # Kota/429 sonrasi bir sure sadece sablon kullan (panel gecikmesin)
        self._llm_cooldown_until = 0.0

    def _refresh_config(self):
        self.provider = os.getenv('LLM_PROVIDER', 'gemini').lower()
        self.gemini_key = (os.getenv('GEMINI_API_KEY') or '').strip()
        self.openai_key = (os.getenv('OPENAI_API_KEY') or '').strip()
        self.model = os.getenv('LLM_MODEL', 'gemini-2.0-flash')
        self.http_timeout = float(os.getenv('LLM_HTTP_TIMEOUT_SEC', 4))
        self.quota_cooldown = float(os.getenv('LLM_QUOTA_COOLDOWN_SEC', 600))

    def _llm_available(self) -> bool:
        return time.time() >= self._llm_cooldown_until

    def _trip_quota_cooldown(self, err: Exception):
        text = str(err)
        if '429' in text or 'quota' in text.lower() or 'rate' in text.lower():
            self._llm_cooldown_until = time.time() + self.quota_cooldown
            logger.warning(
                f"LLM kota/limit — {self.quota_cooldown:.0f}sn sablon modu"
            )

    def status(self) -> dict:
        self._refresh_config()
        if self.provider == 'gemini':
            configured = bool(self.gemini_key)
        elif self.provider == 'openai':
            configured = bool(self.openai_key)
        else:
            configured = False
        cooling = not self._llm_available()
        return {
            'provider': self.provider,
            'model': self.model,
            'configured': configured,
            'mode': 'template' if cooling or not configured else 'llm',
            'quota_cooldown': cooling,
        }

    def generate_report(self, event: dict) -> str:
        self._refresh_config()

        if not self._llm_available():
            return self._template_report(event)

        if self.provider == 'gemini' and self.gemini_key:
            try:
                report = self._gemini_report(event)
                logger.info(f"Gemini rapor uretildi | {event.get('anomaly_type')}")
                return report
            except Exception as e:
                self._trip_quota_cooldown(e)
                logger.warning(f"Gemini hatasi, sablon kullaniliyor: {e}")

        if self.provider == 'openai' and self.openai_key:
            try:
                report = self._openai_report(event)
                logger.info(f"OpenAI rapor uretildi | {event.get('anomaly_type')}")
                return report
            except Exception as e:
                self._trip_quota_cooldown(e)
                logger.warning(f"OpenAI hatasi, sablon kullaniliyor: {e}")

        if self.provider in ('gemini', 'openai') and not (self.gemini_key or self.openai_key):
            logger.debug("LLM anahtari yok — sablon rapor kullaniliyor")

        return self._template_report(event)

    def test_connection(self) -> dict:
        """API anahtarini ornek olay ile dener."""
        sample = {
            'camera_id': 'cam_01',
            'track_id': 1,
            'anomaly_type': 'RUN',
            'confidence_score': 0.91,
            'metrics': {
                'horizontal_velocity': 95.2,
                'vertical_velocity': 12.0,
                'spine_angle': 18.5,
            },
        }
        status = self.status()
        if status['mode'] == 'template':
            return {
                **status,
                'ok': False,
                'message': 'API anahtari tanimli degil. .env dosyasina GEMINI_API_KEY ekleyin.',
                'sample_report': self._template_report(sample),
            }

        try:
            if self.provider == 'gemini':
                report = self._gemini_report(sample)
            elif self.provider == 'openai':
                report = self._openai_report(sample)
            else:
                raise RuntimeError(f"Bilinmeyen provider: {self.provider}")
            return {
                **status,
                'ok': True,
                'message': 'LLM baglantisi basarili',
                'sample_report': report,
            }
        except Exception as e:
            return {
                **status,
                'ok': False,
                'message': str(e),
                'sample_report': self._template_report(sample),
            }

    def _build_prompt(self, event: dict) -> str:
        label = ANOMALY_LABELS.get(event['anomaly_type'], event['anomaly_type'])
        metrics = event.get('metrics') or {}
        motion = event.get('motion') or event.get('motion_confirmed') or metrics.get('motion')
        return (
            "Sen bir guvenlik izleme sistemisin. Asagidaki anomaliyi kisa, resmi Turkce "
            "ihbar cumlesine cevir. Tek paragraf, en fazla 2 cumle. "
            "Mumkunse su tarza yakin yaz: "
            "'Varlik ID:2 kosarak yasakli alana giris yapti (cam_01). Guven: %95.' "
            "Uydurma bilgi ekleme; sadece verilen alanlari kullan.\n"
            f"Kamera: {event['camera_id']}\n"
            f"Varlik ID: {event['track_id']}\n"
            f"Anomali: {label} ({event.get('anomaly_type')})\n"
            f"Hareket: {motion or 'bilinmiyor'}\n"
            f"Guven: {event['confidence_score']}\n"
            f"Dikey hiz: {metrics.get('vertical_velocity', 'N/A')}\n"
            f"Yatay hiz: {metrics.get('horizontal_velocity', 'N/A')}\n"
            f"Omurga acisi: {metrics.get('spine_angle', 'N/A')}"
        )

    def _extract_gemini_text(self, data: dict) -> str:
        candidates = data.get('candidates') or []
        if not candidates:
            block = data.get('promptFeedback') or {}
            raise RuntimeError(f"Gemini yanit vermedi: {block}")

        parts = candidates[0].get('content', {}).get('parts') or []
        text = ''.join(p.get('text', '') for p in parts).strip()
        if not text:
            raise RuntimeError("Gemini bos metin dondurdu")
        return text

    def _gemini_report(self, event: dict) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            'contents': [{'parts': [{'text': self._build_prompt(event)}]}],
            'generationConfig': {'temperature': 0.4, 'maxOutputTokens': 256},
        }
        with httpx.Client(timeout=self.http_timeout) as client:
            resp = client.post(url, params={'key': self.gemini_key}, json=payload)
            if resp.status_code != 200:
                detail = resp.text[:300]
                raise RuntimeError(f"Gemini HTTP {resp.status_code}: {detail}")
            return self._extract_gemini_text(resp.json())

    def _openai_report(self, event: dict) -> str:
        url = 'https://api.openai.com/v1/chat/completions'
        headers = {'Authorization': f'Bearer {self.openai_key}'}
        payload = {
            'model': self.model if 'gpt' in self.model else 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': 'Sen bir guvenlik operasyonu raporlama asistanisin.'},
                {'role': 'user', 'content': self._build_prompt(event)},
            ],
            'max_tokens': 200,
        }
        with httpx.Client(timeout=self.http_timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content'].strip()

    def _template_report(self, event: dict) -> str:
        atype = event.get('anomaly_type')
        tid = event.get('track_id')
        cam = event.get('camera_id')
        score = float(event.get('confidence_score', 0) or 0)
        motion = event.get('motion_confirmed') or event.get('motion')
        in_zone = event.get('in_zone')

        if atype == 'RUN_ZONE' or (atype == 'ZONE_VIOLATION' and motion in ('RUNNING', 'RUN')):
            action = 'kosarak yasakli alana giris yapti'
        elif atype == 'RUN' and in_zone:
            action = 'kosarak yasakli alana giris yapti'
        elif atype == 'RUN':
            action = 'hizli kosma hareketi sergiledi'
        elif atype == 'ZONE_VIOLATION':
            action = 'yasakli alana giris yapti'
        elif atype == 'FALL':
            action = 'dusme hareketi sergiledi'
        else:
            label = ANOMALY_LABELS.get(atype, atype)
            action = f'{label} tespit edildi'

        return (
            f"Varlik ID:{tid} {action} ({cam}). Guven skoru: {score:.2f}."
        )
