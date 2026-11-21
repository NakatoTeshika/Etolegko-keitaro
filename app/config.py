import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

KEITARO_BASE_URL = os.getenv("KEITARO_BASE_URL", "").strip().rstrip("/")
KEITARO_API_KEY = os.getenv("KEITARO_API_KEY", "").strip()