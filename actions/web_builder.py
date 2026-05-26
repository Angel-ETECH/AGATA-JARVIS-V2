import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

from core.paths import BASE_DIR
from core.config import get_api_key
from core.logging import get_logger

log = get_logger("jarvis.web_builder")

OPENCODE_API_KEY = "sk-6uTKF9DpKWQ8yxQoVi8b6hMSvfwjjBtibv786RgzWohnad0z9sdGV9fnKjTwJTNS"
OPENCODE_BASE_URL = "https://opencode.ai/zen/v1"
OPENCODE_MODEL = "deepseek-v4-flash-free"
OPENCODE_FALLBACK = "nemotron-3-super-free"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "phi:2.7b"

PROJECTS_DIR = Path.home() / "Desktop" / "JarvisProjects"
MAX_RETRIES = 3


def _call_opencode(prompt: str, system_prompt: str = "", max_tokens: int = 8000) -> str:
    last_error = ""
    for model in [OPENCODE_MODEL, OPENCODE_FALLBACK]:
        headers = {
            "Authorization": f"Bearer {OPENCODE_API_KEY}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        try:
            r = requests.post(
                f"{OPENCODE_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )
            if r.status_code == 200:
                msg = r.json()["choices"][0]["message"]
                content = msg.get("content", "") or msg.get("reasoning_content", "")
                if content and len(content.strip()) > 20:
                    log.info("OpenCode %s returned %d chars", model, len(content))
                    return content
                last_error = f"[OpenCode] {model} returned empty"
            else:
                last_error = f"[OpenCode Error {r.status_code}]: {r.text[:300]}"
        except Exception as e:
            last_error = f"[OpenCode Connection Error]: {str(e)[:200]}"
    return last_error or "[OpenCode Error]"


def _call_ollama(prompt: str, system_prompt: str = "", max_tokens: int = 8000) -> str:
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.2,
                },
            },
            timeout=180,
        )
        if r.status_code == 200:
            content = r.json().get("response", "")
            if content.strip():
                return content
        return f"[Ollama Error {r.status_code}]"
    except Exception as e:
        return f"[Ollama Connection Error]: {str(e)[:200]}"


def _call_gemini(prompt: str, system_prompt: str = "", max_tokens: int = 8000, model: str = "gemini-2.5-flash") -> str:
    from core.config import gemini_generate
    try:
        return gemini_generate(prompt, model=model, system_instruction=system_prompt or None, max_tokens=max_tokens)
    except Exception as e:
        return f"[Gemini Error]: {str(e)[:200]}"


def _ai_generate(prompt: str, system_prompt: str = "", max_tokens: int = 8000, model: str = "gemini-2.5-flash") -> str:
    result = _call_opencode(prompt, system_prompt, max_tokens)
    if result.startswith("[OpenCode"):
        log.info("OpenCode failed, trying Ollama...")
        result = _call_ollama(prompt, system_prompt, max_tokens)
        if result.startswith("[Ollama"):
            log.info("Ollama failed, trying Gemini...")
            result = _call_gemini(prompt, system_prompt, max_tokens, model)
    return result


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()


def _plan_website(description: str, tech: str, features: str) -> dict:
    system_prompt = (
        "You are a senior web architect. Plan a complete website project. "
        "Return ONLY valid JSON, no markdown, no explanation."
    )

    prompt = f"""Plan a complete website with this specification:

Technology: {tech}
Description: {description}
Features: {features}

Return this JSON structure:
{{
  "project_name": "kebab-case-name",
  "entry_point": "index.html",
  "description": "Brief description",
  "files": [
    {{"path": "index.html", "description": "Main HTML with structure", "imports": []}},
    {{"path": "css/style.css", "description": "Styles", "imports": []}},
    {{"path": "js/main.js", "description": "Main JavaScript logic", "imports": []}},
    {{"path": "js/app.js", "description": "App logic", "imports": ["js/main.js"]}}
  ],
  "run_command": "start index.html",
  "dependencies": [],
  "dev_dependencies": [],
  "build_command": null,
  "has_server": false
}}

CRITICAL RULES:
1. For plain HTML/CSS/JS: no dependencies, entry_point = "index.html", has_server = false
2. For React: dependencies = ["react", "react-dom"], dev_dependencies = ["vite", "@vitejs/plugin-react"], entry_point = "index.html", build_command = "npm run dev", has_server = true
3. For Vue: dependencies = ["vue"], dev_dependencies = ["vite", "@vitejs/plugin-vue"], entry_point = "index.html", has_server = true
4. For Node.js/Express: dependencies = ["express"], entry_point = "server.js", run_command = "node server.js", has_server = true
5. List files in dependency order (leaf files first, main entry last)
6. Include ALL necessary files (package.json for npm projects, .gitignore, etc.)
7. Every file that provides exports must be listed in imports by dependent files

JSON:"""

    try:
        result = _ai_generate(prompt, system_prompt, max_tokens=2000)
        if result.startswith("[") and result.endswith("]"):
            result = result
        return json.loads(_strip_fences(result))
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON: {e}\nRaw: {result[:300]}")
    except Exception as e:
        raise


