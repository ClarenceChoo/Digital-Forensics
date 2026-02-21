from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from sqlalchemy.orm import Session

from ..config import MEDIUM_SIZE, ORIGINALS_DIR, SMALL_SIZE, SUPPORTED_FORMATS, THUMB_MEDIUM_DIR, THUMB_SMALL_DIR
from ..database import SessionLocal
from ..models import ImageRecord
from .captioning import caption_service

logger = logging.getLogger("digital_forensics.pipeline")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_storage_dirs() -> None:
    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_SMALL_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_MEDIUM_DIR.mkdir(parents=True, exist_ok=True)


def validate_image_bytes(file_name: str, image_bytes: bytes) -> tuple[str, int, int]:
    if not image_bytes:
        raise ValueError("empty file")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = (image.format or "").lower()
            if image_format not in SUPPORTED_FORMATS:
                raise ValueError("invalid file format")
            width, height = image.size
            return image_format, width, height
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("invalid image file") from exc


def save_original_image(image_id: str, image_format: str, image_bytes: bytes) -> Path:
    _ensure_storage_dirs()
    extension = SUPPORTED_FORMATS[image_format]
    output_path = ORIGINALS_DIR / f"{image_id}.{extension}"
    output_path.write_bytes(image_bytes)
    return output_path


def _extract_exif(image: Image.Image) -> dict:
    """Extract EXIF metadata from an image, returning a JSON-serialisable dict."""
    exif_data = {}
    raw_exif = image.getexif()
    if not raw_exif:
        return exif_data

    for tag_id, value in raw_exif.items():
        tag_name = TAGS.get(tag_id, str(tag_id))
        # Skip binary / large blobs
        if isinstance(value, bytes):
            continue
        try:
            exif_data[tag_name] = str(value) if not isinstance(value, (int, float, str)) else value
        except Exception:
            continue

    # Try to extract GPS info if present
    gps_ifd = raw_exif.get_ifd(0x8825)
    if gps_ifd:
        gps_info = {}
        for tag_id, value in gps_ifd.items():
            tag_name = GPSTAGS.get(tag_id, str(tag_id))
            if isinstance(value, bytes):
                continue
            try:
                gps_info[tag_name] = str(value) if not isinstance(value, (int, float, str)) else value
            except Exception:
                continue
        if gps_info:
            exif_data["GPSInfo"] = gps_info

    return exif_data


def _create_thumbnail(source: Path, destination: Path, size: tuple[int, int]) -> None:
    with Image.open(source) as image:
        output = image if image.mode == "RGB" else image.convert("RGB")
        output.thumbnail(size)
        output.save(destination, format="JPEG", quality=90)


def _process_image_sync(image_id: str) -> None:
    db: Session = SessionLocal()
    started_at = now_utc()
    logger.info("Processing started for image_id=%s", image_id)
    try:
        record = db.get(ImageRecord, image_id)
        if record is None:
            logger.warning("Image not found for processing image_id=%s", image_id)
            return

        record.status = "processing"
        db.commit()

        source_path = Path(record.original_path)
        if not source_path.exists():
            raise FileNotFoundError("original image file not found")

        with Image.open(source_path) as image:
            image_format = (image.format or "").lower()
            if image_format not in SUPPORTED_FORMATS:
                raise ValueError("invalid file format")
            width, height = image.size
            exif_data = _extract_exif(image)

        size_bytes = source_path.stat().st_size
        file_datetime = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc)

        small_path = THUMB_SMALL_DIR / f"{record.id}.jpg"
        medium_path = THUMB_MEDIUM_DIR / f"{record.id}.jpg"
        _create_thumbnail(source_path, small_path, SMALL_SIZE)
        _create_thumbnail(source_path, medium_path, MEDIUM_SIZE)

        caption = caption_service.generate_caption(source_path, image_format, width, height)

        finished_at = now_utc()
        record.status = "success"
        record.width = width
        record.height = height
        record.format = SUPPORTED_FORMATS[image_format]
        record.size_bytes = size_bytes
        record.file_datetime = file_datetime
        record.caption = caption
        record.exif_data = exif_data if exif_data else None
        record.small_thumbnail_path = str(small_path)
        record.medium_thumbnail_path = str(medium_path)
        record.error = None
        record.processed_at = finished_at
        record.processing_duration_seconds = (finished_at - started_at).total_seconds()
        db.commit()
        logger.info("Processing succeeded for image_id=%s", image_id)
    except Exception as exc:
        failed_at = now_utc()
        record = db.get(ImageRecord, image_id)
        if record is not None:
            record.status = "failed"
            record.error = str(exc)
            record.processed_at = failed_at
            record.processing_duration_seconds = (failed_at - started_at).total_seconds()
            db.commit()
        logger.exception("Processing failed for image_id=%s", image_id)
    finally:
        db.close()


async def process_image_async(image_id: str) -> None:
    await asyncio.to_thread(_process_image_sync, image_id)


def to_response_payload(record: ImageRecord, base_url: str) -> dict:
    metadata = {}
    thumbnails = {}

    if record.status == "success":
        metadata = {
            "width": record.width,
            "height": record.height,
            "format": record.format,
            "size_bytes": record.size_bytes,
            "file_datetime": iso_utc(record.file_datetime),
            "caption": record.caption,
        }
        if record.exif_data:
            metadata["exif"] = record.exif_data
        thumbnails = {
            "small": f"{base_url}api/images/{record.id}/thumbnails/small",
            "medium": f"{base_url}api/images/{record.id}/thumbnails/medium",
        }

    processed_time = record.processed_at or record.created_at

    return {
        "status": record.status,
        "data": {
            "image_id": record.id,
            "original_name": record.original_name,
            "processed_at": iso_utc(processed_time),
            "metadata": metadata,
            "thumbnails": thumbnails,
        },
        "error": record.error,
    }
