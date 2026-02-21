import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from digital_forensics.config import ORIGINALS_DIR, THUMB_MEDIUM_DIR, THUMB_SMALL_DIR
from digital_forensics.database import Base, SessionLocal, engine
from digital_forensics.main import app
from digital_forensics.models import ImageRecord


@pytest.fixture(scope="session")
def client() -> TestClient:
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_state() -> None:
    for directory in (ORIGINALS_DIR, THUMB_SMALL_DIR, THUMB_MEDIUM_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        for file_path in directory.glob("*"):
            if file_path.is_file():
                file_path.unlink()

    db = SessionLocal()
    try:
        db.execute(delete(ImageRecord))
        db.commit()
    finally:
        db.close()
