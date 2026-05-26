# 🤖 J.A.R.V.I.S. — Jarvis & Agata
### Ultimate Personal AI Assistant — By BLACK0DEV

A real-time voice AI assistant with dual personalities: **Jarvis** (technical, system control, programming) and **Agata** (design, documents, presentations). Can hear, see, understand, and control your computer on Windows, macOS, and Linux. Local execution. Zero subscriptions.

---

## ✨ Overview

Jarvis & Agata is a voice-controlled AI assistant powered by Google Gemini Live API. It features real-time voice conversation, screen analysis, file processing, system control, web browsing, code generation, and autonomous multi-step task execution — all through natural dialogue.

Switch between **Jarvis** (your technical right hand) and **Agata** (your creative designer) with a simple voice command.

---

## 🚀 Capabilities

### Core Features
| Feature | Description |
|---|---|
| 🎙️ Real-time Voice | Ultra-low latency conversation with natural audio via Gemini Live API |
| 🖥️ System Control | Launch apps, manage files, execute terminal commands, control volume/brightness |
| 🧩 Autonomous Tasks | High-level planning for complex multi-step goals |
| 👁️ Visual Awareness | Real-time screen processing and webcam vision |
| 🧠 Persistent Memory | Remembers your projects, preferences, and personal context |
| ⌨️ Hybrid Input | Voice + keyboard, seamlessly switch between both |

### Jarvis (Technical)
| Ability | Description |
|---|---|
| 💻 Programming | Write, edit, explain, run code in any language (Python, JS, Java, C#, etc.) |
| 🌐 Web Control | Browse websites, fill forms, click elements, take screenshots |
| 📁 File Management | Create, delete, move, copy, read, write, organize files and folders |
| 🎵 Media | Spotify control, YouTube search/play, podcasts, recipes |
| 🔧 System | CPU/RAM/disk monitor, process management, system settings |
| 🤖 Agent | Execute complex multi-step workflows autonomously |
| 🗄️ Databases | SQL queries on SQLite and MySQL |
| 🖱️ Desktop Control | Mouse, keyboard, macros, screen capture, window management |
| 📧 Communication | Email (Gmail/Outlook), WhatsApp/Telegram messaging |
| 🔍 Information | Web search, weather, news, stocks/crypto, flights, translation |

### Agata (Design)
| Ability | Description |
|---|---|
| 📄 Word Documents | Professional documents with elegant design, covers, tables, typography |
| 📊 PowerPoint | High-impact presentations with modern design and animations |
| 🎨 Color Palettes | Multiple design palettes: elegant, pastel, corporate, modern, nordic |
| 🖼️ Image Tools | Process, convert, and edit images |

---

## 🆕 What's New

- 📂 **Advanced File Handling** — Direct file uploads. Drop PDFs, code, or images for instant analysis, summarization, or editing
- 🎨 **Adaptive UI** — Fully resizable, responsive interface with transparency controls
- 👥 **Dual Persona** — Switch between Jarvis and Agata with voice commands
- 🐧🍎 **Cross-Platform** — Full support for Windows, macOS, and Linux
- ⚡ **Optimized Engine** — 40% faster interaction speed with improved tool-calling
- 🗣️ **HD Voices** — 30+ natural voices with emotional tone control

---

## ⚡ Quick Start

```bash
# Clone the repository
git clone https://github.com/BLACK0DEV/jarvis-agata.git
cd jarvis-agata

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers (required for browser control)
playwright install

# Run the assistant
python main.py
```

> ⚠️ On first run, you'll be prompted to enter your **Gemini API key** (free tier available at [aistudio.google.com](https://aistudio.google.com/)).

---

## 📋 Requirements

### System Requirements
| Requirement | Details |
|---|---|
| **OS** | Windows 10/11, macOS 12+, or Linux (Ubuntu 22.04+) |
| **Python** | 3.11 or 3.12 |
| **RAM** | 4 GB minimum (8 GB recommended) |
| **Storage** | 500 MB for the assistant + Playwright browsers |
| **Microphone** | Required for voice interaction |
| **Internet** | Required for Gemini API connection |

### Python Dependencies

| Package | Purpose |
|---|---|
| `google-genai` | Gemini Live API and model access |
| `PyQt6` | Graphical user interface |
| `sounddevice` | Microphone audio capture |
| `playwright` | Browser automation (Chrome, Edge, Firefox) |
| `opencv-python` | Screen capture and computer vision |
| `pyautogui` | Desktop mouse/keyboard control |
| `pywinauto` | Windows GUI automation |
| `Pillow` | Image processing |
| `numpy` | Numerical computations |
| `mss` | High-speed screen capture |
| `requests` | HTTP requests |
| `beautifulsoup4` | HTML parsing |
| `duckduckgo-search` | Web search fallback |
| `python-docx` | Word document generation |
| `python-pptx` | PowerPoint presentation generation |
| `PyPDF2` / `pdfplumber` | PDF reading and extraction |
| `fpdf` | PDF generation |
| `youtube-transcript-api` | YouTube video transcripts |
| `psutil` | System monitoring (CPU, RAM, disk) |
| `pyperclip` | Clipboard management |
| `pygetwindow` | Window management |
| `comtypes` / `pycaw` | Windows audio control |
| `mysql-connector-python` | MySQL database queries |
| `colorthief` | Color palette extraction |
| `send2trash` | Safe file deletion |
| `win10toast` | Windows desktop notifications |

---

## 🔧 Setup

### 1. Get a Gemini API Key
1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Click **Get API Key**
3. Create a free API key
4. Enter the key when prompted on first launch

### 2. Configuration
The assistant stores your configuration in `config/api_keys.json`. You can also configure:
- Default AI provider (Gemini, OpenCode, or Ollama)
- Voice selection
- UI preferences

---

## 🎮 Usage

### Voice Commands
Just speak naturally. Examples:
- "Abre Chrome y busca el clima en Madrid"
- "Crea un programa en Python que calcule el factorial de un número"
- "Analiza mi pantalla"
- "Reproduce música de Coldplay en Spotify"
- "Agata, crea una presentación sobre energías renovables"

### Text Commands
Open the chat panel by saying "muestra el chat" and type your commands.

### Switching Personas
- "Agata" or "pásame con Agata" → switches to the design assistant
- "Jarvis" or "vuelve Jarvis" → switches back to the technical assistant

---

## 🧩 Key Files

| File | Purpose |
|---|---|
| `main.py` | Main entry point — audio pipeline, tool routing, Gemini Live connection |
| `ui.py` | PyQt6 GUI — starfield HUD, glass overlay, chat panel |
| `core/prompt.txt` | Jarvis system prompt — personality, rules, routing |
| `core/agata_prompt.txt` | Agata system prompt — designer persona |
| `core/constants.py` | Model names, audio constants, limits |
| `core/paths.py` | File path definitions |
| `actions/` | 35+ action modules (browser, files, code, spotify, etc.) |
| `agent/` | Autonomous task planning and execution system |
| `memory/` | Long-term memory persistence |

---

## ⚠️ License

Personal and non-commercial use only.
Licensed under **[Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**.

---

## 👤 Connect with the Creator

Engineered by **BLACK0DEV** — building a real-world JARVIS-style assistant.
⭐ **Star the repository to support the journey.**
