import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_env
load_env()

from llm.reporter import LLMReporter


def test_llm_template_report():
    reporter = LLMReporter()
    event = {
        'camera_id': 'cam_01',
        'track_id': 5,
        'anomaly_type': 'FALL',
        'confidence_score': 0.92,
        'metrics': {'vertical_velocity': -100}
    }
    report = reporter.generate_report(event)
    assert 'cam_01' in report
    assert 'dusme' in report.lower() or '5' in report


def test_llm_status():
    reporter = LLMReporter()
    status = reporter.status()
    assert status['provider'] in ('gemini', 'openai')
    assert status['mode'] in ('llm', 'template')


def test_llm_test_connection():
    reporter = LLMReporter()
    result = reporter.test_connection()
    assert 'ok' in result
    assert 'sample_report' in result
    assert len(result['sample_report']) > 10


def test_daily_template_report():
    reporter = LLMReporter()
    summary = {
        'date': '22 Temmuz 2026',
        'total': 2,
        'by_type': {'ZONE_VIOLATION': 2},
        'cameras': ['cam_01'],
        'hourly': [0] * 24,
        'peak_hour': 15,
        'top_events': [
            {
                'anomaly_type': 'ZONE_VIOLATION',
                'camera_id': 'cam_01',
                'track_id': 1,
                'confidence_score': 0.9,
            }
        ],
    }
    # Force template path
    reporter._llm_cooldown_until = 1e18
    out = reporter.generate_daily_report(summary)
    assert out['mode'] == 'template'
    assert '2' in out['report']
    assert 'cam_01' in out['report']
