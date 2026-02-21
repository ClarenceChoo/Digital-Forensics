from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db_session
from ..models import ImageRecord
from ..schemas import ImageResponse, StatsResponse
from ..services.image_pipeline import process_image_async, save_original_image, to_response_payload, validate_image_bytes

logger = logging.getLogger("digital_forensics")
job_queue: asyncio.Queue[str] = asyncio.Queue()
worker_task: asyncio.Task | None = None


async def worker_loop() -> None:
    while True:
        image_id = await job_queue.get()
        try:
            await process_image_async(image_id)
        except Exception:
            logger.exception("Processing job failed for image_id=%s", image_id)
        finally:
            job_queue.task_done()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global worker_task
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    Base.metadata.create_all(bind=engine)
    worker_task = asyncio.create_task(worker_loop())
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            worker_task = None


app = FastAPI(
    title="Image Processing Pipeline API",
    version="1.0.0",
    description=(
        "An image processing pipeline that accepts JPG/PNG uploads, "
        "generates thumbnails, extracts metadata and EXIF data, "
        "and produces AI captions using BLIP.\n\n"
        "Interactive docs: **[Swagger UI](/docs)** | **[ReDoc](/redoc)**"
    ),
    lifespan=lifespan,
)
UI_FILE = Path(__file__).resolve().parents[1] / "ui" / "index.html"


@app.get("/", include_in_schema=False)
def serve_ui_root():
    return FileResponse(UI_FILE)


@app.get("/ui", include_in_schema=False)
def serve_ui():
    return FileResponse(UI_FILE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@app.post("/api/images", response_model=ImageResponse, status_code=202,
          summary="Upload an image",
          description="Upload a JPG or PNG image. Returns immediately with a unique ID while processing runs in the background.")
async def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db_session)):
    image_bytes = await file.read()
    try:
        image_format, _, _ = validate_image_bytes(file.filename or "uploaded-image", image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    image_id = f"img{uuid4().hex[:10]}"
    created_at = utc_now()
    original_path = save_original_image(image_id, image_format, image_bytes)

    record = ImageRecord(
        id=image_id,
        original_name=file.filename or "uploaded-image",
        status="processing",
        created_at=created_at,
        original_path=str(original_path),
    )
    db.add(record)
    db.commit()

    job_queue.put_nowait(image_id)

    return JSONResponse(
        status_code=202,
        content={
            "status": "processing",
            "data": {
                "image_id": image_id,
                "original_name": record.original_name,
                "processed_at": created_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "metadata": {},
                "thumbnails": {},
            },
            "error": None,
        },
    )


@app.get("/api/images", response_model=list[ImageResponse],
         summary="List all images",
         description="Returns all images with their processing status, metadata, and thumbnail URLs.")
def list_images(request: Request, db: Session = Depends(get_db_session)):
    records = db.scalars(select(ImageRecord).order_by(ImageRecord.created_at.desc())).all()
    base_url = str(request.base_url)
    return [to_response_payload(record, base_url) for record in records]


@app.get("/api/images/{image_id}", response_model=ImageResponse,
         summary="Get image details",
         description="Get details for a specific image including metadata, EXIF data, caption, and thumbnail URLs.")
def get_image_details(image_id: str, request: Request, db: Session = Depends(get_db_session)):
    record = db.get(ImageRecord, image_id)
    if record is None:
        raise HTTPException(status_code=404, detail="image not found")

    base_url = str(request.base_url)
    return to_response_payload(record, base_url)


@app.get("/api/images/{image_id}/thumbnails/{size}",
         summary="Get thumbnail",
         description="Download the small (128×128) or medium (256×256) thumbnail for an image.",
         responses={200: {"content": {"image/jpeg": {}}}},
         response_class=FileResponse)
def get_thumbnail(image_id: str, size: str, db: Session = Depends(get_db_session)):
    if size not in {"small", "medium"}:
        raise HTTPException(status_code=400, detail="thumbnail size must be small or medium")

    record = db.get(ImageRecord, image_id)
    if record is None:
        raise HTTPException(status_code=404, detail="image not found")

    thumbnail_path = record.small_thumbnail_path if size == "small" else record.medium_thumbnail_path
    if not thumbnail_path:
        raise HTTPException(status_code=404, detail="thumbnail not found")

    return FileResponse(thumbnail_path, media_type="image/jpeg")


@app.get("/api/stats", response_model=StatsResponse,
         summary="Processing statistics",
         description="Returns total images, failure count, success rate, and average processing time.")
def get_stats(db: Session = Depends(get_db_session)):
    total = db.scalar(select(func.count(ImageRecord.id))) or 0
    failed = db.scalar(select(func.count(ImageRecord.id)).where(ImageRecord.status == "failed")) or 0
    success = db.scalar(select(func.count(ImageRecord.id)).where(ImageRecord.status == "success")) or 0
    avg_processing = (
        db.scalar(
            select(func.avg(ImageRecord.processing_duration_seconds)).where(
                ImageRecord.status == "success",
                ImageRecord.processing_duration_seconds.is_not(None),
            )
        )
        or 0.0
    )

    success_rate = f"{((success / total) * 100) if total else 0:.2f}%"
    return {
        "total": total,
        "failed": failed,
        "success_rate": success_rate,
        "average_processing_time_seconds": round(float(avg_processing), 2),
    }


def run() -> None:
    import uvicorn

    uvicorn.run("digital_forensics.api.app:app", host="0.0.0.0", port=8000, reload=False)
