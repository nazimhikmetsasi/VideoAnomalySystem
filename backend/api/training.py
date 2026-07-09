"""Model egitimi API durumu."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()
_state = {
    'status': 'idle',
    'started_at': None,
    'finished_at': None,
    'result': None,
    'error': None,
}


def get_training_status() -> dict:
    with _lock:
        return dict(_state)


def _run_training():
    global _state
    try:
        from training.finetune_yolo import run_finetune
        result = run_finetune()
        with _lock:
            _state['status'] = 'completed'
            _state['finished_at'] = datetime.now().isoformat()
            _state['result'] = result
    except Exception as e:
        with _lock:
            _state['status'] = 'failed'
            _state['finished_at'] = datetime.now().isoformat()
            _state['error'] = str(e)


def start_training_async() -> dict:
    with _lock:
        if _state['status'] == 'running':
            return {'ok': False, 'message': 'Egitim zaten devam ediyor'}
        _state.update({
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'finished_at': None,
            'result': None,
            'error': None,
        })
    threading.Thread(target=_run_training, daemon=True).start()
    return {'ok': True, 'message': 'Fine-tune arka planda baslatildi'}


def latest_model_info() -> dict:
    root = Path(__file__).resolve().parents[2]
    project = os.getenv('FINETUNE_PROJECT', str(root / 'runs' / 'detect'))
    name = os.getenv('FINETUNE_NAME', 'pilot_person')
    best = Path(project) / name / 'weights' / 'best.pt'
    current = os.getenv('YOLO_MODEL_PATH', 'yolov8n.pt')
    return {
        'current_model': current,
        'best_finetuned': str(best) if best.exists() else None,
        'finetuned_ready': best.exists(),
    }
