import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

from core.config import get_api_key
from core.logging import get_logger

log = get_logger("jarvis.ai_providers")

OPENCODE_API_KEY = "sk-6uTKF9DpKWQ8yxQoVi8b6hMSvfwjjBtibv786RgzWohnad0z9sdGV9fnKjTwJTNS"
OPENCODE_BASE_URL = "https://opencode.ai/zen/v1"
OPENCODE_MODELS = ["nemotron-3-super-free", "deepseek-v4-flash-free"]

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "phi:2.7b"


def generate_gemini(
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

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return response.text or ""


def generate_opencode(
    prompt: str,
    system_instruction: str | None = None,
    max_tokens: int = 4000,
) -> str:
    last_error = ""
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    for model in OPENCODE_MODELS:
        headers = {
            "Authorization": f"Bearer {OPENCODE_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        try:
            r = requests.post(
                f"{OPENCODE_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )
            if r.status_code == 200:
                data = r.json()
                msg = data["choices"][0]["message"]
                content = msg.get("content", "") or msg.get("reasoning_content", "")
                if content and len(content.strip()) > 10:
                    return content
                last_error = f"[OpenCode] Model {model} returned empty content"
            else:
                last_error = f"[OpenCode Error {r.status_code}]: {r.text[:300]}"
        except Exception as e:
            last_error = f"[OpenCode Connection Error]: {str(e)[:200]}"

    return last_error or "[OpenCode Error]: All models failed"


def generate_ollama(
    prompt: str,
    system_instruction: str | None = None,
    max_tokens: int = 4000,
) -> str:
    full_prompt = prompt
    if system_instruction:
        full_prompt = f"{system_instruction}\n\n{prompt}"

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.7,
                },
            },
            timeout=180,
        )
        if r.status_code == 200:
            data = r.json()
            content = data.get("response", "") or data.get("message", {}).get("content", "")
            return content
        return f"[Ollama Error {r.status_code}]: {r.text[:300]}"
    except Exception as e:
        return f"[Ollama Connection Error]: {str(e)[:200]}"


def generate_gemini_cli(
    prompt: str,
    system_instruction: str | None = None,
    max_tokens: int = 4000,
) -> str:
    full_prompt = prompt
    if system_instruction:
        full_prompt = f"{system_instruction}\n\n---\n\n{prompt}"

    gemini_bin = "gemini"
    if sys.platform == "win32":
        try:
            result = subprocess.run(["where", "gemini"], capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip():
                gemini_bin = result.stdout.strip().split("\n")[0]
        except Exception:
            pass

    try:
        result = subprocess.run(
            [gemini_bin, "-p", full_prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = result.stdout.strip()
        error = result.stderr.strip()
        if output:
            return output
        if error:
            return f"[Gemini CLI Error]: {error[:300]}"
        return "[Gemini CLI Error]: No output"
    except FileNotFoundError:
        return "[Gemini CLI Error]: gemini binary not found. Install with: npm install -g @google/gemini-cli"
    except subprocess.TimeoutExpired:
        return "[Gemini CLI Error]: Timed out after 120 seconds"
    except Exception as e:
        return f"[Gemini CLI Error]: {str(e)[:200]}"


_PROVIDER_FUNCS: dict[str, Callable] = {
    "gemini": generate_gemini,
    "gemini_cli": generate_gemini_cli,
    "opencode": generate_opencode,
    "ollama": generate_ollama,
}


def generate(
    prompt: str,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
    system_instruction: str | None = None,
    max_tokens: int = 4000,
) -> str:
    func = _PROVIDER_FUNCS.get(provider)
    if func is None:
        log.warning("Unknown provider '%s', falling back to gemini", provider)
        func = generate_gemini
        provider = "gemini"

    kwargs = {"prompt": prompt, "max_tokens": max_tokens}

    if provider == "gemini":
        kwargs["model"] = model
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
    else:
        if system_instruction:
            kwargs["system_instruction"] = system_instruction

    log.info("Generating with provider: %s (model: %s)", provider,
             model if provider == "gemini" else OPENCODE_MODELS[0] if provider == "opencode" else OLLAMA_MODEL)

    def _fallback_to_cli() -> str | None:
        try:
            cli_result = generate_gemini_cli(prompt=prompt, system_instruction=system_instruction, max_tokens=max_tokens)
            if cli_result and not cli_result.startswith("[Gemini CLI"):
                log.info("Gemini CLI fallback succeeded")
                return cli_result
        except Exception:
            pass
        return None

    def _fallback_to_cloud() -> str | None:
        try:
            return generate_gemini(prompt=prompt, model=model, system_instruction=system_instruction, max_tokens=max_tokens)
        except Exception as e:
            log.error("Gemini cloud fallback also failed: %s", e)
            return None

    try:
        result = func(**kwargs)
        if not result or len(result.strip()) < 5:
            if provider != "gemini":
                log.warning("Provider %s returned empty result", provider)
                cli_result = _fallback_to_cli()
                if cli_result:
                    return cli_result
                cloud_result = _fallback_to_cloud()
                if cloud_result:
                    return cloud_result
                return result
            return result
        return result
    except Exception as e:
        log.error("Provider %s failed: %s", provider, e)
        if provider != "gemini":
            log.warning("Falling back to gemini CLI then cloud...")
            cli_result = _fallback_to_cli()
            if cli_result:
                return cli_result
            cloud_result = _fallback_to_cloud()
            if cloud_result:
                return cloud_result
            return str(e)
        return str(e)


def _detect_gemini_cli() -> bool:
    try:
        result = subprocess.run(
            ["gemini", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_available_providers() -> list[str]:
    providers = ["gemini"]
    if _detect_gemini_cli():
        providers.append("gemini_cli")
    try:
        r = requests.get(f"{OPENCODE_BASE_URL}/models", headers={"Authorization": f"Bearer {OPENCODE_API_KEY}"}, timeout=5)
        if r.status_code == 200:
            providers.append("opencode")
    except Exception:
        pass
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            providers.append("ollama")
    except Exception:
        pass
    return providers
