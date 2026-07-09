import os
from datetime import datetime
from sqlalchemy import create_engine, Column, BigInteger, String, Integer, Float, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://mcbu_user:anomaly_password@localhost:5432/anomaly_db'
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class AnomalyRecord(Base):
    __tablename__ = 'anomalies'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    camera_id = Column(String(50), nullable=False)
    detected_person_id = Column(Integer, nullable=False)
    anomaly_type = Column(String(50), nullable=False)
    confidence_score = Column(Float, nullable=False)
    ai_generated_report = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()
