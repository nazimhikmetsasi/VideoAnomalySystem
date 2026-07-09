"""YOLO kisi tespiti mAP degerlendirmesi."""

from __future__ import annotations

import os
from pathlib import Path


def run_detection_benchmark(dataset_yaml: str | None = None) -> dict:
    """
    datasets/pilot/detection/dataset.yaml varsa ozel mAP.
    Yoksa yolov8n COCO on-egitim mAP referansi dondurur.
    """
    from ultralytics import YOLO

    model_path = os.getenv('YOLO_MODEL_PATH', 'yolov8n.pt')
    model = YOLO(model_path)

    root = Path(__file__).resolve().parents[2]
    default_yaml = root / 'datasets' / 'pilot' / 'detection' / 'dataset.yaml'

    yaml_path = Path(dataset_yaml) if dataset_yaml else default_yaml
    images_dir = yaml_path.parent / 'images'
    if yaml_path.exists() and images_dir.exists() and any(images_dir.glob('*')):
        metrics = model.val(data=str(yaml_path), verbose=False)
        box = metrics.box
        return {
            'source': 'pilot_dataset',
            'dataset': str(yaml_path),
            'map50': round(float(box.map50), 4),
            'map50_95': round(float(box.map), 4),
            'precision': round(float(box.mp), 4),
            'recall': round(float(box.mr), 4),
        }

    # Referans: COCO person sinifi icin on-egitimli model metrikleri (offline yaml gerekmez)
    return {
        'source': 'pretrained_reference',
        'dataset': None,
        'map50': 0.52,
        'map50_95': 0.37,
        'precision': None,
        'recall': None,
        'note': (
            'Ozel pilot etiketleri icin datasets/pilot/detection/ klasorune '
            'goruntu + YOLO label ekleyin ve dataset.yaml olusturun. '
            'Su an yolov8n COCO referans degerleri gosteriliyor.'
        ),
    }
