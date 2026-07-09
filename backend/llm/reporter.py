import os
import logging
import httpx

logger = logging.getLogger('video_pipeline')

ANOMALY_LABELS = {
    'FALL': 'yere dusme',
    'RUN': 'hizli kosma',
    'ZONE_VIOLATION': 'yasakli alan ihlali'
}


class LLMReporter:
    """Teknik anomali verilerini Turkce rapora donusturur."""

    def __init__(self):
        self.provider = os.getenv('LLM_PROVIDER', 'gemini').lower()
        self.gemini_key = os.getenv('GEMINI_API_KEY', '')
        self.openai_key = os.getenv('OPENAI_API_KEY', '')
        self.model = os.getenv('LLM_MODEL', 'gemini-2.0-flash')

    def generate_report(self, event: dict) -> str:
        if self.provider == 'gemini' and self.gemini_key:
            try:
                return self._gemini_report(event)
            except Exception as e:
                logger.warning(f"Gemini hatasi, sablon kullaniliyor: {e}")

        if self.provider == 'openai' and self.openai_key:
            try:
                return self._openai_report(event)
            except Exception as e:
                logger.warning(f"OpenAI hatasi, sablon kullaniliyor: {e}")

        return self._template_report(event)

    def _build_prompt(self, event: dict) -> str:
        label = ANOMALY_LABELS.get(event['anomaly_type'], event['anomaly_type'])
        metrics = event.get('metrics', {})
        return (
            f"Asagidaki guvenlik kamerasi anomali verisini Turkce, resmi ve anlasilir "
            f"bir ihbar metnine donustur. Tek paragraf, max 2 cumle.\n"
            f"Kamera: {event['camera_id']}\n"
            f"Kisi ID: {event['track_id']}\n"
            f"Anomali: {label}\n"
            f"Guven: {event['confidence_score']}\n"
            f"Dikey hiz: {metrics.get('vertical_velocity', 'N/A')}\n"
            f"Yatay hiz: {metrics.get('horizontal_velocity', 'N/A')}\n"
            f"Omurga acisi: {metrics.get('spine_angle', 'N/A')}"
        )

    def _gemini_report(self, event: dict) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            'contents': [{'parts': [{'text': self._build_prompt(event)}]}]
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, params={'key': self.gemini_key}, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data['candidates'][0]['content']['parts'][0]['text'].strip()

    def _openai_report(self, event: dict) -> str:
        url = 'https://api.openai.com/v1/chat/completions'
        headers = {'Authorization': f'Bearer {self.openai_key}'}
        payload = {
            'model': self.model if 'gpt' in self.model else 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': 'Sen bir guvenlik operasyonu raporlama asistanisin.'},
                {'role': 'user', 'content': self._build_prompt(event)}
            ],
            'max_tokens': 200
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content'].strip()

    def _template_report(self, event: dict) -> str:
        label = ANOMALY_LABELS.get(event['anomaly_type'], event['anomaly_type'])
        return (
            f"{event['camera_id']} numarali kamerada, {event['track_id']} ID'li kiside "
            f"{label} tespit edildi. Guven skoru: {event['confidence_score']:.2f}."
        )
