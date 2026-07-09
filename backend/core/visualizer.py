import cv2
import numpy as np


def draw_tracks(frame: np.ndarray, tracks: list) -> np.ndarray:
    """Track ID'li bounding box'lari cizer."""
    for tr in tracks:
        x1, y1, x2, y2 = tr['bbox']
        tid = tr['track_id']
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 165, 0), 2)
        label = f"ID:{tid} {tr['confidence']:.2f}"
        cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
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


def draw_anomaly_alert(frame: np.ndarray, anomaly: dict) -> np.ndarray:
    """Anomali uyarisini ekrana yazar."""
    text = f"! {anomaly['anomaly_type']} | ID:{anomaly['track_id']} | {anomaly['confidence_score']:.2f}"
    cv2.rectangle(frame, (0, frame.shape[0] - 40), (frame.shape[1], frame.shape[0]), (0, 0, 200), -1)
    cv2.putText(frame, text, (10, frame.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return frame
