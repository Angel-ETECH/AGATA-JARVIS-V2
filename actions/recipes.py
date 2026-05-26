import json
import re
from pathlib import Path

from core.logging import get_logger

log = get_logger("jarvis.recipes")

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False


def _search_recipes(query: str, max_results: int = 3) -> str:
    if not HAS_DDGS:
        return "Necesito duckduckgo-search."

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                f"{query} recipe ingredients instructions site:allrecipes.com OR site:foodnetwork.com",
                max_results=max_results
            ))
            if not results:
                results = list(ddgs.text(
                    f"{query} receta ingredientes preparacion",
                    max_results=max_results
                ))

            if not results:
                return f"No encontre recetas para '{query}'."

            lines = [f"Recetas para '{query}':\n"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "Sin titulo")
                body = r.get("body", "")[:400]
                url = r.get("href", "")
                lines.append(f"{i}. {title}")
                lines.append(f"   {body}...")
                lines.append(f"   {url}")
                lines.append("")
            return "\n".join(lines)
    except Exception as e:
        return f"Error al buscar recetas: {e}"


def recipes(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "search")

    if action == "search":
        query = p.get("query", "")
        if not query:
            return "Que receta buscas, senor? Necesito el parametro 'query'."
        max_results = int(p.get("max_results", 3))
        return _search_recipes(query, max_results)

    elif action == "random":
        import random
        cuisines = ["italiana", "mexicana", "japonesa", "china", "india",
                     "francesa", "mediterranea", "argentina", "peruana", "tailandesa"]
        cuisine = random.choice(cuisines)
        return _search_recipes(f"{cuisine} recipe", 2)

    else:
        return f"Accion desconocida: {action}. Usa: search, random"
