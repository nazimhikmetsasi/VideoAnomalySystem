from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    for path in [ROOT / '.env', ROOT / 'VideoAnomalySystem' / '.env']:
        if path.exists():
            load_dotenv(path)
            return
    load_dotenv()
