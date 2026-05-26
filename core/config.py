import json
from pathlib import Path

from core.paths import CONFIG_PATH

_cache: dict[str, str] = {}


def _load_raw_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_config() -> dict:
    if "_config" not in _cache:
        _cache["_config"] = _load_raw_config()
    return _cache["_config"]


def get_api_key() -> str:
    if "api_key" not in _cache:
        _cache["api_key"] = get_config()["gemini_api_key"]
    return _cache["api_key"]


def get_os() -> str:
    return get_config().get("os_system", "windows").lower()


def is_windows() -> bool:
    return get_os() == "windows"


def is_mac() -> bool:
    return get_os() == "mac"


def is_linux() -> bool:
    return get_os() == "linux"


def get_setting(key: str, default=None):
    return get_config().get(key, default)


def gemini_generate(
    prompt: str,
    model: str = "gemini-2.5-flash",
    system_instruction: str | None = None,
    max_tokens: int = 4000,
) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_api_key())
    config = types.GenerateContentConfig(max_output_tokens=max_tokens)
    if system_instruction:
        config.system_instruction = system_instruction

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        return response.text or ""
    except Exception as e:
        raise e
