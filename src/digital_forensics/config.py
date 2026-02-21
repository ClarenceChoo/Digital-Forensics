from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
ORIGINALS_DIR = STORAGE_DIR / "originals"
THUMB_SMALL_DIR = STORAGE_DIR / "thumbnails" / "small"
THUMB_MEDIUM_DIR = STORAGE_DIR / "thumbnails" / "medium"
DB_PATH = BASE_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

SMALL_SIZE = (128, 128)
MEDIUM_SIZE = (256, 256)
SUPPORTED_FORMATS = {"jpeg": "jpg", "png": "png"}
