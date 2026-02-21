import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class _JSONText(Text):
    """Stores a Python dict/list as a JSON-encoded TEXT column."""


class ImageRecord(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    _exif_json: Mapped[str | None] = mapped_column("exif_data", Text, nullable=True)

    @property
    def exif_data(self) -> dict[str, Any] | None:
        if self._exif_json is None:
            return None
        try:
            return json.loads(self._exif_json)
        except (json.JSONDecodeError, TypeError):
            return None

    @exif_data.setter
    def exif_data(self, value: dict[str, Any] | None) -> None:
        if value is None:
            self._exif_json = None
        else:
            self._exif_json = json.dumps(value)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    small_thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    medium_thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
