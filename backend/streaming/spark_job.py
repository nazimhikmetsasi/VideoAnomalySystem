"""
Apache Spark Structured Streaming ile Kafka anomali akisi isleme.
Docker spark servisi veya yerel pyspark ile calistirilir.
"""
import os
import logging
from config import load_env
load_env()

logger = logging.getLogger('spark_processor')


def run_spark_streaming():
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, window, count, first
    from pyspark.sql.types import (
        StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
    )

    bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
    in_topic = os.getenv('KAFKA_ANOMALY_TOPIC', 'anomaly-events')
    out_topic = os.getenv('KAFKA_VERIFIED_TOPIC', 'verified-anomalies')
    window_sec = os.getenv('SPARK_WINDOW_SEC', '10 seconds')

    spark = (
        SparkSession.builder
        .appName('AnomalyStreaming')
        .master(os.getenv('SPARK_MASTER', 'local[*]'))
        .config('spark.sql.shuffle.partitions', '4')
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel('WARN')

    schema = StructType([
        StructField('camera_id', StringType()),
        StructField('track_id', IntegerType()),
        StructField('anomaly_type', StringType()),
        StructField('confidence_score', DoubleType()),
        StructField('timestamp', DoubleType()),
    ])

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
        .selectExpr('from_json(json, schema) as data')
        .select('data.*')
        .withColumn('event_time', (col('timestamp').cast('timestamp')))
    )

    verified = (
        events
        .withWatermark('event_time', '5 seconds')
        .groupBy(
            window(col('event_time'), window_sec, window_sec),
            col('camera_id'), col('track_id'), col('anomaly_type')
        )
        .agg(
            count('*').alias('event_count'),
            first('confidence_score').alias('confidence_score'),
            first('timestamp').alias('timestamp')
        )
        .filter(col('event_count') >= 2)
    )

    query = (
        verified.selectExpr(
            'camera_id as key',
            'to_json(struct(camera_id, track_id, anomaly_type, confidence_score, timestamp, event_count)) as value'
        )
        .writeStream
        .format('kafka')
        .option('kafka.bootstrap.servers', bootstrap)
        .option('topic', out_topic)
        .option('checkpointLocation', '/tmp/anomaly-checkpoint')
        .outputMode('append')
        .start()
    )

    logger.info(f"Spark streaming basladi | {in_topic} -> {out_topic}")
    query.awaitTermination()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    run_spark_streaming()
