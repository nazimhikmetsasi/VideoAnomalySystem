import os
import logging
from dotenv import load_dotenv

load_dotenv()

import cv2
import threading
import json
import base64
import time
from kafka import KafkaProducer

# ---------------------------------------------------------------------------
# LOGGING YAPISINI KONFIGÜRE EDİYORUZ
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = '[%(levelname)s] %(asctime)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOG_DIR, 'pipeline.log'),
            encoding='utf-8'
        )
    ]
)

logger = logging.getLogger('video_pipeline')
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# KAFKA CALLBACK FONKSİYONLARI
# ---------------------------------------------------------------------------
def on_send_success(record_metadata):
    """Mesaj başarıyla gönderildiğinde çağrılır."""
    logger.debug(
        f"Mesaj gönderildi → Topic: {record_metadata.topic} | "
        f"Partition: {record_metadata.partition} | "
        f"Offset: {record_metadata.offset}"
    )

def on_send_error(exception):
    """Mesaj gönderilemediğinde çağrılır."""
    logger.error(f"Kafka'ya mesaj gönderilemedi: {exception}")
# ---------------------------------------------------------------------------


class VideoKafkaProducer:
    def __init__(self, source=None, topic=None):
        # Kamera kaynağını .env'den oku
        camera_source = source if source is not None else os.getenv('CAMERA_SOURCE', 0)
        self.cap = cv2.VideoCapture(int(camera_source))

        self.topic = topic or os.getenv('KAFKA_TOPIC', 'video-stream')

        # Kamera ID'sini .env'den oku — Kafka partition key'i olarak kullanılacak
        self.camera_id = os.getenv('CAMERA_ID', 'cam_01')

        # Frame boyutlarını .env'den oku
        self.frame_width = int(os.getenv('FRAME_WIDTH', 640))
        self.frame_height = int(os.getenv('FRAME_HEIGHT', 480))

        # Kafka'ya bağlanıyoruz
        bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')

        try:
            self.producer = KafkaProducer(
                bootstrap_servers=[bootstrap_servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8'),
                acks='all',
                retries=3,
                retry_backoff_ms=500
            )
            logger.info(
                f"Kafka Producer '{self.topic}' kuyruğu için başlatıldı. "
                f"Sunucu: {bootstrap_servers} | Kamera: {self.camera_id} | acks=all | retries=3"
            )
        except Exception as e:
            logger.error(f"Kafka Producer başlatılamadı: {e}")
            raise

        self.stopped = False

    def start(self):
        logger.debug("Video stream thread'i başlatılıyor...")
        t = threading.Thread(target=self.stream_video, args=())
        t.daemon = True
        t.start()
        logger.info("Video stream thread'i başlatıldı.")
        return self

    def stream_video(self):
        frame_count = 0

        while not self.stopped:
            success, frame = self.cap.read()
            if not success:
                logger.error("Kameradan görüntü okunamadı. Stream durduruluyor.")
                break

            frame_count += 1

            # Görüntüyü boyutlandırıyoruz
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))

            # --- Gece/Düşük Işık Optimizasyonu (CLAHE) ---
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            # ------------------------------------------------

            # Kamerayı ekranda göster
            cv2.imshow("MCBU Kamera Test - CLAHE", frame)
            cv2.waitKey(1)

            # Kareyi Base64'e çeviriyoruz
            _, buffer = cv2.imencode('.jpg', frame)
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')

            # Kafka'ya gönderilecek veri paketi
            message = {
                "camera_id": self.camera_id,   # artık .env'den geliyor
                "timestamp": time.time(),
                "frame_data": jpg_as_text
            }

            # camera_id'yi Kafka partition key'i olarak kullanıyoruz
            self.producer.send(
                self.topic,
                key=self.camera_id,
                value=message
            ) \
            .add_callback(on_send_success) \
            .add_errback(on_send_error)

            # Her 100 karede bir bilgi logu
            if frame_count % 100 == 0:
                logger.debug(f"{frame_count}. kare Kafka'ya gönderildi.")

            # Saniyede ~30 kare
            time.sleep(0.033)

    def stop(self):
        self.stopped = True
        self.cap.release()
        cv2.destroyAllWindows()
        self.producer.flush()
        self.producer.close()
        logger.info("Kafka Producer ve kamera bağlantısı kapatıldı.")