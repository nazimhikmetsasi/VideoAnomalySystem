import cv2
import numpy as np

MOTION_COLORS = {
    'STANDING': (0, 200, 0),
    'WALKING': (0, 220, 220),
    'RUNNING': (0, 140, 255),
    'FALLING': (0, 0, 255),
    'SITTING': (255, 180, 0),
    'CROUCHING': (255, 120, 0),
    'UNKNOWN': (180, 180, 180),
}

MOTION_LABELS_TR = {
    'STANDING': 'Duruyor',
    'WALKING': 'Yuruyor',
    'RUNNING': 'Kosuyor',
    'FALLING': 'Dusuyor',
    'SITTING': 'Oturuyor',
    'CROUCHING': 'Egiliyor',
    'UNKNOWN': 'Belirsiz',
}


def draw_tracks(frame: np.ndarray, tracks: list, motion_map: dict | None = None) -> np.ndarray:
    """Track ID'li bounding box'lari hareket etiketiyle cizer."""
    motion_map = motion_map or {}

    for tr in tracks:
        x1, y1, x2, y2 = tr['bbox']
        tid = tr['track_id']
        motion = motion_map.get(tid, {})
        state = motion.get('motion', 'UNKNOWN')
        confirmed = motion.get('motion_confirmed', 'UNKNOWN')
        stable = tr.get('is_stable', True)
        color = MOTION_COLORS.get(confirmed if confirmed != 'UNKNOWN' else state, (255, 165, 0))

        if not stable:
            color = (128, 128, 255)

        label_tr = MOTION_LABELS_TR.get(
            confirmed if confirmed != 'UNKNOWN' else state,
            state,
        )
        label = f"ID:{tid} | {label_tr}"
        if not stable:
            label += " *"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, max(y1 - 8, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.putText(
        frame, f"Takip: {len(tracks)} kisi",
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2
    )
    return frame


def draw_pose(frame: np.ndarray, landmarks: list, bbox: list) -> np.ndarray:
    """Iskelet baglantilarini cizer (COCO 17 nokta)."""
    connections = [
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12), (11, 13), (13, 15),
        (12, 14), (14, 16)
    ]
    for i, j in connections:
        if i >= len(landmarks) or j >= len(landmarks):
            continue
        if landmarks[i]['visibility'] < 0.3 or landmarks[j]['visibility'] < 0.3:
            continue
        pt1 = (int(landmarks[i]['x']), int(landmarks[i]['y']))
        pt2 = (int(landmarks[j]['x']), int(landmarks[j]['y']))
        cv2.line(frame, pt1, pt2, (0, 255, 255), 2)

    for lm in landmarks:
        if lm['visibility'] >= 0.3:
            cv2.circle(frame, (int(lm['x']), int(lm['y'])), 3, (0, 255, 255), -1)
    return frame


def draw_zones(frame: np.ndarray, zones: list) -> np.ndarray:
    """Yasakli/izinli bolge poligonlarini cizer."""
    for polygon in zones:
        pts = np.array(polygon, dtype=np.int32)
        cv2.polylines(frame, [pts], True, (0, 0, 255), 2)
    return frame


def draw_kinematics_debug(
    frame: np.ndarray,
    track_id: int,
    metrics: dict,
    run_threshold: float,
    fall_threshold: float,
    y_offset: int = 55,
) -> np.ndarray:
    """Canli hiz metriklerini ekrana yazar (DEBUG_KINEMATICS=true)."""
    vx = metrics.get('horizontal_velocity', 0)
    vy = metrics.get('vertical_velocity', 0)
    spine = metrics.get('spine_angle', 90)
    samples = metrics.get('sample_count', 0)
    motion = metrics.get('motion', '?')
    confirmed = metrics.get('motion_confirmed', '?')
    lines = [
        f"ID:{track_id} | ornek:{samples} | {motion} -> {confirmed}",
        f"vx:{vx:+.0f} (kosma>={run_threshold:.0f})",
        f"vy:{vy:+.0f} (dusme>={fall_threshold:.0f}) | omurga:{spine:.0f}",
    ]
    for i, line in enumerate(lines):
        cv2.putText(
            frame, line, (10, y_offset + i * 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 255, 180), 2
        )
    return frame


def draw_anomaly_alert(frame: np.ndarray, anomaly: dict) -> np.ndarray:
    """Anomali uyarisini ekrana yazar."""
    motion = anomaly.get('motion', '')
    motion_txt = f" | {motion}" if motion else ''
    text = (
        f"! {anomaly['anomaly_type']} | ID:{anomaly['track_id']} | "
        f"{anomaly['confidence_score']:.2f}{motion_txt}"
    )
    cv2.rectangle(frame, (0, frame.shape[0] - 40), (frame.shape[1], frame.shape[0]), (0, 0, 200), -1)
    cv2.putText(frame, text, (10, frame.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return frame
