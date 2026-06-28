"""Image visual analysis - send document images to vision-capable LLMs"""
import base64
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysisConfig:
    enabled: bool = False
    model: str = "gpt-4o"
    max_images: int = 8
    min_width: int = 100
    min_height: int = 100
    skip_similar: bool = True
    similarity_threshold: float = 0.9


@dataclass
class ImageDescription:
    image_index: int
    page: int
    caption: str
    analysis: str
    model_used: str


class ImageAnalyzer:
    """Analyze document images using vision models."""

    MAX_CONTEXT_CHARS = 400

    async def analyze_images(
        self,
        images: list,
        config: ImageAnalysisConfig | None = None,
    ) -> list[ImageDescription]:
        """Analyze a list of ImageItems, filtering out non-essential ones."""
        if config is None:
            config = ImageAnalysisConfig()
        if not config.enabled or not images:
            return []

        # Filter images worth analyzing
        candidates = [img for img in images if self._should_analyze(img, config)]
        candidates = candidates[:config.max_images]

        if config.skip_similar and len(candidates) > 1:
            candidates = self._deduplicate(candidates, config.similarity_threshold)

        results = []
        for img in candidates:
            try:
                desc = await self._analyze_single(img, config.model)
                results.append(desc)
            except Exception as e:
                logger.warning("Image analysis failed for image %d: %s", img.index, e)
                continue

        return results

    def _should_analyze(self, image, config: ImageAnalysisConfig) -> bool:
        """Skip small images (icons, decorations) and header/footer images."""
        if image.width < config.min_width or image.height < config.min_height:
            logger.debug("Skipping small image %d (%dx%d)", image.index, image.width, image.height)
            return False
        # Skip images that look like logos or decorations (very wide or tall aspect ratio)
        if image.width > 0 and image.height > 0:
            ratio = image.width / image.height
            if ratio > 5 or ratio < 0.2:
                logger.debug("Skipping extreme-aspect image %d (ratio %.2f)", image.index, ratio)
                return False
        return True

    def _deduplicate(self, images: list, threshold: float) -> list:
        """Remove near-duplicate images based on file hash and dimensions."""
        kept = []
        seen_hashes = set()
        for img in images:
            try:
                img_bytes = Path(img.image_path).read_bytes()
                h = hashlib.md5(img_bytes).hexdigest()
            except Exception:
                h = f"{img.width}x{img.height}"
            if h not in seen_hashes:
                seen_hashes.add(h)
                kept.append(img)
            else:
                logger.debug("Skipping duplicate image %d (hash=%s)", img.index, h[:8])
        return kept

    async def _analyze_single(self, image, model: str) -> ImageDescription:
        """Send a single image to the vision model for analysis."""
        from app.core.api_scheduler import api_client
        from app.core.api_scheduler.client import GenerationConfig, TaskType

        # Read and encode image
        try:
            img_data = Path(image.image_path).read_bytes()
            img_b64 = base64.b64encode(img_data).decode("ascii")
        except Exception as e:
            raise RuntimeError(f"Cannot read image {image.index}: {e}")

        # Determine image MIME type
        ext = Path(image.image_path).suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp"}
        media_type = mime_map.get(ext, "image/png")

        # Build prompt with context
        prompt = (
            "请用中文简要描述这张图片在文档中表达的关键信息（1-3句话），"
            "重点关注：数据、流程图、架构关系、关键概念。不要描述装饰性元素。"
        )

        context_parts = []
        if image.caption:
            context_parts.append(f"图片标题：{image.caption}")
        if image.context_before:
            context_parts.append(f"上文：{image.context_before[-self.MAX_CONTEXT_CHARS:]}")
        if image.context_after:
            context_parts.append(f"下文：{image.context_after[:self.MAX_CONTEXT_CHARS:]}")
        context_text = "\n".join(context_parts) if context_parts else ""

        # Use vision-capable adapter
        try:
            content = await api_client.analyze_image(
                image_base64=img_b64,
                image_type=media_type,
                prompt=prompt,
                context_text=context_text,
                model=model,
            )
        except Exception as e:
            error_msg = str(e)
            if "No adapter configured" in error_msg or "image" in error_msg.lower():
                raise RuntimeError(
                    f"图片分析需要视觉模型（如 gpt-4o），请配置 OpenAI API Key。"
                    f"当前模型 {model} 不可用或不支持视觉功能。"
                )
            raise

        return ImageDescription(
            image_index=image.index,
            page=image.page,
            caption=image.caption,
            analysis=content.strip(),
            model_used=model,
        )


image_analyzer = ImageAnalyzer()
