from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    for path in [ROOT / '.env', ROOT / 'VideoAnomalySystem' / '.env']:
        if path.exists():
            # override=False: run_video.bat / shell CAMERA_SOURCE ezilmesin
            load_dotenv(path, override=False)
            return
    load_dotenv(override=False)
