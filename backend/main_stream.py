import sys

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'python'

    if mode == 'spark':
        from streaming.spark_job import run_spark_streaming
        run_spark_streaming()
    else:
        from streaming.sliding_window import run_sliding_window_processor
        run_sliding_window_processor()
