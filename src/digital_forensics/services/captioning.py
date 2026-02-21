import logging
import os
from pathlib import Path

from PIL import Image, ImageStat

logger = logging.getLogger("digital_forensics.captioning")


class CaptionService:
    def __init__(self) -> None:
        self._processor = None
        self._model = None
        self._tried_load = False
        configured_models = os.getenv(
            "CAPTION_MODELS",
            "Salesforce/blip-image-captioning-base,Salesforce/blip-image-captioning-large",
        )
        self._model_candidates = [item.strip() for item in configured_models.split(",") if item.strip()]
        self._active_model = None

    def _load_model(self):
        if self._tried_load:
            return
        self._tried_load = True

        if os.getenv("PYTEST_CURRENT_TEST"):
            logger.info("Skipping caption model loading during tests")
            self._model = None
            self._processor = None
            return

        try:
            from transformers import BlipForConditionalGeneration, BlipProcessor
        except Exception as exc:
            logger.warning("Transformers import failed, using fallback captions: %s", exc)
            self._model = None
            self._processor = None
            return

        for model_name in self._model_candidates:
            try:
                self._processor = BlipProcessor.from_pretrained(model_name)
                self._model = BlipForConditionalGeneration.from_pretrained(model_name)
                self._active_model = model_name
                logger.info("Caption model loaded: %s (direct BLIP)", model_name)
                return
            except Exception as exc:
                logger.warning("Failed to load caption model '%s': %s", model_name, exc)

        self._model = None
        self._processor = None
        logger.warning("No caption model loaded; fallback captions will be used")

    @staticmethod
    def _brightness_label(value: float) -> str:
        if value < 70:
            return "dark"
        if value > 180:
            return "bright"
        return "moderately lit"

    def _fallback_caption(self, image_path: Path, image_format: str, width: int, height: int) -> str:
        try:
            with Image.open(image_path) as image:
                grayscale = image.convert("L")
                brightness = ImageStat.Stat(grayscale).mean[0]
                brightness_label = self._brightness_label(brightness)

                orientation = "landscape" if width >= height else "portrait"
                return (
                    f"A {brightness_label} {orientation} {image_format.upper()} image "
                    f"with resolution {width}x{height}."
                )
        except Exception:
            return f"A {image_format.upper()} image with resolution {width}x{height}."

    def generate_caption(self, image_path: Path, image_format: str, width: int, height: int) -> str:
        self._load_model()
        if self._model is not None and self._processor is not None:
            try:
                import torch

                with Image.open(image_path) as image:
                    rgb_image = image.convert("RGB")

                inputs = self._processor(images=rgb_image, return_tensors="pt")
                with torch.no_grad():
                    generated_ids = self._model.generate(**inputs, max_new_tokens=32, num_beams=4)

                text = self._processor.decode(generated_ids[0], skip_special_tokens=True)
                if text:
                    return text.strip()
            except Exception as exc:
                logger.warning(
                    "Caption generation failed with model '%s': %s",
                    self._active_model,
                    exc,
                )

        return self._fallback_caption(image_path, image_format, width, height)


caption_service = CaptionService()
