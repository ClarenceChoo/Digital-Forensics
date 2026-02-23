FROM python:3.11-slim

WORKDIR /app

# Set to "ai" to include AI captioning deps (transformers + torch)
ARG INSTALL_EXTRAS="ai"

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && if [ -n "$INSTALL_EXTRAS" ]; then \
         pip install --no-cache-dir ".[$INSTALL_EXTRAS]"; \
       else \
         pip install --no-cache-dir .; \
       fi

EXPOSE 8000

CMD ["uvicorn", "digital_forensics.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
