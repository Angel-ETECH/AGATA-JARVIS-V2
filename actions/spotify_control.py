import subprocess
import time

import pyautogui
import pygetwindow as gw
import pyperclip

SPOTIFY_PATH = "spotify:"


def _focus_spotify() -> bool:
    for w in gw.getWindowsWithTitle("Spotify"):
        if w.title.strip() and not w.isMinimized:
            try:
                w.activate()
                time.sleep(0.3)
                return True
            except Exception:
                pass
    for w in gw.getWindowsWithTitle("Spotify"):
        try:
            w.restore()
            w.activate()
            time.sleep(0.3)
            return True
        except Exception:
            pass
    return False


def _launch_spotify() -> bool:
    try:
        subprocess.Popen(["spotify"], shell=True)
        time.sleep(3)
        return _focus_spotify()
    except Exception:
        return False


def _ensure_spotify() -> bool:
    if _focus_spotify():
        return True
    return _launch_spotify()


def spotify_control(parameters: dict, player=None, speak=None) -> str:
    action = parameters.get("action", "play")
    query = parameters.get("query", "")

    if action == "play":
        if not query:
            return "Necesito el nombre de la cancion o artista para buscar."

        if not _ensure_spotify():
            return "No pude abrir Spotify. Asegurate de que este instalado."

        # Ctrl+L to focus search bar
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.3)

        # Select all and delete existing search
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("delete")
        time.sleep(0.1)

        # Type the search query
        pyperclip.copy(query)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(1.2)

        # Press Tab to move to the first result, then Enter to play
        pyautogui.press("tab")
        time.sleep(0.2)
        pyautogui.press("tab")
        time.sleep(0.2)
        pyautogui.press("enter")

        if speak:
            speak(f"Reproduciendo {query} en Spotify, senor.")

        return f"Reproduciendo '{query}' en Spotify."

    elif action == "pause":
        if not _focus_spotify():
            if not _launch_spotify():
                return "No pude abrir Spotify."
        pyautogui.press("space")
        if speak:
            speak("Pausado, senor.")
        return "Spotify pausado."

    elif action == "resume":
        if not _focus_spotify():
            if not _launch_spotify():
                return "No pude abrir Spotify."
        pyautogui.press("space")
        if speak:
            speak("Reanudado, senor.")
        return "Spotify reanudado."

    elif action == "next":
        if not _focus_spotify():
            return "Spotify no esta abierto."
        pyautogui.hotkey("ctrl", "right")
        return "Siguiente cancion."

    elif action == "previous":
        if not _focus_spotify():
            return "Spotify no esta abierto."
        pyautogui.hotkey("ctrl", "left")
        return "Cancion anterior."

    elif action == "volume_up":
        if not _focus_spotify():
            if not _launch_spotify():
                return "No pude abrir Spotify."
        for _ in range(3):
            pyautogui.hotkey("ctrl", "up")
            time.sleep(0.05)
        return "Volumen subido."

    elif action == "volume_down":
        if not _focus_spotify():
            if not _launch_spotify():
                return "No pude abrir Spotify."
        for _ in range(3):
            pyautogui.hotkey("ctrl", "down")
            time.sleep(0.05)
        return "Volumen bajado."

    return f"Accion desconocida: {action}"
