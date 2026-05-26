import json

from core.config import gemini_generate


def _translate_with_gemini(text: str, target_lang: str, source_lang: str = "auto") -> str:
    src_hint = f"from {source_lang} " if source_lang != "auto" else ""
    prompt = (
        f"Translate the following text {src_hint}to {target_lang}. "
        f"Return ONLY the translation, nothing else. "
        f"Preserve formatting, line breaks, and structure.\n\n"
        f"Text:\n{text[:4000]}"
    )

    try:
        return gemini_generate(prompt, model="gemini-2.5-flash-lite")
    except Exception as e:
        return f"Error de traduccion: {e}"


_LANG_MAP = {
    "espanol": "Spanish", "español": "Spanish", "spanish": "Spanish", "es": "Spanish",
    "ingles": "English", "inglés": "English", "english": "English", "en": "English",
    "frances": "French", "francés": "French", "french": "French", "fr": "French",
    "aleman": "German", "alemán": "German", "german": "German", "de": "German",
    "italiano": "Italian", "italian": "Italian", "it": "Italian",
    "portugues": "Portuguese", "portugués": "Portuguese", "portuguese": "Portuguese", "pt": "Portuguese",
    "chino": "Chinese", "chinese": "Chinese", "zh": "Chinese",
    "japones": "Japanese", "japonés": "Japanese", "japanese": "Japanese", "ja": "Japanese",
    "coreano": "Korean", "korean": "Korean", "ko": "Korean",
    "ruso": "Russian", "russian": "Russian", "ru": "Russian",
    "arabe": "Arabic", "árabe": "Arabic", "arabic": "Arabic", "ar": "Arabic",
    "hindi": "Hindi", "hi": "Hindi",
    "holandes": "Dutch", "holandés": "Dutch", "dutch": "Dutch", "nl": "Dutch",
    "polaco": "Polish", "polish": "Polish", "pl": "Polish",
    "turco": "Turkish", "turkish": "Turkish", "tr": "Turkish",
}


def translator(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    text = p.get("text", "")
    target = p.get("target_lang", "Spanish")
    source = p.get("source_lang", "auto")

    if not text:
        return "Necesito el texto a traducir (text)."

    target_full = _LANG_MAP.get(target.lower(), target)
    source_full = _LANG_MAP.get(source.lower(), source) if source != "auto" else "auto"

    translated = _translate_with_gemini(text, target_full, source_full)

    if translated.startswith("Error"):
        return translated

    return (
        f"Traduccion {'(' + source_full + ' -> ' + target_full + ')' if source != 'auto' else 'a ' + target_full}:\n\n"
        f"{translated}"
    )
