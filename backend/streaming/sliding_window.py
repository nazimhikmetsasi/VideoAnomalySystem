"""
Kayan pencere (sliding window) anomali süzgeci.
Spark ortaminda calistirilmadiginda yerel Python fallback olarak kullanilir.
"""
import os
import json
import logging
import time
from collections import defaultdict, deque
from config import load_env
load_env()

from kafka import KafkaConsumer, KafkaProducer

logger = logging.getLogger('spark_processor')

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
            return event

        if len(window) >= MIN_EVENTS:
            window.clear()
            event['verified'] = True
            event['window_count'] = MIN_EVENTS
            return event

        return None


def run_sliding_window_processor():
    bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
    in_topic = os.getenv('KAFKA_ANOMALY_TOPIC', 'anomaly-events')
    out_topic = os.getenv('KAFKA_VERIFIED_TOPIC', 'verified-anomalies')

    consumer = KafkaConsumer(
        in_topic,
        bootstrap_servers=[bootstrap],
        auto_offset_reset='latest',
        enable_auto_commit=True,
        group_id='anomaly-window-filter',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    producer = KafkaProducer(
        bootstrap_servers=[bootstrap],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8')
    )

    filt = SlidingWindowFilter()
    logger.info(f"Sliding window processor basladi | in={in_topic} | out={out_topic}")

    for msg in consumer:
        event = msg.value
        verified = filt.process(event)
        if verified:
            producer.send(out_topic, key=event['camera_id'], value=verified)
            producer.flush()
            logger.info(
                f"Dogrulanmis anomali -> {out_topic} | "
                f"{event['anomaly_type']} | track={event['track_id']}"
            )


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    run_sliding_window_processor()
