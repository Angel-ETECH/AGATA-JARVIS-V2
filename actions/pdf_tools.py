import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from core.paths import BASE_DIR
from core.config import get_api_key
from core.logging import get_logger

log = get_logger("jarvis.pdf_tools")

try:
    import PyPDF2
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


def _read_pdf(filepath: str, pages: str = "all") -> str:
    if not Path(filepath).exists():
        return f"Archivo no encontrado: {filepath}"

    try:
        text_parts = []
        if HAS_PDFPLUMBER:
            with pdfplumber.open(filepath) as pdf:
                total = len(pdf.pages)
                page_nums = _parse_pages(pages, total)
                for i in page_nums:
                    page = pdf.pages[i]
                    txt = page.extract_text()
                    if txt:
                        text_parts.append(f"--- Pagina {i + 1} ---\n{txt}")
                if not text_parts:
                    return "No se pudo extraer texto del PDF (puede ser escaneado/imagen)."
                return f"PDF: {Path(filepath).name} ({total} paginas)\n\n" + "\n\n".join(text_parts)
        elif HAS_PYPDF:
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                total = len(reader.pages)
                page_nums = _parse_pages(pages, total)
                for i in page_nums:
                    txt = reader.pages[i].extract_text()
                    if txt:
                        text_parts.append(f"--- Pagina {i + 1} ---\n{txt}")
                if not text_parts:
                    return "No se pudo extraer texto del PDF."
                return f"PDF: {Path(filepath).name} ({total} paginas)\n\n" + "\n\n".join(text_parts)
        else:
            return "Necesito PyPDF2 o pdfplumber. Ejecuta: pip install PyPDF2 pdfplumber"
    except Exception as e:
        return f"Error al leer PDF: {e}"


def _merge_pdfs(files: list[str], output_name: str) -> str:
    if not HAS_PYPDF:
        return "Necesito PyPDF2. Ejecuta: pip install PyPDF2"

    if len(files) < 2:
        return "Necesito al menos 2 archivos para combinar."

    merger = PyPDF2.PdfMerger()
    try:
        for f in files:
            if not Path(f).exists():
                return f"Archivo no encontrado: {f}"
            merger.append(str(f))

        desktop = Path.home() / "Desktop"
        outpath = desktop / f"{output_name}.pdf"
        merger.write(str(outpath))
        merger.close()
        return f"PDF combinado guardado en: {outpath}"
    except Exception as e:
        return f"Error al combinar PDFs: {e}"


def _split_pdf(filepath: str, pages: str) -> str:
    if not PyPDF2:
        return "Necesito PyPDF2."

    if not Path(filepath).exists():
        return f"Archivo no encontrado: {filepath}"

    try:
        reader = PyPDF2.PdfReader(str(filepath))
        total = len(reader.pages)
        page_nums = _parse_pages(pages, total)
        desktop = Path.home() / "Desktop"
        base = Path(filepath).stem

        for i in page_nums:
            writer = PyPDF2.PdfWriter()
            writer.add_page(reader.pages[i])
            outpath = desktop / f"{base}_pag_{i + 1}.pdf"
            writer.write(str(outpath))

        return f"{len(page_nums)} paginas extraidas al Escritorio."
    except Exception as e:
        return f"Error al dividir PDF: {e}"


def _parse_pages(pages_spec: str, total: int) -> list[int]:
    if pages_spec.lower() == "all":
        return list(range(total))
    result = []
    parts = pages_spec.replace(" ", "").split(",")
    for part in parts:
        if "-" in part:
            a, b = part.split("-", 1)
            result.extend(range(int(a) - 1, min(int(b), total)))
        else:
            p = int(part) - 1
            if 0 <= p < total:
                result.append(p)
    return sorted(set(result))


def _pdf_info(filepath: str) -> str:
    if not Path(filepath).exists():
        return f"Archivo no encontrado: {filepath}"

    try:
        if HAS_PYPDF:
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                info = []
                info.append(f"Archivo: {Path(filepath).name}")
                info.append(f"Paginas: {len(reader.pages)}")
                meta = reader.metadata
                if meta:
                    if meta.title:
                        info.append(f"Titulo: {meta.title}")
                    if meta.author:
                        info.append(f"Autor: {meta.author}")
                return "\n".join(info)
        else:
            return f"Archivo: {Path(filepath).name}\nTamano: {Path(filepath).stat().st_size / 1024:.1f} KB"
    except Exception as e:
        return f"Error: {e}"


def pdf_tools(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "read")
    filepath = p.get("file_path", "")

    if action == "read":
        pages = p.get("pages", "all")
        return _read_pdf(filepath, pages)

    elif action == "info":
        return _pdf_info(filepath)

    elif action == "merge":
        files = p.get("files", [])
        if isinstance(files, str):
            files = [f.strip() for f in files.split(",")]
        output = p.get("output_name", "merged")
        return _merge_pdfs(files, output)

    elif action == "split":
        pages = p.get("pages", "1")
        return _split_pdf(filepath, pages)

    else:
        return f"Accion desconocida: {action}. Usa: read, info, merge, split"
