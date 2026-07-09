"""
Kayan pencere (sliding window) anomali suzgeci.
Birincil stream islemcisi — Spark olmadan Kafka uzerinde calisir.
"""
import os
import json
import time
from collections import defaultdict, deque
from config import load_env

load_env()

from kafka import KafkaConsumer, KafkaProducer
from core.logging_config import setup_logging

logger = setup_logging('stream_processor', 'stream.log')

WINDOW_SEC = float(os.getenv('SPARK_WINDOW_SEC', 10))
MIN_EVENTS = int(os.getenv('SPARK_MIN_EVENTS', 2))


class SlidingWindowFilter:
    """Ayni track+tip icin pencere icinde tekrarlayan sinyalleri dogrular."""

    def __init__(self):
        self._windows: dict[str, deque] = defaultdict(deque)

    def process(self, event: dict) -> dict | None:
        key = f"{event['camera_id']}_{event['track_id']}_{event['anomaly_type']}"
        now = event.get('timestamp', time.time())
        window = self._windows[key]

        while window and now - window[0] > WINDOW_SEC:
            window.popleft()

        window.append(now)

        if MIN_EVENTS <= 1:
            event['verified'] = True
            event['window_count'] = 1
            event['processor'] = 'sliding_window'
            return event

        if len(window) >= MIN_EVENTS:
            window.clear()
            event['verified'] = True
            event['window_count'] = MIN_EVENTS
            event['processor'] = 'sliding_window'
            return event

        return None


def run_sliding_window_processor():
    bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
    in_topic = os.getenv('KAFKA_ANOMALY_TOPIC', 'anomaly-events')
    out_topic = os.getenv('KAFKA_VERIFIED_TOPIC', 'verified-anomalies')
    filt = SlidingWindowFilter()

    logger.info(
        f"Sliding window basladi | in={in_topic} | out={out_topic} | "
        f"window={WINDOW_SEC}s | min_events={MIN_EVENTS}"
    )

    while True:
        consumer = None
        producer = None
        try:
            consumer = KafkaConsumer(
                in_topic,
                bootstrap_servers=[bootstrap],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='anomaly-window-filter-v2',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=1000,
            )
            producer = KafkaProducer(
                bootstrap_servers=[bootstrap],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8'),
            )
            logger.info("Kafka baglantisi kuruldu")

            for msg in consumer:
                event = msg.value
                verified = filt.process(event)
                if verified:
                    producer.send(out_topic, key=event['camera_id'], value=verified)
                    producer.flush()
                    logger.info(
                        f"Dogrulandi -> {out_topic} | {event['anomaly_type']} | "
                        f"track={event['track_id']} | count={verified.get('window_count')}"
                    )

        except KeyboardInterrupt:
            logger.info("Sliding window durduruldu.")
            break
        except Exception as e:
            logger.error(f"Stream hatasi, 5 sn sonra yeniden denenecek: {e}")
            time.sleep(5)
        finally:
            if consumer:
                consumer.close()
            if producer:
                producer.flush()
                producer.close()


if __name__ == '__main__':
    run_sliding_window_processor()
