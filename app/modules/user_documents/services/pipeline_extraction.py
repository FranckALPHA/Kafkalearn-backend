"""
app/modules/user_documents/services/pipeline_extraction.py
==========================================================
Pipeline d'extraction de texte pour l'ingestion.
Supporte PDF (natif + OCR), DOCX, TXT, etc.
"""
import io
import logging

logger = logging.getLogger(__name__)


class PipelineExtraction:
    """Pipeline d'extraction de texte pour les fichiers ingestés."""

    def extraire_texte(self, file_bytes: bytes, file_type: str) -> str:
        """
        Extrait le texte d'un fichier selon son type MIME.
        Retourne le texte extrait ou une chaîne vide.
        """
        mime = (file_type or "").lower()

        if "pdf" in mime:
            return self._extraire_pdf(file_bytes)
        elif "docx" in mime or "word" in mime:
            return self._extraire_docx(file_bytes)
        elif "text" in mime:
            return file_bytes.decode("utf-8", errors="replace")
        else:
            # Try PDF by default for unknown types
            return self._extraire_pdf(file_bytes)

    def _extraire_pdf(self, file_bytes: bytes) -> str:
        """Extraction native PDF via pdfplumber, OCR fallback."""
        # Native extraction
        try:
            import pdfplumber

            pdf_file = io.BytesIO(file_bytes)
            all_text = []
            page_count = 0

            with pdfplumber.open(pdf_file) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text.append(text)

            native_text = "\n\n".join(all_text)
            if native_text and len(native_text.strip()) > 50:
                logger.debug(f"Native PDF extraction succeeded ({page_count} pages)")
                return native_text
        except Exception as exc:
            logger.warning(f"pdfplumber extraction failed: {exc}")

        # OCR fallback
        return self._extraire_pdf_ocr(file_bytes)

    def _extraire_pdf_ocr(self, file_bytes: bytes) -> str:
        """OCR extraction for scanned PDFs."""
        try:
            from pdf2image import convert_from_bytes
            import pytesseract

            images = convert_from_bytes(file_bytes, dpi=200)
            text_parts = []
            for img in images:
                text_parts.append(pytesseract.image_to_string(img, lang="fra"))

            ocr_text = "\n\n".join(text_parts)
            if ocr_text.strip():
                logger.debug(f"OCR extraction succeeded ({len(images)} pages)")
            return ocr_text
        except ImportError as exc:
            logger.warning(f"OCR tools not available: {exc}")
            return ""
        except Exception as exc:
            logger.warning(f"OCR extraction failed: {exc}")
            return ""

    def _extraire_docx(self, file_bytes: bytes) -> str:
        """Extract text from DOCX files."""
        try:
            from docx import Document
            import io

            doc = Document(io.BytesIO(file_bytes))
            text_parts = [para.text for para in doc.paragraphs if para.text]
            return "\n\n".join(text_parts)
        except ImportError:
            logger.warning("python-docx not installed")
            return ""
        except Exception as exc:
            logger.warning(f"DOCX extraction failed: {exc}")
            return ""
