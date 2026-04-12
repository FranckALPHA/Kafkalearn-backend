import subprocess
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

class DocConverter:
    @staticmethod
    def convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.docx")
            with open(input_path, "wb") as f:
                f.write(docx_bytes)
            try:
                cmd = ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, input_path]
                result = subprocess.run(cmd, capture_output=True, timeout=60)
                if result.returncode != 0:
                    raise Exception(f"LibreOffice error: {result.stderr.decode()}")
                pdf_path = os.path.join(tmpdir, "input.pdf")
                if not os.path.exists(pdf_path):
                    raise Exception("PDF file not generated")
                with open(pdf_path, "rb") as f:
                    return f.read()
            except subprocess.TimeoutExpired:
                raise Exception("Conversion timeout")
