import os
import logging
from datetime import datetime
from pymongo import MongoClient

logger = logging.getLogger('video_pipeline')


class MongoRepository:
    def __init__(self):
        host = os.getenv('MONGO_HOST', 'localhost')
        port = int(os.getenv('MONGO_PORT', 27017))
        db_name = os.getenv('MONGO_DB', 'anomaly_metrics')

        self.client = MongoClient(host, port, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self.collection = self.db['raw_metrics']
        logger.info(f"MongoDB baglandi | {host}:{port}/{db_name}")

    def save_raw_metrics(self, event: dict, postgres_id: int | None = None):
        doc = {
            'postgres_id': postgres_id,
            'camera_id': event['camera_id'],
            'track_id': event['track_id'],
            'anomaly_type': event['anomaly_type'],
            'confidence_score': event['confidence_score'],
            'metrics': event.get('metrics', {}),
            'hip_center': event.get('hip_center', {}),
            'landmarks': event.get('landmarks', []),
            'timestamp': datetime.fromtimestamp(event.get('timestamp', datetime.utcnow().timestamp()))
        }
        result = self.collection.insert_one(doc)
        logger.info(f"MongoDB ham metrik kaydi | _id={result.inserted_id}")
        return str(result.inserted_id)
