#!/usr/bin/env bash
set -euo pipefail

HOST="127.0.0.1"
PORT="8000"
BASE_URL="http://${HOST}:${PORT}"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  rm -f sample.jpg
}
trap cleanup EXIT

/usr/local/bin/python3 -m uvicorn digital_forensics.api.app:app --host "$HOST" --port "$PORT" >/tmp/forensics_api.log 2>&1 &
SERVER_PID=$!

sleep 1

/usr/local/bin/python3 -c "from PIL import Image; Image.new('RGB',(640,480),(12,34,200)).save('sample.jpg','JPEG')"

UPLOAD_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/images" -F "file=@sample.jpg")
echo "Upload: ${UPLOAD_RESPONSE}"

IMAGE_ID=$(/usr/local/bin/python3 -c "import json,sys; print(json.loads(sys.argv[1])['data']['image_id'])" "$UPLOAD_RESPONSE")

echo "Image ID: ${IMAGE_ID}"

for _ in {1..30}; do
  DETAILS=$(curl -s "${BASE_URL}/api/images/${IMAGE_ID}")
  STATUS=$(/usr/local/bin/python3 -c "import json,sys; print(json.loads(sys.argv[1])['status'])" "$DETAILS")
  if [[ "$STATUS" == "success" || "$STATUS" == "failed" ]]; then
    break
  fi
  sleep 0.2
done

echo "Details: ${DETAILS}"
echo "List: $(curl -s "${BASE_URL}/api/images")"
echo "Stats: $(curl -s "${BASE_URL}/api/stats")"

echo "Thumbnail status: $(curl -s -o /tmp/thumb_small.jpg -w '%{http_code}' "${BASE_URL}/api/images/${IMAGE_ID}/thumbnails/small")"
echo "Saved thumbnail to /tmp/thumb_small.jpg"
