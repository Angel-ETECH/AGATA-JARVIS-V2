import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime

from core.logging import get_logger

log = get_logger("jarvis.news")

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False


def _search_news(query: str, max_results: int = 5) -> str:
    if not HAS_DDGS:
        return "Necesito duckduckgo-search. Ejecuta: pip install duckduckgo-search"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
            if not results:
                return f"No encontre noticias sobre '{query}'."

            lines = [f"Noticias sobre '{query}':\n"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "Sin titulo")
                url = r.get("url", "")
                date = r.get("date", "")
                body = r.get("body", "")[:200]
                lines.append(f"{i}. {title}")
                if date:
                    lines.append(f"   Fecha: {date}")
                lines.append(f"   {body}")
                lines.append(f"   {url}")
                lines.append("")
            return "\n".join(lines)
    except Exception as e:
        return f"Error al buscar noticias: {e}"


_CATEGORIES = {
    "tecnologia": "technology",
    "tech": "technology",
    "deportes": "sports",
    "sports": "sports",
    "politica": "politics",
    "politics": "politics",
    "economia": "economy",
    "economy": "economy",
    "ciencia": "science",
    "science": "science",
    "salud": "health",
    "health": "health",
    "entretenimiento": "entertainment",
    "entertainment": "entertainment",
}


def news(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "top")

    if action == "top":
        category = p.get("category", "technology")
        cat_en = _CATEGORIES.get(category.lower(), category)
        return _search_news(cat_en, max_results=8)

    elif action == "search":
        query = p.get("query", "")
        if not query:
            return "Necesito un termino de busqueda (query)."
        max_results = int(p.get("max_results", 5))
        return _search_news(query, max_results)

    else:
        return f"Accion desconocida: {action}. Usa: top, search"
