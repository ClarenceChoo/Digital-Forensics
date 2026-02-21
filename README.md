# Digital Forensics Internship — Take Home Assessment

## Project Overview

An image processing pipeline API that accepts JPG/PNG uploads, processes them asynchronously, and exposes results through RESTful endpoints.

**Features:**

- Upload images and get a unique ID back immediately (non-blocking)
- Async job queue processes images in the background
- Generates two thumbnail sizes (small 128×128, medium 256×256)
- Extracts metadata: dimensions, format, file size, file datetime
- Extracts EXIF data when present (camera make/model, GPS, exposure, etc.)
- AI-powered image captioning using [BLIP](https://huggingface.co/Salesforce/blip-image-captioning-base)
- Persistent storage in SQLite
- Built-in browser UI for testing all endpoints

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Framework | FastAPI |
| Database | SQLAlchemy + SQLite |
| Image Processing | Pillow |
| AI Captioning | Transformers + PyTorch (BLIP) |
| Testing | pytest |

---

## Quick Start

```bash
# 1. Clone the repo and cd into it
cd Digital\ Forensics

# 2. Create a virtual environment and activate it
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the project and all dependencies (core + test + AI)
pip install -e '.[dev,ai]'

# 4. Start the server
python3 -m uvicorn digital_forensics.api.app:app --host 127.0.0.1 --port 8000 --reload

# 5. Open the browser UI
open http://127.0.0.1:8000/
```

> **Tip:** If port 8000 is already in use, free it first:
> ```bash
> lsof -ti:8000 | xargs kill -9
> ```

---

## Installation (Detailed)

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

### 2. Install the project

Core dependencies only (no AI captioning):

```bash
pip install -e .
```

With test dependencies:

```bash
pip install -e '.[dev]'
```

With AI captioning (BLIP model — recommended for full functionality):

```bash
pip install -e '.[ai]'
```

All dependencies at once:

```bash
pip install -e '.[dev,ai]'
```

> **Note:** The AI model (~990 MB) downloads automatically on first image upload. To speed this up, you can set:
> ```bash
> export CAPTION_MODELS="Salesforce/blip-image-captioning-base"
> ```

---

## How to Run the Server

### Start the backend

```bash
source .venv/bin/activate
python3 -m uvicorn digital_forensics.api.app:app --host 127.0.0.1 --port 8000 --reload
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### Open the browser UI

Navigate to **http://127.0.0.1:8000/** in your browser. The UI lets you:

- Upload images (drag & drop or file picker)
- Query image details by ID
- View thumbnails
- List all images
- View processing stats

### Interactive API Documentation

FastAPI auto-generates interactive docs from the Pydantic response models:

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000/docs | Swagger UI — try out every endpoint from the browser |
| http://127.0.0.1:8000/redoc | ReDoc — alternative read-only documentation |

### Alternative run commands

```bash
# Without --reload
uvicorn digital_forensics.api.app:app --host 0.0.0.0 --port 8000

# Using the installed entrypoint
forensics-api
```

---

## How to Test

### 1. Run the automated test suite

```bash
source .venv/bin/activate
python3 -m pytest
```

Expected output:

```
.......                                                            [100%]
7 passed
```

**Tests cover:**

| Test | What it verifies |
|------|-----------------|
| `test_upload_process_and_fetch_thumbnail` | Full upload → async processing → thumbnail retrieval |
| `test_reject_unsupported_format` | Returns 400 for non JPG/PNG files (e.g. GIF) |
| `test_stats_and_list` | `/api/stats` and `/api/images` return correct data |
| `test_ui_route_available` | Browser UI served at `/` |
| `test_upload_png_with_alpha_channel` | RGBA PNGs don't crash thumbnail generation |
| `test_exif_data_extracted` | EXIF metadata appears in response when present |

### 2. Run the end-to-end demo script

This script starts the server, uploads an image, hits every endpoint, and prints the output:

```bash
chmod +x scripts/demo.sh
./scripts/demo.sh
```

### 3. Manual testing with curl

Start the server first (see above), then in a separate terminal:

**Upload an image:**

```bash
curl -X POST http://127.0.0.1:8000/api/images \
  -F "file=@/path/to/your/photo.jpg"
```

Response (immediate, 202 Accepted):

```json
{
  "status": "processing",
  "data": {
    "image_id": "img865bd3d460",
    "original_name": "photo.jpg",
    "processed_at": "2026-02-21T12:59:31Z",
    "metadata": {},
    "thumbnails": {}
  },
  "error": null
}
```

**Check image details** (use the `image_id` from above):

```bash
curl http://127.0.0.1:8000/api/images/img865bd3d460
```

Response (after processing completes):

```json
{
  "status": "success",
  "data": {
    "image_id": "img865bd3d460",
    "original_name": "photo.jpg",
    "processed_at": "2026-02-21T12:59:40Z",
    "metadata": {
      "width": 400,
      "height": 300,
      "format": "jpg",
      "size_bytes": 5003,
      "file_datetime": "2026-02-21T04:59:31Z",
      "caption": "a blue background with a red circle and green squares",
      "exif": {
        "Make": "Canon",
        "Model": "EOS R5"
      }
    },
    "thumbnails": {
      "small": "http://127.0.0.1:8000/api/images/img865bd3d460/thumbnails/small",
      "medium": "http://127.0.0.1:8000/api/images/img865bd3d460/thumbnails/medium"
    }
  },
  "error": null
}
```

> **Note:** The `exif` field only appears when the image contains EXIF data. The `caption` field uses AI when the `[ai]` dependencies are installed, otherwise falls back to a descriptive caption based on image properties.

**Download a thumbnail:**

```bash
curl -o thumb_small.jpg http://127.0.0.1:8000/api/images/img865bd3d460/thumbnails/small
curl -o thumb_medium.jpg http://127.0.0.1:8000/api/images/img865bd3d460/thumbnails/medium
```

**List all images:**

```bash
curl http://127.0.0.1:8000/api/images
```

**View processing stats:**

```bash
curl http://127.0.0.1:8000/api/stats
```

Response:

```json
{
  "total": 3,
  "failed": 1,
  "success_rate": "66.67%",
  "average_processing_time_seconds": 0.42
}
```

---

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/images` | Upload a JPG/PNG image. Returns 202 with `image_id`. |
| `GET` | `/api/images` | List all images with status, metadata, and thumbnails. |
| `GET` | `/api/images/{id}` | Get details for a specific image. |
| `GET` | `/api/images/{id}/thumbnails/small` | Download the small thumbnail (128×128). |
| `GET` | `/api/images/{id}/thumbnails/medium` | Download the medium thumbnail (256×256). |
| `GET` | `/api/stats` | Processing statistics (total, failed, success rate, avg time). |

---

## Processing Pipeline Explanation

```
Client                           Server
  │                                │
  │  POST /api/images (file)       │
  │ ─────────────────────────────► │
  │                                │── Validate image (JPG/PNG only)
  │                                │── Save original file to storage/originals/
  │                                │── Create DB record (status: processing)
  │  202 { image_id: "img..." }    │── Enqueue job to async worker
  │ ◄───────────────────────────── │
  │                                │
  │                                │   ┌─── Background Worker ───┐
  │                                │   │ Extract metadata        │
  │                                │   │ Extract EXIF data       │
  │                                │   │ Generate thumbnails     │
  │                                │   │ Generate AI caption     │
  │                                │   │ Update DB (success/fail)│
  │                                │   └─────────────────────────┘
  │                                │
  │  GET /api/images/{id}          │
  │ ─────────────────────────────► │
  │  200 { status: "success", ...} │
  │ ◄───────────────────────────── │
```

1. Client uploads image via `POST /api/images`
2. API validates the file is a valid JPG or PNG (returns 400 if not)
3. Original file is saved to `storage/originals/`
4. A record is persisted in SQLite with status `processing`
5. The image ID is returned immediately (HTTP 202) — **non-blocking**
6. A background async worker picks up the job and:
   - Extracts metadata (width, height, format, size, file datetime)
   - Extracts EXIF data if present (camera info, GPS coordinates, etc.)
   - Generates small (128×128) and medium (256×256) JPEG thumbnails
   - Generates an AI caption using BLIP (or a descriptive fallback)
   - Records processing duration and updates status to `success` or `failed`
7. Client polls `GET /api/images/{id}` until status is `success` or `failed`

---

## Project Structure

```
.
├── src/digital_forensics/
│   ├── api/
│   │   ├── app.py                 # FastAPI app, all route handlers, async worker
│   │   └── __init__.py
│   ├── services/
│   │   ├── image_pipeline.py      # Image processing, thumbnails, metadata, EXIF
│   │   └── captioning.py          # BLIP AI caption service + fallback
│   ├── models.py                  # SQLAlchemy ORM model (ImageRecord)
│   ├── database.py                # DB engine and session factory
│   ├── config.py                  # Paths, sizes, supported formats
│   ├── ui/
│   │   └── index.html             # Built-in browser test UI
│   ├── main.py                    # Compatibility shim
│   └── __init__.py
├── tests/
│   ├── conftest.py                # Test fixtures (client, DB reset)
│   └── test_api.py                # 7 API tests
├── scripts/
│   └── demo.sh                    # One-command end-to-end demo
├── storage/                       # Created at runtime
│   ├── originals/
│   └── thumbnails/
│       ├── small/
│       └── medium/
├── app.db                         # SQLite database (created at runtime)
├── pyproject.toml                 # Package config, dependencies, extras
├── Dockerfile                     # Docker containerisation
├── .dockerignore
└── README.md
```

---

## Docker (Bonus)

```bash
docker build -t digital-forensics-api .
docker run --rm -p 8000:8000 digital-forensics-api
```

Then open http://localhost:8000/ in your browser.

---

## Further Improvements

Given more time, the following enhancements could be added:

| Improvement | Description |
|-------------|-------------|
| **Rate limiting** | Throttle uploads per client to prevent abuse (e.g. `slowapi`) |
| **File-size limits** | Reject uploads above a configurable max size before processing |
| **CORS middleware** | Allow cross-origin requests for front-end apps on different domains |
| **Pagination** | Add `limit`/`offset` query params to `GET /api/images` for large datasets |
| **Authentication** | API-key or OAuth2 to restrict access |
| **Image deduplication** | Hash-based detection to avoid storing duplicate uploads |
| **Webhook / SSE notifications** | Push processing results to clients instead of polling |
| **S3 / cloud storage** | Replace local filesystem with object storage for scalability |
| **Batch uploads** | Accept multiple images in a single request |
| **Configurable thumbnail sizes** | Let callers request arbitrary dimensions |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Address already in use` on port 8000 | Run `lsof -ti:8000 \| xargs kill -9` then restart |
| `uvicorn: command not found` | Use `python3 -m uvicorn ...` instead |
| Captions are generic/descriptive instead of AI | Install AI deps: `pip install -e '.[ai]'` and restart server |
| First upload is slow (~10-30s) | Normal — the BLIP model downloads on first use (~990 MB) |
| `python: command not found` | Use `python3` instead of `python` |
