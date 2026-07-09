import time
from config import load_env

load_env()

from core.pipeline import VideoKafkaProducer

if __name__ == '__main__':
    # Kafka olmadan yerel kamera + AI testi (Docker gerekmez)
    pipeline = VideoKafkaProducer(source=0, kafka_enabled=False).start()
    print("Kamera testi basladi. Durdurmak icin Ctrl+C")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pipeline.stop()
