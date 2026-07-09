"""
YOLOv8 fine-tune — pilot detection veri seti ile kisi tespiti iyilestirme.
"""
from __future__ import annotations

import os
from pathlib import Path

from config import load_env

load_env()


def run_finetune(
    dataset_yaml: str | None = None,
    base_model: str | None = None,
    epochs: int | None = None,
    imgsz: int | None = None,
    batch: int | None = None,
    project: str | None = None,
    name: str | None = None,
) -> dict:
    from ultralytics import YOLO

    root = Path(__file__).resolve().parents[2]
    yaml_path = Path(dataset_yaml) if dataset_yaml else root / 'datasets' / 'pilot' / 'detection' / 'dataset.yaml'
    images_dir = yaml_path.parent / 'images'

    if not yaml_path.exists():
        raise FileNotFoundError(f'Dataset yaml bulunamadi: {yaml_path}')
    if not images_dir.exists() or not any(images_dir.glob('*')):
        raise FileNotFoundError(
            f'Goruntu yok: {images_dir}\n'
            f'Once datasets/pilot/detection/images/ ve labels/ doldurun.'
        )

    model_path = base_model or os.getenv('YOLO_MODEL_PATH', 'yolov8n.pt')
    epochs = epochs or int(os.getenv('FINETUNE_EPOCHS', 30))
    imgsz = imgsz or int(os.getenv('FINETUNE_IMGSZ', 640))
    batch = batch or int(os.getenv('FINETUNE_BATCH', 8))
    project = project or os.getenv('FINETUNE_PROJECT', str(root / 'runs' / 'detect'))
    name = name or os.getenv('FINETUNE_NAME', 'pilot_person')

    device = 'cuda' if os.getenv('USE_GPU', 'true').lower() == 'true' else 'cpu'
    model = YOLO(model_path)

    results = model.train(
        data=str(yaml_path),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=project,
        name=name,
        device=device,
        patience=10,
        exist_ok=True,
        verbose=True,
    )

    best_weights = Path(project) / name / 'weights' / 'best.pt'
    return {
        'status': 'ok',
        'dataset': str(yaml_path),
        'base_model': model_path,
        'epochs': epochs,
        'best_weights': str(best_weights) if best_weights.exists() else None,
        'message': (
            f'Egitim tamamlandi. .env icinde YOLO_MODEL_PATH={best_weights} yaparak kullanin.'
            if best_weights.exists() else 'Egitim bitti — best.pt yolunu kontrol edin.'
        ),
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_finetune(), ensure_ascii=False, indent=2))
