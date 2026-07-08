import os
import logging
from ultralytics import YOLO
import cv2
import numpy as np

logger = logging.getLogger('video_pipeline')

class HumanDetector:
    def __init__(self):
        # Model ağırlıklarını .env'den oku, yoksa varsayılan yolo8n kullan
        model_path = os.getenv('YOLO_MODEL_PATH', 'yolov8n.pt')
        
        # Güven eşiği ve IOU eşiği .env'den oku
        self.conf_threshold = float(os.getenv('YOLO_CONF_THRESHOLD', 0.25))
        self.iou_threshold = float(os.getenv('YOLO_IOU_THRESHOLD', 0.45))

        # GPU varsa cuda, yoksa cpu kullan
        self.device = 'cuda' if os.getenv('USE_GPU', 'true').lower() == 'true' else 'cpu'

        logger.info(f"YOLOv8 modeli yükleniyor: {model_path} | Device: {self.device}")
        self.model = YOLO(model_path)
        self.model.to(self.device)
        logger.info(f"YOLOv8 modeli yüklendi. conf={self.conf_threshold} | iou={self.iou_threshold}")

    def detect(self, frame: np.ndarray) -> list:
        """
        Verilen karede insan tespiti yapar.
        
        Args:
            frame: OpenCV BGR formatında numpy array
            
        Returns:
            list: Tespit edilen her insan için sözlük listesi
                  [{"bbox": [x1,y1,x2,y2], "confidence": 0.95, "class": "person"}, ...]
        """
        results = self.model(
            frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            classes=[0],        # Sadece insan sınıfı (class 0 = person)
            verbose=False       # Gereksiz ultralytics loglarını kapat
        )

        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(confidence, 3),
                    "class": "person"
                })

        if detections:
            logger.debug(f"{len(detections)} kişi tespit edildi.")

        return detections

    def draw_detections(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """
        Tespit edilen kişileri kare üzerine çizer.
        
        Args:
            frame: Orijinal kare
            detections: detect() metodundan dönen liste
            
        Returns:
            np.ndarray: Bounding box'lar çizilmiş kare
        """
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = det["confidence"]

            # Bounding box çiz
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Güven skoru etiketi
            label = f"person {conf:.2f}"
            cv2.putText(
                frame, label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (0, 255, 0), 2
            )

        # Toplam kişi sayısını sol üste yaz
        count_label = f"Kisi Sayisi: {len(detections)}"
        cv2.putText(
            frame, count_label,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1, (0, 0, 255), 2
        )

        return frame