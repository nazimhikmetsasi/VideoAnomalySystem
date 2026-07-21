"""
Pilot videolardan kare cikarir + yolov8n ile person pseudo-label yazar.
Sonra run_finetune.bat ile egitim yapilabilir.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from ultralytics import YOLO

from config import load_env

load_env()

ROOT = Path(__file__).resolve().parents[2]
VIDEOS_DIR = ROOT / 'datasets' / 'pilot' / 'videos'
IMAGES_DIR = ROOT / 'datasets' / 'pilot' / 'detection' / 'images'
LABELS_DIR = ROOT / 'datasets' / 'pilot' / 'detection' / 'labels'
PERSON_CLASS = 0


def extract_and_label(
    stride: int = 20,
    max_per_video: int = 40,
    conf: float = 0.35,
    model_path: str = 'yolov8n.pt',
) -> dict:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    # Eski README disindaki etiketleri temizleme: sadece yeni uretilenleri yazariz
    videos = sorted(VIDEOS_DIR.glob('*.mp4'))
    if not videos:
        raise FileNotFoundError(f'Video yok: {VIDEOS_DIR}')

    model = YOLO(str(ROOT / model_path) if (ROOT / model_path).exists() else model_path)

    saved = 0
    labeled = 0
    skipped_empty = 0

    for video in videos:
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            print(f'[UYARI] Acilamadi: {video.name}')
            continue

        frame_idx = 0
        kept = 0
        stem = video.stem

        while kept < max_per_video:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_idx % stride != 0:
                frame_idx += 1
                continue

            results = model.predict(frame, conf=conf, classes=[PERSON_CLASS], verbose=False)
            boxes = results[0].boxes if results else None
            if boxes is None or len(boxes) == 0:
                skipped_empty += 1
                frame_idx += 1
                continue

            h, w = frame.shape[:2]
            name = f'{stem}_{frame_idx:06d}'
            img_path = IMAGES_DIR / f'{name}.jpg'
            lbl_path = LABELS_DIR / f'{name}.txt'

            cv2.imwrite(str(img_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

            lines = []
            for box in boxes:
                # xyxy -> YOLO normalized cx,cy,bw,bh
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = ((x1 + x2) / 2.0) / w
                cy = ((y1 + y2) / 2.0) / h
                bw = (x2 - x1) / w
                bh = (y2 - y1) / h
                lines.append(f'{PERSON_CLASS} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}')

            lbl_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            saved += 1
            labeled += 1
            kept += 1
            frame_idx += 1

        cap.release()
        print(f'[OK] {video.name}: {kept} kare')

    return {
        'videos': len(videos),
        'images_saved': saved,
        'labels_saved': labeled,
        'skipped_no_person': skipped_empty,
        'images_dir': str(IMAGES_DIR),
        'labels_dir': str(LABELS_DIR),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stride', type=int, default=20)
    parser.add_argument('--max-per-video', type=int, default=40)
    parser.add_argument('--conf', type=float, default=0.35)
    args = parser.parse_args()
    import json
    out = extract_and_label(stride=args.stride, max_per_video=args.max_per_video, conf=args.conf)
    print(json.dumps(out, ensure_ascii=False, indent=2))
