import logging
from datetime import datetime
from database.models import get_session, AnomalyRecord, init_db

logger = logging.getLogger('video_pipeline')


class PostgresRepository:
    def __init__(self):
        init_db()

    def save_anomaly(self, event: dict, report: str | None = None) -> int:
        session = get_session()
        try:
            record = AnomalyRecord(
                camera_id=event['camera_id'],
                detected_person_id=event['track_id'],
                anomaly_type=event['anomaly_type'],
                confidence_score=event['confidence_score'],
                ai_generated_report=report,
                timestamp=datetime.fromtimestamp(event.get('timestamp', datetime.utcnow().timestamp()))
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            logger.info(f"PostgreSQL kayit | id={record.id} | type={record.anomaly_type}")
            return record.id
        except Exception as e:
            session.rollback()
            logger.error(f"PostgreSQL kayit hatasi: {e}")
            raise
        finally:
            session.close()

    def list_recent(self, limit: int = 50) -> list:
        session = get_session()
        try:
            rows = session.query(AnomalyRecord).order_by(AnomalyRecord.timestamp.desc()).limit(limit).all()
            return [
                {
                    'id': r.id,
                    'camera_id': r.camera_id,
                    'track_id': r.detected_person_id,
                    'anomaly_type': r.anomaly_type,
                    'confidence_score': r.confidence_score,
                    'ai_generated_report': r.ai_generated_report,
                    'timestamp': r.timestamp.isoformat()
                }
                for r in rows
            ]
        finally:
            session.close()
