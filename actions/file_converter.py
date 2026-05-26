import subprocess
import sys
from pathlib import Path

from core.logging import get_logger

log = get_logger("jarvis.file_converter")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


_FORMAT_MAP = {
    "png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP",
    "bmp": "BMP", "gif": "GIF", "ico": "ICO", "tiff": "TIFF",
}


def _convert_image(filepath: str, to_format: str) -> str:
    if not HAS_PIL:
        return "Necesito Pillow. Ejecuta: pip install Pillow"

    src = Path(filepath)
    if not src.exists():
        return f"Archivo no encontrado: {filepath}"

    fmt = _FORMAT_MAP.get(to_format.lower())
    if not fmt:
        return f"Formato no soportado: {to_format}. Usa: {', '.join(_FORMAT_MAP.keys())}"

    try:
        img = Image.open(str(src))
        desktop = Path.home() / "Desktop"
        outpath = desktop / f"{src.stem}_converted.{to_format.lower()}"

        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.save(str(outpath), format=fmt)
        return f"Imagen convertida: {outpath}"
    except Exception as e:
        return f"Error al convertir imagen: {e}"


def _convert_doc_to_pdf(filepath: str) -> str:
    src = Path(filepath)
    if not src.exists():
        return f"Archivo no encontrado: {filepath}"

    ext = src.suffix.lower()
    desktop = Path.home() / "Desktop"
    outpath = desktop / f"{src.stem}.pdf"

    if ext == ".docx":
        try:
            from docx import Document
            return "Para convertir DOCX a PDF usa la herramienta de Agata (agata_create type=pdf) o instala una impresora PDF virtual."
        except ImportError:
            return "python-docx no instalado."

    if ext == ".txt" or ext == ".md" or ext == ".csv":
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=10)
            for line in Path(filepath).read_text(encoding="utf-8", errors="replace").split("\n")[:200]:
                pdf.cell(200, 8, txt=line[:200], ln=True)
            pdf.output(str(outpath))
            return f"Convertido a PDF: {outpath}"
        except ImportError:
            return "Necesito fpdf. Ejecuta: pip install fpdf"
        except Exception as e:
            return f"Error: {e}"

    return f"Conversion de {ext} a PDF no soportada directamente. Usa Microsoft Print to PDF."


def file_converter(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "image")
    filepath = p.get("file_path", "")

    if not filepath:
        return "Necesito la ruta del archivo (file_path)."

    if action == "image":
        to_format = p.get("to_format", "png")
        return _convert_image(filepath, to_format)

    elif action == "to_pdf":
        return _convert_doc_to_pdf(filepath)

    else:
        return f"Accion desconocida: {action}. Usa: image, to_pdf"
