import subprocess
import time
import shutil
import urllib.parse

import pyautogui
import pygetwindow as gw
import pyperclip


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
    exe = shutil.which("spotify") or shutil.which("Spotify")
    if exe:
        try:
            subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            return _focus_spotify()
        except Exception:
            pass
    try:
        subprocess.Popen(["start", "Spotify:"], shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        if _focus_spotify():
            return True
    except Exception:
        pass
    try:
        pyautogui.press("win")
        time.sleep(0.7)
        pyautogui.write("Spotify", interval=0.05)
        time.sleep(0.9)
        pyautogui.press("enter")
        time.sleep(3)
        return _focus_spotify()
    except Exception:
        return False


def _ensure_spotify() -> bool:
    if _focus_spotify():
        return True
    return _launch_spotify()


def _play_via_search(query: str) -> bool:
    """
    Busca y reproduce una cancion/artista en Spotify.
    Retorna True si se logro, False si fallo.
    """
    # Ctrl+L foco en la barra de busqueda
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.3)

    # Seleccionar todo y borrar
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)

    # Escribir query
    pyperclip.copy(query)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)

    # Enter para buscar
    pyautogui.press("enter")
    time.sleep(1.5)

    # Intentar reproducir el primer resultado:
    # Metodo 1: Enter de nuevo (a veces el primer resultado ya esta seleccionado)
    pyautogui.press("enter")
    time.sleep(0.5)

    # Verificar si se reprodujo (la ventana cambia de titulo/estado)
    # Metodo 2: Si no funciono, intentar Down + Enter
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.5)

    return True


def _play_via_spotify_uri(query: str) -> bool:
    """
    Metodo alternativo: usa el URI de Spotify para abrir busqueda
    y reproducir desde ahi.
    """
    search_uri = f"spotify:search:{urllib.parse.quote(query)}"

    try:
        subprocess.Popen(
            ["powershell", "-Command", f"Start-Process '{search_uri}'"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)
        if _focus_spotify():
            time.sleep(1)
            # Down + Enter para seleccionar primer resultado
            pyautogui.press("down")
            time.sleep(0.3)
            pyautogui.press("enter")
            return True
    except Exception:
        pass
    return False


def spotify_control(parameters: dict, player=None, speak=None) -> str:
    action = parameters.get("action", "play")
    query = parameters.get("query", "")

    if action == "play":
        if not query:
            return "Necesito el nombre de la cancion o artista para buscar."

        if not _ensure_spotify():
            return "No pude abrir Spotify. Asegurate de que este instalado."

        # Metodo principal: busqueda por teclado
        try:
            _play_via_search(query)
            if speak:
                speak(f"Reproduciendo {query} en Spotify, señor.")
            return f"Reproduciendo '{query}' en Spotify."
        except Exception as e:
            # Fallback: URI de Spotify
            try:
                success = _play_via_spotify_uri(query)
                if success:
                    if speak:
                        speak(f"Reproduciendo {query} en Spotify, señor.")
                    return f"Reproduciendo '{query}' en Spotify."
                else:
                    return f"No se pudo reproducir '{query}'. Spotify esta abierto pero no se pudo ejecutar la busqueda automatica."
            except Exception:
                return f"Error al reproducir en Spotify: {str(e)[:200]}"

    elif action == "pause":
        if not _focus_spotify():
            if not _launch_spotify():
                return "No pude abrir Spotify."
        pyautogui.press("space")
        if speak:
            speak("Pausado, señor.")
        return "Spotify pausado."

    elif action == "resume":
        if not _focus_spotify():
            if not _launch_spotify():
                return "No pude abrir Spotify."
        pyautogui.press("space")
        if speak:
            speak("Reanudado, señor.")
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
