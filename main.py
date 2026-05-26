import asyncio
import re
import threading
import sys
import traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import sounddevice as sd
from google import genai
from google.genai import types
from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)

from core.paths import PROMPT_PATH, AGATA_PROMPT_PATH
from core.config import get_api_key
from core.constants import (
    LIVE_MODEL, CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE,
)
from core.logging import get_logger

log = get_logger("jarvis.main")

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.agata_creator      import agata_create, list_palettes
from actions.spotify_control    import spotify_control
from actions.system_monitor     import system_monitor
from actions.clipboard_manager  import clipboard_manager
from actions.pdf_tools          import pdf_tools
from actions.file_converter     import file_converter
from actions.database_query     import database_query
from actions.translator         import translator
from actions.news               import news
from actions.scheduler          import scheduler
from actions.backup             import backup
from actions.stocks_crypto      import stocks_crypto
from actions.email_manager      import email_manager
from actions.calendar_manager   import calendar_manager
from actions.macro_recorder     import macro_recorder
from actions.workflow           import workflow
from actions.recipes            import recipes
from actions.podcast            import podcast
from actions.web_builder         import web_builder
from actions.terminal             import terminal
from actions.slide_builder        import slide_builder


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "You speak and respond in Spanish. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Also supports opening project folders in IDEs "
            "like Antigravity and VS Code using the project_path parameter. "
            "Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify', 'Antigravity')"
                },
                "project_path": {
                    "type": "STRING",
                    "description": "Optional: full path to a project folder to open in an IDE (Antigravity, VS Code, etc.)"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source":   {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "question": {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": []
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, screenshots, navigation, any web-based task. "
            "Always pass the 'browser' parameter when the user specifies a browser (e.g. 'open in Edge', "
            "'use Firefox', 'open Chrome'). Multiple browsers can run simultaneously."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"},
                "browser":     {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser."},
                "url":         {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "engine":      {"type": "STRING", "description": "Search engine: google | bing | duckduckgo | yandex (default: google)"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"},
                "key":         {"type": "STRING", "description": "Key name for press action (e.g. Enter, Escape, F5)"},
                "path":        {"type": "STRING", "description": "Save path for screenshot"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files. Supports gemini, opencode, and ollama providers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "provider":    {"type": "STRING", "description": "AI provider: gemini | opencode | ollama (default: gemini)"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors. Ask the user ALL project specifications before calling this. Supports gemini, opencode, and ollama providers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "Complete project description including all features, database, framework, and design preferences"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "database":     {"type": "STRING", "description": "Database to use (e.g. SQLite, PostgreSQL, MySQL, MongoDB, Firebase)"},
                "framework":    {"type": "STRING", "description": "Framework or technology (e.g. React, Django, Flask, FastAPI, Electron)"},
                "platform":     {"type": "STRING", "description": "Where it runs: web, desktop, mobile, cli, api"},
                "provider":     {"type": "STRING", "description": "AI provider: gemini | opencode | ollama (default: gemini)"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "web_builder",
        "description": "Builds complete websites using OpenCode AI, Ollama, or Gemini. Supports HTML/CSS/JS, React, Vue, Node.js. Plans structure, generates all files, installs npm deps, opens browser preview and VSCode.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":   {"type": "STRING", "description": "What the website should do and contain"},
                "tech":          {"type": "STRING", "description": "html | react | vue | node | static | landing | dashboard | blog | portfolio | ecommerce"},
                "features":      {"type": "STRING", "description": "Specific features: responsive, dark mode, animations, contact form, gallery, API calls, etc."},
                "project_name":  {"type": "STRING", "description": "Optional project folder name (kebab-case)"},
                "design":        {"type": "STRING", "description": "modern | minimal | dark | colorful | corporate (default: modern)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "spotify_control",
        "description": (
            "Controls Spotify: search and play songs, pause, resume, skip tracks, adjust volume. "
            "Use this for ANY music/song request. "
            "Examples: 'pon Despacito en Spotify', 'reproduce musica de Coldplay', 'pausa la musica', "
            "'siguiente cancion', 'sube el volumen de Spotify'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | pause | resume | next | previous | volume_up | volume_down (default: play)"},
                "query":  {"type": "STRING", "description": "Song name or artist to search and play"},
            },
            "required": []
        }
    },
    {
        "name": "shutdown_jarvis",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop Jarvis. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
    "name": "file_processor",
    "description": (
        "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Juan, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "toggle_panel",
        "description": (
            "Muestra u oculta el panel de interfaz de JARVIS (chat, subida de archivos, comandos). "
            "Usalo cuando el usuario pida ver/ocultar el chat, subir un archivo, "
            "o interactuar con la interfaz visual. "
            "Ejemplos: 'muestrame el chat', 'quiero subir un archivo', "
            "'oculta los paneles', 'muestra la interfaz', 'abre el cargador de archivos', "
            "'cierra el panel lateral'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "show_chat | show_files | show_all | hide_all"
                },
            },
            "required": ["action"]
        }
    },
    {
        "name": "switch_persona",
        "description": (
            "Changes the assistant's personality and voice. "
            "Use when the user calls 'Agata' or 'Jarvis' by name. "
            "Switches to Agata (female, designer, elegant) or Jarvis (male, technical, direct). "
            "The UI colors, voice, and name will change automatically. "
            "Examples: 'Agata!', 'Jarvis!', 'switch to Agata', 'change to Jarvis'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "persona": {
                    "type": "STRING",
                    "description": "agata | jarvis"
                },
            },
            "required": ["persona"]
        }
    },
    {
        "name": "agata_create",
        "description": (
            "Creates beautifully designed Word documents or PowerPoint presentations. "
            "ONLY use when Agata persona is active. "
            "Generates content with DeepSeek/OpenCode AI and applies professional design. "
            "Supports color palettes: elegant, pastel, corporativo, moderno, rosa, nordico."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING", "description": "word | ppt (default: word)"},
                "title": {"type": "STRING", "description": "Document/presentation title"},
                "topic": {"type": "STRING", "description": "Topic or description of content to generate"},
                "palette": {"type": "STRING", "description": "elegant | pastel | corporativo | moderno | rosa | nordico (default: elegant)"},
            },
            "required": ["title", "topic"]
        }
    },
    {
        "name": "list_palettes",
        "description": "Shows available design color palettes for document creation (Agata feature).",
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
    {
        "name": "terminal",
        "description": (
            "Executes any command in the system terminal (PowerShell on Windows, "
            "bash/zsh on Mac/Linux). Use this when the user asks to run a command, "
            "execute a script, install packages, check system info, or any CLI task. "
            "Returns the command output. Max 2000 chars returned."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "The full command to execute (e.g. 'dir', 'ls -la', 'pip install requests', 'python script.py')"
                },
                "timeout": {
                    "type": "INTEGER",
                    "description": "Timeout in seconds (default: 30, max: 120)"
                },
                "cwd": {
                    "type": "STRING",
                    "description": "Working directory for the command (default: user home)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "system_monitor",
        "description": "Shows system information: CPU, RAM, disk, network, battery, running processes, uptime.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "cpu | ram | disk | network | battery | processes | uptime | full (default: full)"},
            },
            "required": []
        }
    },
    {
        "name": "clipboard_manager",
        "description": "Manages clipboard history: list history, get last item, copy at index, clear history.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | get_last | get_index | copy | clear"},
                "index": {"type": "INTEGER", "description": "Clipboard history index for get_index"},
                "text": {"type": "STRING", "description": "Text to copy to clipboard"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "pdf_tools",
        "description": "Read, get info, merge, and split PDF files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "read | info | merge | split"},
                "file_path": {"type": "STRING", "description": "Path to the PDF file"},
                "files": {"type": "STRING", "description": "Comma-separated file paths for merge"},
                "pages": {"type": "STRING", "description": "Page range e.g. '1-5' or '1,3,5' (default: all)"},
                "output_name": {"type": "STRING", "description": "Output file name for merge"},
            },
            "required": ["action", "file_path"]
        }
    },
    {
        "name": "file_converter",
        "description": "Converts files between formats: images (png, jpg, webp, bmp, gif), text/markdown to PDF.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "image | to_pdf"},
                "file_path": {"type": "STRING", "description": "Path to the file to convert"},
                "to_format": {"type": "STRING", "description": "Target format for image conversion (png, jpg, webp, etc.)"},
            },
            "required": ["action", "file_path"]
        }
    },
    {
        "name": "database_query",
        "description": "Executes SQL queries on SQLite or MySQL databases. Also lists tables.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "query | tables"},
                "type": {"type": "STRING", "description": "sqlite | mysql (default: sqlite)"},
                "file_path": {"type": "STRING", "description": "Path to the SQLite database file"},
                "query": {"type": "STRING", "description": "SQL query to execute"},
                "host": {"type": "STRING", "description": "MySQL host (default: localhost)"},
                "user": {"type": "STRING", "description": "MySQL username"},
                "password": {"type": "STRING", "description": "MySQL password"},
                "database": {"type": "STRING", "description": "MySQL database name"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "translator",
        "description": "Translates text between languages using AI. Supports: Spanish, English, French, German, Italian, Portuguese, Chinese, Japanese, Korean, Russian, Arabic, Hindi, Dutch, Polish, Turkish.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Text to translate"},
                "target_lang": {"type": "STRING", "description": "Target language (e.g. english, spanish, french, es, en, fr)"},
                "source_lang": {"type": "STRING", "description": "Source language (auto-detect if empty)"},
            },
            "required": ["text", "target_lang"]
        }
    },
    {
        "name": "news",
        "description": "Searches and retrieves latest news by category or keyword via DuckDuckGo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "top | search"},
                "category": {"type": "STRING", "description": "technology | sports | politics | economy | science | health | entertainment"},
                "query": {"type": "STRING", "description": "Search term for news"},
                "max_results": {"type": "INTEGER", "description": "Max results (default: 5-8)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "scheduler",
        "description": "Manages scheduled recurring tasks: list, add, remove, toggle, or run tasks now. Supports open_app, run_command, reminder, and backup actions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | add | remove | toggle | run_now"},
                "name": {"type": "STRING", "description": "Task name"},
                "task_action": {"type": "STRING", "description": "open_app | run_command | reminder | backup"},
                "interval_minutes": {"type": "INTEGER", "description": "How often to run (minutes, default: 60)"},
                "extra": {"type": "STRING", "description": "App name, command, or source->dest for backup tasks"},
                "index": {"type": "INTEGER", "description": "Task index to remove/toggle/run"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "backup",
        "description": "Backs up files or folders to a destination. Can also schedule recurring backups.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "run | schedule"},
                "source": {"type": "STRING", "description": "File or folder to backup"},
                "destination": {"type": "STRING", "description": "Where to save the backup"},
                "interval_minutes": {"type": "INTEGER", "description": "Minutes between scheduled backups (default: 1440 = daily)"},
            },
            "required": ["action", "source"]
        }
    },
    {
        "name": "stocks_crypto",
        "description": "Gets real-time stock prices (AAPL, TSLA, MSFT, etc.) and crypto prices (BTC, ETH, SOL, etc.).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "stock | crypto"},
                "symbol": {"type": "STRING", "description": "Stock symbol (AAPL, TSLA) or crypto name (bitcoin, ethereum, btc, eth)"},
            },
            "required": ["action", "symbol"]
        }
    },
    {
        "name": "email_manager",
        "description": "Reads or sends emails via Gmail or Outlook. Requires setup first with email and app password.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "read | send | setup | status"},
                "email": {"type": "STRING", "description": "Email address for setup"},
                "password": {"type": "STRING", "description": "App password for setup"},
                "provider": {"type": "STRING", "description": "gmail | outlook"},
                "to": {"type": "STRING", "description": "Recipient email for sending"},
                "subject": {"type": "STRING", "description": "Email subject"},
                "body": {"type": "STRING", "description": "Email body text"},
                "limit": {"type": "INTEGER", "description": "Max emails to read (default: 5)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "calendar_manager",
        "description": "Manages personal calendar: view upcoming/today events, add, remove events.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "upcoming | list | add | remove | today"},
                "title": {"type": "STRING", "description": "Event title"},
                "datetime": {"type": "STRING", "description": "Date and time: YYYY-MM-DDTHH:MM"},
                "location": {"type": "STRING", "description": "Event location"},
                "days": {"type": "INTEGER", "description": "Days ahead to look (default: 7)"},
                "index": {"type": "INTEGER", "description": "Event index to remove"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "macro_recorder",
        "description": "Records and plays back mouse movements, clicks, and keystrokes as macros.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "record | stop | play | play_now | list | delete"},
                "name": {"type": "STRING", "description": "Macro name"},
                "duration": {"type": "INTEGER", "description": "Recording duration in seconds (default: 10)"},
                "speed": {"type": "NUMBER", "description": "Playback speed multiplier (default: 1.0)"},
                "delay": {"type": "INTEGER", "description": "Delay before playback starts (default: 3)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "workflow",
        "description": "Creates, lists, runs, and deletes multi-step workflows that chain multiple tools together.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | run | create | delete"},
                "name": {"type": "STRING", "description": "Workflow name"},
                "steps": {"type": "STRING", "description": "JSON array of steps for create: [{\"tool\": \"...\", \"parameters\": {...}}]"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "recipes",
        "description": "Searches for recipes online. Finds ingredients, instructions from cooking sites.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "search | random"},
                "query": {"type": "STRING", "description": "What recipe to search for (e.g. 'pasta carbonara')"},
                "max_results": {"type": "INTEGER", "description": "Max results (default: 3)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "podcast",
        "description": "Searches for podcasts by topic or keyword. Shows trending podcasts.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "search | trending"},
                "query": {"type": "STRING", "description": "Topic to search podcasts for"},
                "max_results": {"type": "INTEGER", "description": "Max results (default: 5)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "slide_builder",
        "description": (
            "Creates CINEMATIC HTML slideshow presentations with immersive design system. "
            "Generates full-screen slides with dark cinematic theme, glow effects, image integration, "
            "and smooth scroll-snap navigation. Use when the user wants a visual presentation, "
            "slideshow, portfolio, or cinematic gallery. The result opens automatically in the browser."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "topic": {
                    "type": "STRING",
                    "description": "Main topic or theme of the presentation (e.g. 'Product Launch', 'Portfolio', 'Tech Conference')"
                },
                "slides": {
                    "type": "STRING",
                    "description": "Description of what each slide should contain. Leave empty for AI-generated content."
                },
                "include_images": {
                    "type": "BOOLEAN",
                    "description": "Whether to include relevant background images (default: true)"
                },
            },
            "required": ["topic"]
        }
    },
]

_CASUAL_TOOLS = {
    "open_app", "web_search", "weather_report", "send_message", "reminder",
    "youtube_video", "screen_process", "save_memory", "toggle_panel", 
    "switch_persona", "shutdown_jarvis", "translator", "news", "recipes", 
    "podcast", "stocks_crypto", "calendar_manager", "email_manager"
}

_AGATA_TOOLS = _CASUAL_TOOLS | {
    "agata_create", "list_palettes", "file_converter", "pdf_tools"
}

_JARVIS_TOOLS = _CASUAL_TOOLS | {
    "browser_control", "file_controller", "spotify_control", "file_processor",
    "computer_settings", "desktop_control", "code_helper", "dev_agent", 
    "agent_task", "computer_control", "game_updater", "flight_finder",
    "system_monitor", "clipboard_manager", "database_query", "scheduler",
    "backup", "macro_recorder", "workflow", "web_builder", "terminal",
    "slide_builder"
}

def _filter_tools_for_persona(persona: str) -> list[dict]:
    if persona == "agata":
        return [t for t in TOOL_DECLARATIONS if t["name"] in _AGATA_TOOLS]
    return [t for t in TOOL_DECLARATIONS if t["name"] in _JARVIS_TOOLS]


class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self._turn_done_event: asyncio.Event | None = None
        self._persona       = "jarvis"
        self._reconnect     = False

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            log.warning("[SPEAK] Cannot speak: loop=%s session=%s", bool(self._loop), bool(self.session))
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.session.send_client_content(
                    turns={"parts": [{"text": text}]},
                    turn_complete=True
                ),
                self._loop
            )
        except Exception as e:
            log.warning("[SPEAK] Failed: %s", e)

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)

        if self._persona == "agata":
            try:
                sys_prompt = AGATA_PROMPT_PATH.read_text(encoding="utf-8")
            except Exception:
                sys_prompt = _load_system_prompt()
            voice_name = "Aoede"
        else:
            sys_prompt = _load_system_prompt()
            sys_prompt += "\n\nCRITICAL: Eres J.A.R.V.I.S., la inteligencia artificial de Tony Stark."
            voice_name = "Orus"

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        tools = _filter_tools_for_persona(self._persona)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": tools}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        log.info("[TOOL] %s  %s", name, args)
        self.ui.set_state("THINKING")

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                log.info("[Memory] [SAVE] %s/%s = %s", category, key, value)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Hecho."
        silent = False

        def _run(func, *a, **kw):
            return loop.run_in_executor(None, lambda: func(*a, **kw))

        try:
            handler = self._get_handler(name)
            if handler:
                result = await handler(args, loop, _run)
            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if isinstance(result, dict):
            silent = result.pop("__silent__", False)
            result = result.get("result", "ok")

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        log.info("[DONE] %s -> %s silent=%s", name, str(result)[:80], silent)
        resp = {"result": result}
        if silent:
            resp["silent"] = True
        return types.FunctionResponse(
            id=fc.id, name=name,
            response=resp
        )

    def _get_handler(self, name: str):
        handlers = {
            "open_app":          self._h_open_app,
            "weather_report":    self._h_weather,
            "browser_control":   self._h_browser,
            "file_controller":   self._h_file_ctrl,
            "send_message":      self._h_send_msg,
            "reminder":          self._h_reminder,
            "youtube_video":     self._h_youtube,
            "screen_process":    self._h_screen,
            "computer_settings": self._h_comp_settings,
            "desktop_control":   self._h_desktop,
            "code_helper":       self._h_code,
            "dev_agent":         self._h_dev_agent,
            "agent_task":        self._h_agent_task,
            "web_search":        self._h_web_search,
            "file_processor":    self._h_file_proc,
            "computer_control":  self._h_comp_control,
            "game_updater":      self._h_game,
            "flight_finder":     self._h_flight,
            "spotify_control":   self._h_spotify,
            "toggle_panel":      self._h_toggle_panel,
            "switch_persona":    self._h_switch_persona,
            "agata_create":      self._h_agata_create,
            "list_palettes":     self._h_list_palettes,
            "shutdown_jarvis":   self._h_shutdown,
            "system_monitor":    self._h_system_monitor,
            "clipboard_manager": self._h_clipboard,
            "pdf_tools":         self._h_pdf_tools,
            "file_converter":    self._h_file_converter,
            "database_query":    self._h_db_query,
            "translator":        self._h_translator,
            "news":              self._h_news,
            "scheduler":         self._h_scheduler,
            "backup":            self._h_backup,
            "stocks_crypto":     self._h_stocks,
            "email_manager":     self._h_email,
            "calendar_manager":  self._h_calendar,
            "macro_recorder":    self._h_macro,
            "workflow":          self._h_workflow,
            "recipes":           self._h_recipes,
            "podcast":           self._h_podcast,
            "web_builder":       self._h_web_builder,
            "terminal":          self._h_terminal,
            "slide_builder":     self._h_slide_builder,
        }
        return handlers.get(name)

    async def _h_open_app(self, args, loop, _run):
        return (await _run(open_app, parameters=args, response=None, player=self.ui)) or f"Opened {args.get('app_name')}."

    async def _h_weather(self, args, loop, _run):
        return (await _run(weather_action, parameters=args, player=self.ui)) or "Weather delivered."

    async def _h_browser(self, args, loop, _run):
        return (await _run(browser_control, parameters=args, player=self.ui)) or "Hecho."

    async def _h_file_ctrl(self, args, loop, _run):
        return (await _run(file_controller, parameters=args, player=self.ui)) or "Hecho."

    async def _h_send_msg(self, args, loop, _run):
        return (await _run(send_message, parameters=args, response=None, player=self.ui, session_memory=None)) or f"Message sent to {args.get('receiver')}."

    async def _h_reminder(self, args, loop, _run):
        return (await _run(reminder, parameters=args, response=None, player=self.ui)) or "Reminder set."

    async def _h_youtube(self, args, loop, _run):
        return (await _run(youtube_video, parameters=args, response=None, player=self.ui)) or "Hecho."

    async def _h_screen(self, args, loop, _run):
        threading.Thread(
            target=screen_process,
            kwargs={"parameters": args, "response": None,
                    "player": self.ui, "session_memory": None,
                    "speak_func": self.speak},
            daemon=True
        ).start()
        return {"__silent__": True, "result": "Vision module activated."}

    async def _h_comp_settings(self, args, loop, _run):
        return (await _run(computer_settings, parameters=args, response=None, player=self.ui)) or "Hecho."

    async def _h_desktop(self, args, loop, _run):
        return (await _run(desktop_control, parameters=args, player=self.ui)) or "Hecho."

    async def _h_code(self, args, loop, _run):
        return (await _run(code_helper, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_dev_agent(self, args, loop, _run):
        return (await _run(dev_agent, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_agent_task(self, args, loop, _run):
        from agent.task_queue import get_queue, TaskPriority
        priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
        priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
        task_id = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
        return f"Task started (ID: {task_id})."

    async def _h_web_search(self, args, loop, _run):
        return (await _run(web_search_action, parameters=args, player=self.ui)) or "Hecho."

    async def _h_file_proc(self, args, loop, _run):
        if not args.get("file_path") and self.ui.current_file:
            args["file_path"] = self.ui.current_file
        return (await _run(file_processor, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_comp_control(self, args, loop, _run):
        return (await _run(computer_control, parameters=args, player=self.ui)) or "Hecho."

    async def _h_game(self, args, loop, _run):
        return (await _run(game_updater, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_flight(self, args, loop, _run):
        return (await _run(flight_finder, parameters=args, player=self.ui)) or "Hecho."

    async def _h_spotify(self, args, loop, _run):
        return (await _run(spotify_control, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_toggle_panel(self, args, loop, _run):
        action = args.get("action", "show_all")
        self.ui.toggle_panel(action)
        return f"Panel {action}."

    async def _h_switch_persona(self, args, loop, _run):
        new_persona = args.get("persona", "jarvis")
        if new_persona not in ("jarvis", "agata"):
            return f"Persona invalida: {new_persona}. Usa jarvis o agata."
        self._persona = new_persona
        self.ui.set_persona(new_persona)
        self._reconnect = True
        if new_persona == "agata":
            self.ui.write_log("SYS: Agata activada. Cambiando voz...")
            return "Hola, señor. Soy Agata. Encantada de estar con usted. ¿En qué puedo ayudarle hoy?"
        else:
            self.ui.write_log("SYS: JARVIS reactivado.")
            return "Señor, Jarvis de vuelta. ¿Cómo está? Aquí estoy para lo que necesite."

    async def _h_agata_create(self, args, loop, _run):
        args["api_key"] = get_api_key()
        doc_type = args.get("type", "word")
        title = args.get("title", "documento")
        self.ui.write_log(f"[Agata] Iniciando {doc_type.upper()} '{title}' en segundo plano...")

        def _agata_thread():
            try:
                res = agata_create(parameters=args, player=self.ui, speak=self.speak)
                if res and ("error" in str(res).lower() or "no pude" in str(res).lower()):
                    self.ui.write_log(f"[Agata] ERROR: {res}")
            except Exception as e:
                self.ui.write_log(f"[Agata] EXCEPCION: {e}")

        threading.Thread(target=_agata_thread, daemon=True).start()
        return f"Creando {doc_type} '{title}' en segundo plano."

    async def _h_list_palettes(self, args, loop, _run):
        return list_palettes(player=self.ui) or "Hecho."

    async def _h_shutdown(self, args, loop, _run):
        self.ui.write_log("SYS: Apagado solicitado.")
        self.speak("Adios, senor.")
        def _shutdown():
            import time, os
            time.sleep(1)
            os._exit(0)
        threading.Thread(target=_shutdown, daemon=True).start()
        return "Shutting down."

    async def _h_system_monitor(self, args, loop, _run):
        return (await _run(system_monitor, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_clipboard(self, args, loop, _run):
        return (await _run(clipboard_manager, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_pdf_tools(self, args, loop, _run):
        return (await _run(pdf_tools, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_file_converter(self, args, loop, _run):
        return (await _run(file_converter, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_db_query(self, args, loop, _run):
        return (await _run(database_query, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_translator(self, args, loop, _run):
        return (await _run(translator, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_news(self, args, loop, _run):
        return (await _run(news, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_scheduler(self, args, loop, _run):
        return (await _run(scheduler, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_backup(self, args, loop, _run):
        return (await _run(backup, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_stocks(self, args, loop, _run):
        return (await _run(stocks_crypto, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_email(self, args, loop, _run):
        return (await _run(email_manager, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_calendar(self, args, loop, _run):
        return (await _run(calendar_manager, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_macro(self, args, loop, _run):
        return (await _run(macro_recorder, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_workflow(self, args, loop, _run):
        return (await _run(workflow, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_recipes(self, args, loop, _run):
        return (await _run(recipes, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_podcast(self, args, loop, _run):
        return (await _run(podcast, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_web_builder(self, args, loop, _run):
        return (await _run(web_builder, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_terminal(self, args, loop, _run):
        return (await _run(terminal, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _h_slide_builder(self, args, loop, _run):
        return (await _run(slide_builder, parameters=args, player=self.ui, speak=self.speak)) or "Hecho."

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def _listen_audio(self):
        log.info("[MIC] Mic started")
        loop = asyncio.get_event_loop()

        def _enqueue(data):
            try:
                self.out_queue.put_nowait(
                    {"data": data, "mime_type": "audio/pcm"}
                )
            except asyncio.QueueFull:
                pass

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            if not jarvis_speaking and not self.ui.muted:
                loop.call_soon_threadsafe(_enqueue, indata.tobytes())

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                log.info("[MIC] Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            log.error("Mic: %s", e)
            raise

    async def _receive_audio(self):
        log.info("[RECV] Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                prefix = "Agata:" if self._persona == "agata" else "Jarvis:"
                                self.ui.write_log(f"{prefix} {full_out}")
                            out_buf = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            log.info("[CALL] %s", fc.name)
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
                        if self._reconnect:
                            log.info("[RECONN] Persona changed, reconnecting...")
                            raise ConnectionError("persona_switch")
        except ConnectionError:
            raise
        except Exception as e:
            log.error("Recv: %s", e)
            traceback.print_exc()
            raise

    async def _play_audio(self):
        log.info("[PLAY] Play started")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            log.error("Play: %s", e)
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        client = genai.Client(
            api_key=get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        backoff = 3
        while True:
            try:
                log.info("[CONN] Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)
                    self._turn_done_event = asyncio.Event()

                    log.info("[OK] Connected.")
                    self.ui.set_state("LISTENING")
                    name = "AGATA" if self._persona == "agata" else "JARVIS"
                    self.ui.write_log(f"SYS: {name} en linea.")
                    backoff = 3

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

            except BaseExceptionGroup as e:
                msg = str(e)
                if any("persona_switch" in str(sub) for sub in getattr(e, "exceptions", [])):
                    log.info("[RECONN] Reconnecting after persona switch...")
                    backoff = 0
                elif "1008" in msg or "policy violation" in msg:
                    log.error("Model error: %s", msg[:120])
                else:
                    log.warning(str(e))
                    traceback.print_exc()
            except Exception as e:
                msg = str(e)
                if "1008" in msg or "policy violation" in msg:
                    log.error("Model error: %s", msg[:120])
                else:
                    log.warning(str(e))
                    traceback.print_exc()
            self.set_speaking(False)
            self._reconnect = False
            self.ui.set_state("THINKING")
            log.info("[RETRY] Reconnecting in %ss...", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 30)

def main():
    ui = JarvisUI("face.png")

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            log.info("[SHUTDOWN] Apagando...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()