import time
from core.pipeline import VideoKafkaProducer

if __name__ == '__main__':
    pipeline = VideoKafkaProducer().start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pipeline.stop()
