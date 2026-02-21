import time
from io import BytesIO

import pytest
from PIL import Image


def create_image_bytes(image_format: str) -> bytes:
    image = Image.new("RGB", (640, 480), color=(20, 120, 220))
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def create_rgba_png_bytes() -> bytes:
    image = Image.new("RGBA", (320, 240), color=(20, 120, 220, 128))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def wait_for_completion(client, image_id: str, timeout_seconds: float = 6.0) -> dict:
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        response = client.get(f"/api/images/{image_id}")
        payload = response.json()
        if payload["status"] in {"success", "failed"}:
            return payload
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for image processing")


def test_ui_route_available(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Image Pipeline API Tester" in response.text


def test_upload_process_and_fetch_thumbnail(client) -> None:
    response = client.post(
        "/api/images",
        files={"file": ("photo.jpg", create_image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "processing"

    image_id = payload["data"]["image_id"]
    final_payload = wait_for_completion(client, image_id)

    assert final_payload["status"] == "success"
    assert final_payload["data"]["metadata"]["format"] == "jpg"
    assert final_payload["data"]["metadata"]["width"] == 640
    assert final_payload["data"]["metadata"]["height"] == 480
    assert "small" in final_payload["data"]["thumbnails"]
    assert "medium" in final_payload["data"]["thumbnails"]

    thumb_response = client.get(f"/api/images/{image_id}/thumbnails/small")
    assert thumb_response.status_code == 200
    assert thumb_response.headers["content-type"] == "image/jpeg"


def test_reject_unsupported_format(client) -> None:
    response = client.post(
        "/api/images",
        files={"file": ("anim.gif", create_image_bytes("GIF"), "image/gif")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid file format"


def test_stats_and_list(client) -> None:
    response = client.post(
        "/api/images",
        files={"file": ("photo.png", create_image_bytes("PNG"), "image/png")},
    )
    image_id = response.json()["data"]["image_id"]
    wait_for_completion(client, image_id)

    list_response = client.get("/api/images")
    assert list_response.status_code == 200
    records = list_response.json()
    assert len(records) == 1
    assert records[0]["data"]["image_id"] == image_id

    stats_response = client.get("/api/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["total"] == 1
    assert stats["failed"] == 0
    assert stats["success_rate"] == "100.00%"
    assert isinstance(stats["average_processing_time_seconds"], float)


def test_upload_png_with_alpha_channel(client) -> None:
    response = client.post(
        "/api/images",
        files={"file": ("alpha.png", create_rgba_png_bytes(), "image/png")},
    )

    assert response.status_code == 202
    image_id = response.json()["data"]["image_id"]
    final_payload = wait_for_completion(client, image_id)

    assert final_payload["status"] == "success"

    thumb_response = client.get(f"/api/images/{image_id}/thumbnails/medium")
    assert thumb_response.status_code == 200
    assert thumb_response.headers["content-type"] == "image/jpeg"


def create_jpeg_with_exif() -> bytes:
    """Create a JPEG with EXIF metadata embedded."""
    import piexif

    image = Image.new("RGB", (800, 600), color=(50, 200, 100))
    buffer = BytesIO()

    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"TestCamera",
            piexif.ImageIFD.Model: b"Model X",
            piexif.ImageIFD.Software: b"TestSuite 1.0",
        }
    }
    exif_bytes = piexif.dump(exif_dict)
    image.save(buffer, format="JPEG", exif=exif_bytes)
    return buffer.getvalue()


def test_exif_data_extracted(client) -> None:
    try:
        import piexif  # noqa: F401
    except ImportError:
        pytest.skip("piexif not installed")

    response = client.post(
        "/api/images",
        files={"file": ("exif.jpg", create_jpeg_with_exif(), "image/jpeg")},
    )

    assert response.status_code == 202
    image_id = response.json()["data"]["image_id"]
    final_payload = wait_for_completion(client, image_id)

    assert final_payload["status"] == "success"
    metadata = final_payload["data"]["metadata"]
    assert "exif" in metadata, "EXIF data should be present in metadata"
    assert metadata["exif"]["Make"] == "TestCamera"
    assert metadata["exif"]["Model"] == "Model X"