def _write_web_file(
    file_info: dict,
    project_description: str,
    all_files: list[dict],
    tech: str,
    features: str,
    project_dir: Path,
    already_written: dict[str, str],
) -> str:
    file_path = file_info["path"]
    file_desc = file_info.get("description", "")
    file_imports = file_info.get("imports", [])

    file_list = "\n".join(
        f"  [{i + 1}] {f['path']}: {f.get('description', '')}"
        for i, f in enumerate(all_files)
    )

    dependency_context = ""
    for dep_path_rel in file_imports:
        if dep_path_rel in already_written:
            code_snippet = already_written[dep_path_rel][:2000]
            dependency_context += f"\n\n--- {dep_path_rel} (this file exports the following API — you must use these exact imports) ---\n{code_snippet}"

    ext = Path(file_path).suffix.lower()
    lang_hint = {
        ".html": "HTML5",
        ".css": "CSS3",
        ".js": "JavaScript ES6+",
        ".jsx": "React JSX",
        ".ts": "TypeScript",
        ".tsx": "React TypeScript",
        ".vue": "Vue SFC",
        ".json": "JSON",
        ".md": "Markdown",
    }.get(ext, tech)

    system_prompt = (
        f"You are an expert {lang_hint} developer building a production-quality web project. "
        "Write clean, modern, well-structured code. "
        "Use semantic HTML5, CSS Grid/Flexbox, modern JavaScript. "
        "Make the design responsive and visually appealing. "
        "Add useful comments where needed. "
        "Output ONLY the complete code — no markdown, no backticks, no explanation."
    )

    prompt = f"""Write the COMPLETE code for this file in a {tech} web project.

Project: {project_description}
Features: {features}

All project files (context only — write just the target file):
{file_list}

{f"This file is {file_path} — purpose: {file_desc}"}
{f"This file imports from: {', '.join(file_imports)}" if file_imports else "This is a standalone file (no project-internal imports)."}
{dependency_context}

CRITICAL RULES:
- Output ONLY the COMPLETE {lang_hint} code. No explanation, no markdown, no backticks.
- Write FULL, COMPLETE, PRODUCTION-READY code — no placeholders, no "// TODO", no "// Add more here".
- Match all imports EXACTLY to the paths in dependency_context above.
- Make the design responsive (mobile-first) and visually polished.
- Use modern CSS with proper color scheme, typography, spacing.
- Handle errors and edge cases properly.

Code for {file_path}:"""

    try:
        response = _ai_generate(prompt, system_prompt, max_tokens=8000)
        code = _strip_fences(response)

        if len(code) < 20:
            raise ValueError(f"Generated code too short ({len(code)} chars)")

        full_path = project_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(code, encoding="utf-8")

        log.info("Written: %s (%d chars)", file_path, len(code))
        return code

    except Exception as e:
        log.error("Failed to write %s: %s", file_path, e)
        raise


def _install_dependencies(dependencies: list[str], dev_dependencies: list[str], project_dir: Path) -> str:
    all_deps = dependencies + dev_dependencies
    if not all_deps:
        return "No npm dependencies."

    log.info("Installing npm: %s", all_deps)

    pkg_json = project_dir / "package.json"
    if not pkg_json.exists():
        pkg_json.write_text(json.dumps({
            "name": project_dir.name,
            "version": "1.0.0",
            "private": True,
        }, indent=2), encoding="utf-8")

    try:
        if dependencies:
            subprocess.run(
                ["npm", "install"] + dependencies,
                cwd=str(project_dir),
                capture_output=True, text=True,
                timeout=120,
            )
        if dev_dependencies:
            subprocess.run(
                ["npm", "install", "--save-dev"] + dev_dependencies,
                cwd=str(project_dir),
                capture_output=True, text=True,
                timeout=120,
            )
        return f"Dependencies installed: {', '.join(all_deps)}"
    except Exception as e:
        log.warning("npm install failed (non-fatal): %s", e)
        return f"npm install note: {e}. Run 'npm install' manually in {project_dir}."


def _open_browser(filepath: str) -> bool:
    try:
        if sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "", filepath], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", filepath])
        else:
            subprocess.Popen(["xdg-open", filepath])
        time.sleep(1)
        return True
    except Exception:
        return False


