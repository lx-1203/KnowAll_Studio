"""Docling-based document parser - extracts structured content with headings, images, tables"""
import hashlib
import re
from pathlib import Path
from dataclasses import dataclass, field
from app.config import settings


@dataclass
class HeadingNode:
    """Native outline heading node"""
    id: str
    label: str
    level: int
    page: int = 0
    children: list["HeadingNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "level": self.level,
            "page": self.page,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ImageItem:
    """Extracted image from document"""
    index: int
    image_path: str
    page: int
    caption: str = ""
    context_before: str = ""
    context_after: str = ""
    width: int = 0
    height: int = 0
    bbox: tuple = ()


@dataclass
class TableItem:
    """Extracted table from document"""
    index: int
    page: int
    caption: str = ""
    markdown: str = ""
    dataframe_json: str = ""


@dataclass
class StructuredDocument:
    """Enhanced parse result with document structure"""
    text: str
    page_count: int
    headings: list[HeadingNode] = field(default_factory=list)
    images: list[ImageItem] = field(default_factory=list)
    tables: list[TableItem] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DoclingParser:
    """Parse PDF/DOCX/PPTX/HTML with Docling, extracting full document structure."""

    SUPPORTED_TYPES = {"pdf", "docx", "pptx", "html"}

    def __init__(self, images_dir: str | None = None):
        self._images_dir = Path(images_dir or settings.document_dir) / "images"

    async def parse(self, file_path: str, file_type: str) -> StructuredDocument:
        """Parse a document with Docling and extract structured content."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path, file_type)

    def _parse_sync(self, file_path: str, file_type: str) -> StructuredDocument:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = settings.docling_ocr
        pipeline_options.do_table_structure = True
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        result = converter.convert(file_path)
        doc = result.document

        # Apply hierarchical PDF fix if available
        try:
            from hierarchical.postprocessor import ResultPostprocessor
            ResultPostprocessor(result).process()
        except Exception:
            pass

        # Extract headings tree
        headings = self._extract_headings(doc, file_path)

        # Extract images
        doc_hash = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()[:12]
        images = self._extract_images(doc, result, doc_hash)

        # Extract tables
        tables = self._extract_tables(doc, result)

        # Generate structured markdown text
        text = doc.export_to_markdown()

        # Get page count
        num_pages = getattr(doc, "num_pages", None)
        if callable(num_pages):
            num_pages = num_pages()
        page_count = num_pages or 1

        return StructuredDocument(
            text=text,
            page_count=page_count,
            headings=headings,
            images=images,
            tables=tables,
            metadata={
                "parser": "docling",
                "file_type": file_type,
                "doc_hash": doc_hash,
            },
        )

    def _extract_headings(self, doc, file_path: str) -> list[HeadingNode]:
        """Extract heading hierarchy from DoclingDocument."""
        node_stack: list[HeadingNode] = []  # stack of (level, node)
        roots: list[HeadingNode] = []
        heading_counter = [0]

        for item, level in doc.iterate_items():
            label = getattr(item, "label", None)
            if label is None:
                continue
            label_str = str(label).lower()
            if "heading" not in label_str and "title" not in label_str and "section" not in label_str:
                continue

            text = getattr(item, "text", "").strip()
            if not text:
                continue

            heading_counter[0] += 1
            item_level = self._infer_heading_level(label_str)
            page = self._get_item_page(item, doc)

            node = HeadingNode(
                id=f"h{heading_counter[0]}",
                label=text,
                level=item_level,
                page=page,
            )

            # Pop siblings at same or deeper level
            while node_stack and node_stack[-1].level >= item_level:
                node_stack.pop()

            if node_stack:
                node_stack[-1].children.append(node)
            else:
                roots.append(node)

            node_stack.append(node)

        # If Docling flattened everything (all same level), try to infer from numbering patterns
        if roots and all(len(r.children) == 0 for r in roots) and len(roots) > 3:
            roots = self._infer_hierarchy_from_numbering(roots)

        return roots

    @staticmethod
    def _infer_heading_level(label: str) -> int:
        """Map DocItemLabel to numeric heading level."""
        label_lower = label.lower()
        if "title" in label_lower:
            return 1
        elif "section" in label_lower:
            return 2
        elif "subsection" in label_lower:
            return 3
        elif "subsubsection" in label_lower:
            return 4
        return 2

    @staticmethod
    def _get_item_page(item, doc) -> int:
        """Get page number for a document item."""
        prov = getattr(item, "prov", None)
        if prov and len(prov) > 0:
            return getattr(prov[0], "page_no", 0) or 0
        return 0

    def _infer_hierarchy_from_numbering(self, flat_nodes: list[HeadingNode]) -> list[HeadingNode]:
        """Try to reconstruct hierarchy from Chinese/English numbering patterns like 一、1.1, 第一章 etc."""
        patterns = [
            (r"^第[一二三四五六七八九十百]+章", 1),
            (r"^第[一二三四五六七八九十百]+节", 2),
            (r"^[一二三四五六七八九十百]、", 1),
            (r"^\d+\.\d+\.\d+", 3),
            (r"^\d+\.\d+", 2),
            (r"^\d+[、.．]", 1),
        ]

        root = HeadingNode(id="root", label="", level=0)
        stack = [(0, root)]

        for node in flat_nodes:
            inferred_level = 1
            for pattern, level_val in patterns:
                if re.match(pattern, node.label):
                    inferred_level = level_val
                    break

            node.level = inferred_level
            while stack and stack[-1][0] >= inferred_level:
                stack.pop()

            parent = stack[-1][1]
            parent.children.append(node)
            stack.append((inferred_level, node))

        return root.children

    def _extract_images(self, doc, result, doc_hash: str) -> list[ImageItem]:
        """Extract and save images from the document."""
        images = []
        img_dir = self._images_dir / doc_hash
        img_dir.mkdir(parents=True, exist_ok=True)

        for i, (item, _level) in enumerate(doc.iterate_items()):
            label = getattr(item, "label", None)
            if label is None or str(label).lower() != "picture":
                continue

            try:
                from PIL import Image
                pil_image = item.get_image(doc)
                if pil_image is None:
                    continue

                img_filename = f"img_{i:03d}.png"
                img_path = img_dir / img_filename
                pil_image.save(img_path, "PNG")

                page = self._get_item_page(item, doc)
                caption = getattr(item, "caption_text", "") or ""
                context_before, context_after = self._get_image_context(doc, item)

                images.append(ImageItem(
                    index=i,
                    image_path=str(img_path),
                    page=page,
                    caption=str(caption),
                    context_before=context_before,
                    context_after=context_after,
                    width=pil_image.width,
                    height=pil_image.height,
                ))
            except Exception:
                continue

        return images

    def _get_image_context(self, doc, picture_item) -> tuple[str, str]:
        """Get text context before and after an image."""
        texts = getattr(doc, "texts", [])
        if not texts:
            return "", ""

        try:
            pic_idx = texts.index(picture_item)
        except (ValueError, IndexError):
            return "", ""

        before = ""
        after = ""

        # Look backwards for nearby text
        for j in range(pic_idx - 1, max(pic_idx - 4, -1), -1):
            if j >= 0:
                label = getattr(texts[j], "label", None)
                if label and str(label).lower() == "text":
                    t = getattr(texts[j], "text", "")
                    if t:
                        before = t[-200:] + "\n" + before

        # Look forward for nearby text
        for j in range(pic_idx + 1, min(pic_idx + 4, len(texts))):
            if j < len(texts):
                label = getattr(texts[j], "label", None)
                if label and str(label).lower() == "text":
                    t = getattr(texts[j], "text", "")
                    if t:
                        after = after + t[:200] + "\n"

        return before.strip()[:500], after.strip()[:500]

    def _extract_tables(self, doc, result) -> list[TableItem]:
        """Extract tables from the document."""
        tables = []
        doc_tables = getattr(doc, "tables", []) or []

        for i, table in enumerate(doc_tables):
            try:
                df = table.export_to_dataframe()
                markdown = df.to_markdown(index=False) if hasattr(df, "to_markdown") else str(df)
                tables.append(TableItem(
                    index=i,
                    page=getattr(table, "page", 0) or 0,
                    caption=getattr(table, "caption_text", "") or "",
                    markdown=markdown,
                    dataframe_json=df.to_json(orient="records", force_ascii=False),
                ))
            except Exception:
                continue

        return tables


docling_parser = DoclingParser()
