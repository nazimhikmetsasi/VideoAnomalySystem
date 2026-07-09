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