def _open_vscode(project_dir: Path) -> bool:
    import shutil
    code_path = shutil.which("code")
    if not code_path:
        candidates = [
            rf"C:\Users\{Path.home().name}\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd",
            r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
        ]
        for c in candidates:
            if Path(c).exists():
                code_path = c
                break
    if code_path:
        try:
            subprocess.Popen([code_path, str(project_dir)], shell=True)
            time.sleep(1.5)
            log.info("VSCode opened: %s", project_dir)
            return True
        except Exception:
            pass
    return False


def _preview_server(project_dir: Path, port: int = 3000) -> subprocess.Popen | None:
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port)],
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        _open_browser(f"http://localhost:{port}")
        return proc
    except Exception as e:
        log.warning("Preview server failed: %s", e)
        return None


def _build_website(
    description: str,
    tech: str,
    features: str,
    project_name: str,
    design: str,
    speak=None,
    player=None,
) -> str:
    def _log(msg: str):
        log.info(msg)
        if player:
            player.write_log(f"[WebBuilder] {msg}")

    _log(f"Planning {tech} website: {project_name or description[:40]}...")

    try:
        plan = _plan_website(description, tech, features)
    except ValueError as e:
        msg = f"Planning failed: {e}"
        if speak:
            speak(msg)
        _log(msg)
        return msg

    proj_name = project_name or plan.get("project_name", "jarvis_site")
    proj_name = re.sub(r"[^\w\-]", "_", proj_name)
    project_dir = PROJECTS_DIR / proj_name
    project_dir.mkdir(parents=True, exist_ok=True)

    files = plan.get("files", [])
    entry_point = plan.get("entry_point", "index.html")
    run_command = plan.get("run_command", "start index.html")
    dependencies = plan.get("dependencies", [])
    dev_dependencies = plan.get("dev_dependencies", [])
    has_server = plan.get("has_server", False)

    _log(f"Project: {proj_name} | Files: {len(files)} | {tech}")

    def _dep_sort_key(fi: dict) -> int:
        return len(fi.get("imports", []))

    sorted_files = sorted(files, key=_dep_sort_key)
    file_codes: dict[str, str] = {}

    for file_info in sorted_files:
        file_path = file_info.get("path", "")
        if not file_path:
            continue
        _log(f"Writing {file_path}...")
        for attempt in range(2):
            try:
                code = _write_web_file(
                    file_info=file_info,
                    project_description=description,
                    all_files=files,
                    tech=tech,
                    features=features,
                    project_dir=project_dir,
                    already_written=file_codes,
                )
                file_codes[file_path] = code
                time.sleep(0.5)
                break
            except Exception as e:
                if attempt == 0:
                    _log(f"Retry {file_path}: {e}")
                    time.sleep(3)
                else:
                    _log(f"Failed {file_path}: {e}")

    if not file_codes:
        msg = "I couldn't write any website files, sir."
        if speak:
            speak(msg)
        return msg

    if dependencies or dev_dependencies:
        install_result = _install_dependencies(dependencies, dev_dependencies, project_dir)
        _log(install_result)

    _open_vscode(project_dir)

    entry_full = project_dir / entry_point
    preview_proc = None

    if has_server:
        _log("Starting dev server...")
        preview_proc = _preview_server(project_dir)
    elif entry_full.exists():
        _open_browser(str(entry_full))

    msg = (
        f"Website '{proj_name}' built successfully, sir. "
        f"{len(file_codes)} files created. "
        f"Saved to: {project_dir}"
    )
    if speak:
        speak(msg)

    return f"{msg}\n\nTech: {tech}\nFiles: {', '.join(file_codes.keys())}"


def web_builder(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    p = parameters or {}
    description = p.get("description", "").strip()
    tech = p.get("tech", "html").strip().lower()
    features = p.get("features", "").strip()
    project_name = p.get("project_name", "").strip()
    design = p.get("design", "modern").strip().lower()

    if not description:
        return "Please describe the website you want me to build, sir."

    tech_map = {
        "html": "HTML/CSS/JavaScript",
        "react": "React (Vite + JSX)",
        "vue": "Vue 3 (Vite + SFC)",
        "node": "Node.js + Express",
        "static": "HTML/CSS/JavaScript (static)",
        "landing": "HTML/CSS/JavaScript (landing page)",
        "dashboard": "React (Vite + JSX + dashboard UI)",
        "blog": "HTML/CSS/JavaScript (blog layout)",
        "portfolio": "HTML/CSS/JavaScript (portfolio)",
        "ecommerce": "React (Vite + JSX + product catalog)",
    }
    tech_full = tech_map.get(tech, tech)

    return _build_website(
        description=description,
        tech=tech_full,
        features=features,
        project_name=project_name,
        design=design,
        speak=speak,
        player=player,
    )
