"""Pydantic response models for typed API documentation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    """Metadata extracted from a processed image."""

    width: int | None = Field(None, description="Image width in pixels", examples=[1920])
    height: int | None = Field(None, description="Image height in pixels", examples=[1080])
    format: str | None = Field(None, description="Image format (jpg, png)", examples=["jpg"])
    size_bytes: int | None = Field(None, description="File size in bytes", examples=[2048576])
    file_datetime: str | None = Field(None, description="File modification datetime (UTC ISO-8601)", examples=["2026-02-21T10:00:00Z"])
    caption: str | None = Field(None, description="AI-generated image caption", examples=["a person standing in front of a building"])
    exif: dict | None = Field(None, description="EXIF metadata (camera info, GPS, etc.) if present")


class ImageThumbnails(BaseModel):
    """URLs for generated thumbnails."""

    small: str | None = Field(None, description="URL for small thumbnail (128×128)", examples=["http://localhost:8000/api/images/img123/thumbnails/small"])
    medium: str | None = Field(None, description="URL for medium thumbnail (256×256)", examples=["http://localhost:8000/api/images/img123/thumbnails/medium"])


class ImageData(BaseModel):
    """Core image data payload."""

    image_id: str = Field(..., description="Unique image identifier", examples=["img123"])
    original_name: str = Field(..., description="Original uploaded filename", examples=["photo.jpg"])
    processed_at: str | None = Field(None, description="Processing completion time (UTC ISO-8601)", examples=["2026-02-21T10:00:00Z"])
    metadata: ImageMetadata | dict = Field(default_factory=dict, description="Image metadata")
    thumbnails: ImageThumbnails | dict = Field(default_factory=dict, description="Thumbnail URLs")


class ImageResponse(BaseModel):
    """Response for a single image."""

    status: str = Field(..., description="Processing status: processing, success, or failed", examples=["success"])
    data: ImageData
    error: str | None = Field(None, description="Error message if processing failed")

    model_config = {"json_schema_extra": {
        "examples": [{
            "status": "success",
            "data": {
                "image_id": "img123",
                "original_name": "photo.jpg",
                "processed_at": "2026-02-21T10:00:00Z",
                "metadata": {
                    "width": 1920,
                    "height": 1080,
                    "format": "jpg",
                    "size_bytes": 2048576,
                    "file_datetime": "2026-02-21T09:59:55Z",
                    "caption": "a person standing in front of a building",
                },
                "thumbnails": {
                    "small": "http://localhost:8000/api/images/img123/thumbnails/small",
                    "medium": "http://localhost:8000/api/images/img123/thumbnails/medium",
                },
            },
            "error": None,
        }]
    }}


class StatsResponse(BaseModel):
    """Processing statistics."""

    total: int = Field(..., description="Total number of images processed", examples=[3])
    failed: int = Field(..., description="Number of failed processing jobs", examples=[1])
    success_rate: str = Field(..., description="Percentage of successful jobs", examples=["66.67%"])
    average_processing_time_seconds: float = Field(..., description="Mean processing time in seconds", examples=[0.42])
