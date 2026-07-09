"""
Apache Spark Structured Streaming ile Kafka anomali akisi isleme.
Opsiyonel — varsayilan islemci sliding_window.py (STREAM_MODE=python).
"""
import os
from config import load_env

load_env()

from core.logging_config import setup_logging

logger = setup_logging('spark_processor', 'spark.log')

KAFKA_PACKAGE = os.getenv(
    'SPARK_KAFKA_PACKAGE',
    'org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0',
)


def run_spark_streaming():
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, window, count, first

    bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
    in_topic = os.getenv('KAFKA_ANOMALY_TOPIC', 'anomaly-events')
    out_topic = os.getenv('KAFKA_VERIFIED_TOPIC', 'verified-anomalies')
    window_sec = os.getenv('SPARK_WINDOW_SEC', '10 seconds')
    min_events = int(os.getenv('SPARK_MIN_EVENTS', 2))
    checkpoint = os.getenv(
        'SPARK_CHECKPOINT',
        os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'spark_checkpoint')),
    )
    master = os.getenv('SPARK_MASTER', 'local[*]')

    os.makedirs(checkpoint, exist_ok=True)

    spark = (
        SparkSession.builder
        .appName('MCBU-AnomalyStreaming')
        .master(master)
        .config('spark.sql.shuffle.partitions', '4')
        .config('spark.jars.packages', KAFKA_PACKAGE)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel('WARN')

    schema = (
        'camera_id STRING, track_id INT, anomaly_type STRING, '
        'confidence_score DOUBLE, timestamp DOUBLE'
    )

    raw = (
        spark.readStream
        .format('kafka')
        .option('kafka.bootstrap.servers', bootstrap)
        .option('subscribe', in_topic)
        .option('startingOffsets', 'latest')
        .load()
    )

    events = (
        raw.selectExpr('CAST(value AS STRING) as json')
        .selectExpr(f'from_json(json, "{schema}") as data')
        .select('data.*')
        .withColumn('event_time', col('timestamp').cast('timestamp'))
    )

    verified = (
        events
        .withWatermark('event_time', '5 seconds')
        .groupBy(
            window(col('event_time'), window_sec, window_sec),
            col('camera_id'), col('track_id'), col('anomaly_type'),
        )
        .agg(
            count('*').alias('event_count'),
            first('confidence_score').alias('confidence_score'),
            first('timestamp').alias('timestamp'),
        )
        .filter(col('event_count') >= min_events)
    )

    query = (
        verified.selectExpr(
            'camera_id as key',
            '''to_json(named_struct(
                'camera_id', camera_id,
                'track_id', track_id,
                'anomaly_type', anomaly_type,
                'confidence_score', confidence_score,
                'timestamp', timestamp,
                'event_count', event_count,
                'verified', true,
                'processor', 'spark'
            )) as value''',
        )
        .writeStream
        .format('kafka')
        .option('kafka.bootstrap.servers', bootstrap)
        .option('topic', out_topic)
        .option('checkpointLocation', checkpoint)
        .outputMode('append')
        .start()
    )

    logger.info(
        f"Spark streaming basladi | {in_topic} -> {out_topic} | "
        f"min_events={min_events} | checkpoint={checkpoint}"
    )

    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        logger.info("Spark streaming durduruluyor...")
        query.stop()
        spark.stop()


if __name__ == '__main__':
    run_spark_streaming()
