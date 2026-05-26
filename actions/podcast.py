import json
import re
from pathlib import Path

from core.logging import get_logger

log = get_logger("jarvis.podcast")

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False


def _search_podcasts(query: str, max_results: int = 5) -> str:
    if not HAS_DDGS:
        return "Necesito duckduckgo-search."

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                f"{query} podcast spotify OR apple podcasts",
                max_results=max_results
            ))
            if not results:
                return f"No encontre podcasts sobre '{query}'."

            lines = [f"Podcasts sobre '{query}':\n"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "Sin titulo")
                body = r.get("body", "")[:200]
                url = r.get("href", "")
                lines.append(f"{i}. {title}")
                lines.append(f"   {body}...")
                lines.append(f"   {url}")
                lines.append("")
            return "\n".join(lines)
    except Exception as e:
        return f"Error al buscar podcasts: {e}"


def podcast(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "search")

    if action == "search":
        query = p.get("query", "")
        if not query:
            return "Que tema de podcast buscas, senor? Necesito el parametro 'query'."
        max_results = int(p.get("max_results", 5))
        return _search_podcasts(query, max_results)

    elif action == "trending":
        return _search_podcasts("trending podcasts 2024", 10)

    else:
        return f"Accion desconocida: {action}. Usa: search, trending"
