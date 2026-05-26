import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
MEMORY_DIR = BASE_DIR / "memory"
CORE_DIR = BASE_DIR / "core"
ACTIONS_DIR = BASE_DIR / "actions"
AGENT_DIR = BASE_DIR / "agent"

PROJECT_DIR = BASE_DIR

CONFIG_PATH = CONFIG_DIR / "api_keys.json"
PROMPT_PATH = CORE_DIR / "prompt.txt"
AGATA_PROMPT_PATH = CORE_DIR / "agata_prompt.txt"
LONG_TERM_MEMORY_PATH = MEMORY_DIR / "long_term.json"
