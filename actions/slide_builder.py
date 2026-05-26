import os, re, uuid
import shutil
from datetime import datetime
from pathlib import Path
import webbrowser

from core.paths import PROJECT_DIR
from actions.utils_diseno import buscar_y_descargar_imagen

SLIDES_DIR = PROJECT_DIR / "slides"

def _generar_html(descripcion: str, player=None) -> str:
    from core.ai_providers import generate_opencode

    SYSTEM = """Eres un disenador UI/UX senior experto en HTML/CSS puro.
Genera UNICAMENTE codigo HTML completo (sin markdown, sin explicaciones).
Debes seguir ESTRICTAMENTE estas 8 reglas de diseno:

1. PALETA: fondo #0b1120, primario #1a9fd4 (azul), acento #f5a623 (dorado, solo estrategico)
2. TIPOGRAFIA: Google Fonts Barlow Condensed (900) para titulos (4vw-5vw), Barlow para cuerpo (1.3vw). Labels en uppercase con letter-spacing amplio.
3. ESTRUCTURA por slide: Label -> Titulo enorme -> Linea acento (3px) -> Descripcion -> Grid de cards
4. PADDING: 5vh-6vh vertical, 6vw horizontal en cada slide
5. OVERLAY en imagenes: linear-gradient(rgba(11,17,32,0.97), transparent)
6. CARDS: background rgba(26,159,212,0.08), border 1px solid rgba(26,159,212,0.3)
7. UNIDADES FLUIDAS: solo vw y vh (prohibido px para fuentes/margenes/anchoses principales)
8. GLOWS: circulos radial-gradient semi-transparentes en esquinas (azul y dorado)

ANIMACIONES: fade-in suave al hacer scroll. Cada slide debe ocupar 100vh con scroll-snap.

La primera diapositiva es PORTADA con numero grande decorativo al fondo.
Incluye <img> con placeholder si se necesitan imagenes (usar https://picsum.photos/seed/NOMBRE/1200/800).
USA imagenes de https://picsum.photos con seeds descriptivas y el overlay de la regla 5.

Genera HTML auto-contenido con TODO el CSS inline en <style>.
NO uses frameworks. NO expliques el codigo. Solo HTML."""

    prompt = f"""Genera un sistema de diapositivas cinematograficas HTML/CSS para:

{descripcion}

Crea entre 2 y 4 diapositivas siguiendo el sistema de diseno cinematografico."""

    html = generate_opencode(prompt=prompt, system_instruction=SYSTEM, max_tokens=8000)
    html = html.strip()
    if "```html" in html:
        html = html.split("```html")[1]
    if "```" in html:
        html = html.split("```")[0]
    return html.strip()


def _descargar_imagenes(html: str, topic: str, output_dir: Path, player=None) -> str:
    urls = re.findall(r'https://picsum\.photos/seed/[^/"\')]+/\d+/\d+', html)
    if not urls:
        return html

    for url in set(urls):
        try:
            seed_match = re.search(r'seed/([^/]+)', url)
            seed = seed_match.group(1) if seed_match else str(uuid.uuid4())[:8]

            filepath = buscar_y_descargar_imagen(seed)
            if filepath:
                ext = Path(filepath).suffix or ".jpg"
                local_name = f"{seed}{ext}"
                local_path = output_dir / local_name
                shutil.copy2(filepath, local_path)
                html = html.replace(url, f"slides/{output_dir.name}/{local_name}")
        except Exception as e:
            if player:
                player.write_log(f"[Slides] Error descargando imagen {url}: {e}")
    return html


def slide_builder(parameters: dict, player=None, speak=None) -> str:
    p = parameters or {}
    topic = p.get("topic", "").strip()
    slides_desc = p.get("slides", "").strip()
    include_images = p.get("include_images", True)

    if not topic:
        return "Por favor especifica un tema para las diapositivas."

    description = f"Tema: {topic}\n"
    if slides_desc:
        description += f"Descripcion de diapositivas: {slides_desc}\n"
    description += f"Incluir imagenes: {'si' if include_images else 'no'}"

    if player:
        player.write_log(f"[Slides] Generando presentacion: {topic}")
        if speak:
            speak(f"Creando presentacion sobre {topic}, senor.")

    try:
        html = _generar_html(description, player)

        safe_name = "".join(c if c.isalnum() else "_" for c in topic)[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir_name = f"{safe_name}_{timestamp}"
        output_dir = SLIDES_DIR / output_dir_name
        output_dir.mkdir(parents=True, exist_ok=True)

        if include_images:
            if player:
                player.write_log("[Slides] Descargando imagenes...")
            html = _descargar_imagenes(html, topic, output_dir, player)

        filename = "presentation.html"
        filepath = output_dir / filename
        filepath.write_text(html, encoding="utf-8")

        webbrowser.open(str(filepath))

        slide_count = html.count("<section")
        if slide_count == 0:
            slide_count = len(re.findall(r'class="slide', html))

        if player:
            player.write_log(f"[Slides] Guardado: {filepath}")

        return (f"Presentacion '{topic}' creada con exito: {output_dir_name}/{filename}\n"
                f"{slide_count} diapositivas generadas. Abierto en el navegador.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"Error generando presentacion: {e}"
        if player:
            player.write_log(f"[Slides] ERROR: {error_msg}")
        return error_msg
