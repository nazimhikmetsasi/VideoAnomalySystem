import os
import sys
from config import load_env

load_env()


def main():
    mode = os.getenv('STREAM_MODE', 'python').lower().strip()
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower().strip()

    if mode == 'spark':
        from streaming.spark_job import run_spark_streaming
        run_spark_streaming()
    else:
        from streaming.sliding_window import run_sliding_window_processor
        run_sliding_window_processor()


if __name__ == '__main__':
    main()
