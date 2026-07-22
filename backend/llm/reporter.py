import os
import logging
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

logger = logging.getLogger('api')

ANOMALY_LABELS = {
    'FALL': 'yere düşme',
    'PERSON_ENTERED': 'kişi kareye girdi',
    'RUN': 'hızlı koşma',
    'ZONE_VIOLATION': 'yasaklı alan ihlali',
    'RUN_ZONE': 'koşarak yasaklı alan ihlali',
}

# Dusunme tokeni tuketip metni MAX_TOKENS ile kesen modeller
_THINKING_MODELS = {
    'gemini-flash-latest',
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-2.0-flash-thinking-exp',
}
_SAFE_GEMINI_MODEL = 'gemini-flash-lite-latest'
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / '.env'


class LLMReporter:
    """Teknik anomali verilerini Turkce rapora donusturur."""

    def __init__(self):
        self._refresh_config()
        # Kota/429 sonrasi bir sure sadece sablon kullan (panel gecikmesin)
        self._llm_cooldown_until = 0.0

    def _file_env(self, key: str, default=None):
        """`.env` dosyasini once oku — process env eski kalsa bile model guncellenir."""
        if _ENV_FILE.exists():
            vals = dotenv_values(_ENV_FILE)
            raw = vals.get(key)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
        return os.getenv(key, default)

    def _refresh_config(self):
        self.provider = (self._file_env('LLM_PROVIDER', 'gemini') or 'gemini').lower()
        self.gemini_key = (self._file_env('GEMINI_API_KEY') or '').strip()
        self.openai_key = (self._file_env('OPENAI_API_KEY') or '').strip()
        model = (self._file_env('LLM_MODEL', _SAFE_GEMINI_MODEL) or _SAFE_GEMINI_MODEL).strip()
        # Dusunme modelleri cumleyi yarida keser → zorunlu guvenli model
        if (
            model in _THINKING_MODELS
            or 'thinking' in model.lower()
            or (model.startswith('gemini') and model.endswith('-latest') and 'lite' not in model)
        ):
            if model != _SAFE_GEMINI_MODEL:
                logger.warning(
                    f"LLM_MODEL={model} kesik metin uretebilir → {_SAFE_GEMINI_MODEL}"
                )
            model = _SAFE_GEMINI_MODEL
        self.model = model
        self.http_timeout = float(self._file_env('LLM_HTTP_TIMEOUT_SEC', '4') or 4)
        self.quota_cooldown = float(self._file_env('LLM_QUOTA_COOLDOWN_SEC', '600') or 600)

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
            if status.get('quota_cooldown'):
                msg = (
                    'LLM kota/limit sogutmasinda — bir sure sablon kullaniliyor. '
                    'API yeniden baslatilarak sogutma sifirlanabilir.'
                )
            elif not status.get('configured'):
                msg = 'API anahtari tanimli degil. .env dosyasina GEMINI_API_KEY ekleyin.'
            else:
                msg = 'Sablon modu aktif.'
            return {
                **status,
                'ok': False,
                'message': msg,
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

        cand = candidates[0]
        parts = cand.get('content', {}).get('parts') or []
        # Dusunme (thought) parcalarini atla — sadece rapor metni
        text = ''.join(
            p.get('text', '') for p in parts
            if p.get('text') and not p.get('thought')
        ).strip()
        if not text:
            # Bazi modeller tumunu text'te dondurur
            text = ''.join(p.get('text', '') for p in parts).strip()
        if not text:
            finish = cand.get('finishReason')
            raise RuntimeError(f"Gemini bos metin dondurdu (finish={finish})")
        return text

    @staticmethod
    def _looks_complete(text: str) -> bool:
        """Cumle yarida kesilmis mi? Noktalama ile bitmeli."""
        t = (text or '').strip()
        if len(t) < 30:
            return False
        return t[-1] in '.!?…' or t.endswith(('."', ".'", '.)', '!”', '?”'))

    def _gemini_call(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.3):
        """Tek Gemini cagrisi → (text, finishReason)."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        gen_cfg = {
            'temperature': temperature,
            'maxOutputTokens': max_tokens,
        }
        # Destekleyen modellerde dusunmeyi kapat (kesik metni onler)
        if 'lite' not in self.model:
            gen_cfg['thinkingConfig'] = {'thinkingBudget': 0}
        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': gen_cfg,
        }
        timeout = max(self.http_timeout, 60.0)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, params={'key': self.gemini_key}, json=payload)
            if resp.status_code != 200:
                detail = resp.text[:300]
                raise RuntimeError(f"Gemini HTTP {resp.status_code}: {detail}")
            data = resp.json()
        text = self._extract_gemini_text(data)
        finish = ((data.get('candidates') or [{}])[0]).get('finishReason') or ''
        if finish == 'MAX_TOKENS':
            logger.warning("Gemini finishReason=MAX_TOKENS — devam denenecek")
        return text, finish

    def _gemini_complete(self, prompt: str, max_tokens: int = 2048, rounds: int = 3) -> str:
        """Tam cumle uretene kadar devam ettir; yine yarimsa hata firlat."""
        text, finish = self._gemini_call(prompt, max_tokens=max_tokens)
        for _ in range(rounds - 1):
            if finish != 'MAX_TOKENS' and self._looks_complete(text):
                return text
            cont = (
                "Asagidaki Turkce guvenlik raporunu yarida kaldigi yerden devam ettirip "
                "tamamla. Onceki metni tekrar etme; sadece devamini yaz. "
                "Son cumleyi bitir ve raporu nokta ile kapat.\n\n"
                f"Onceki metin:\n{text}"
            )
            more, finish = self._gemini_call(cont, max_tokens=max_tokens, temperature=0.2)
            text = f"{text.rstrip()} {more.lstrip()}".strip()
        if not self._looks_complete(text):
            raise RuntimeError('Gemini raporu yarim kaldi (tamamlanamadi)')
        return text

    def _gemini_report(self, event: dict) -> str:
        return self._gemini_complete(self._build_prompt(event), max_tokens=1024, rounds=2)

    def _gemini_text_or_raise(self, data: dict) -> str:
        text = self._extract_gemini_text(data)
        finish = ((data.get('candidates') or [{}])[0]).get('finishReason')
        if finish == 'MAX_TOKENS':
            logger.warning("Gemini finishReason=MAX_TOKENS — metin kesik olabilir")
        return text

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
            action = 'koşarak yasaklı alana giriş yaptı'
        elif atype == 'RUN' and in_zone:
            action = 'koşarak yasaklı alana giriş yaptı'
        elif atype == 'RUN':
            action = 'hızlı koşma hareketi sergiledi'
        elif atype == 'ZONE_VIOLATION':
            action = 'yasaklı alana giriş yaptı'
        elif atype == 'FALL':
            action = 'düşme hareketi sergiledi'
        else:
            label = ANOMALY_LABELS.get(atype, atype)
            action = f'{label} tespit edildi'

        return (
            f"Varlık ID:{tid} {action} ({cam}). Güven skoru: {score:.2f}."
        )

    def generate_daily_report(self, summary: dict) -> dict:
        """Gunluk ozet raporu — Gemini varsa AI, yarimsa/sablon garantili tam metin."""
        self._refresh_config()
        status = self.status()
        mode = status['mode']
        template = self._template_daily(summary)
        text = None

        if mode == 'llm' and self.provider == 'gemini' and self.gemini_key:
            try:
                text = self._gemini_daily(summary)
                if not self._looks_complete(text):
                    raise RuntimeError('Gemini gunluk raporu yarim')
            except Exception as e:
                self._trip_quota_cooldown(e)
                logger.warning(f"Gemini gunluk rapor hatasi, sablon: {e}")
                mode = 'template'
                text = None
        elif mode == 'llm' and self.provider == 'openai' and self.openai_key:
            try:
                text = self._openai_daily(summary)
                if not self._looks_complete(text):
                    raise RuntimeError('OpenAI gunluk raporu yarim')
            except Exception as e:
                self._trip_quota_cooldown(e)
                logger.warning(f"OpenAI gunluk rapor hatasi, sablon: {e}")
                mode = 'template'
                text = None

        if not text:
            text = template
            mode = 'template'

        return {
            'report': text,
            'mode': mode,
            'provider': status['provider'],
            'model': status['model'],
        }

    def _daily_prompt(self, summary: dict) -> str:
        by_type = summary.get('by_type') or {}
        type_lines = ', '.join(
            f"{ANOMALY_LABELS.get(k, k)}: {v}" for k, v in by_type.items()
        ) or 'yok'
        top = summary.get('top_events') or []
        top_lines = []
        for e in top[:5]:
            tip = ANOMALY_LABELS.get(e.get('anomaly_type'), e.get('anomaly_type'))
            top_lines.append(
                f"- {tip} | kam={e.get('camera_id')} | id={e.get('track_id')} | "
                f"guven={e.get('confidence_score')}"
            )
        peak = summary.get('peak_hour')
        return (
            "Sen bir guvenlik izleme operasyon asistanisin. Asagidaki gunluk istatistiklerden "
            "resmi Turkce durum raporu yaz. Tam 4 kisa cumle; her cumleyi nokta ile bitir. "
            "Cumleleri yarida kesme. Madde isareti kullanma. Toplam uyari, tip dagilimi, "
            "kamera, yogun saat ve kritik olaylardan bahset. Uydurma bilgi ekleme.\n"
            f"Tarih: {summary.get('date')}\n"
            f"Toplam uyari: {summary.get('total', 0)}\n"
            f"Tip dagilimi: {type_lines}\n"
            f"Kameralar: {', '.join(summary.get('cameras') or []) or 'yok'}\n"
            f"En yogun saat: {peak if peak is not None else 'yok'} (0-23)\n"
            f"Kritik olaylar:\n" + ('\n'.join(top_lines) if top_lines else 'yok')
        )

    def _gemini_daily(self, summary: dict) -> str:
        return self._gemini_complete(self._daily_prompt(summary), max_tokens=2048, rounds=3)

    def _openai_daily(self, summary: dict) -> str:
        url = 'https://api.openai.com/v1/chat/completions'
        headers = {'Authorization': f'Bearer {self.openai_key}'}
        payload = {
            'model': self.model if 'gpt' in self.model else 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': 'Sen bir guvenlik operasyonu raporlama asistanisin.'},
                {'role': 'user', 'content': self._daily_prompt(summary)},
            ],
            'max_tokens': 450,
        }
        timeout = max(self.http_timeout, 12.0)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content'].strip()

    def _template_daily(self, summary: dict) -> str:
        total = int(summary.get('total') or 0)
        date = summary.get('date') or 'bugün'
        by_type = summary.get('by_type') or {}
        cams = summary.get('cameras') or []
        peak = summary.get('peak_hour')
        top = summary.get('top_events') or []

        if total == 0:
            return (
                f"{date} tarihli MCBU anomali durum raporu: Bugün kayıtlı uyarı bulunmamaktadır. "
                f"İzlenen kamera sayısı: {len(cams) or 0}. Sistem izlemeye devam etmektedir."
            )

        parts = [
            f"{ANOMALY_LABELS.get(k, k)} ({v})" for k, v in sorted(
                by_type.items(), key=lambda x: -x[1]
            )
        ]
        dist = ', '.join(parts) if parts else 'dağılım yok'
        cam_txt = ', '.join(cams) if cams else 'belirtilmedi'
        peak_txt = (
            f" En yoğun saat dilimi {int(peak):02d}:00 civarıdır."
            if peak is not None else ''
        )

        crit_bits = []
        for e in top[:3]:
            tip = ANOMALY_LABELS.get(e.get('anomaly_type'), e.get('anomaly_type'))
            conf = e.get('confidence_score')
            try:
                conf_s = f"{float(conf):.2f}"
            except (TypeError, ValueError):
                conf_s = str(conf)
            crit_bits.append(
                f"{tip} (kamera {e.get('camera_id')}, varlık {e.get('track_id')}, güven {conf_s})"
            )
        crit = (
            f" Öne çıkan olaylar: {'; '.join(crit_bits)}."
            if crit_bits else ''
        )

        return (
            f"{date} tarihli MCBU anomali durum raporu: Bugün toplam {total} uyarı kaydedilmiştir. "
            f"Tip dağılımı: {dist}. İlgili kameralar: {cam_txt}.{peak_txt}{crit} "
            f"Rapor şablon motoru ile üretilmiştir."
        )
