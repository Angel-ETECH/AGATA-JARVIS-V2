import json
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from core.paths import BASE_DIR
from core.logging import get_logger

log = get_logger("jarvis.email")

CONFIG_FILE = BASE_DIR / "config" / "email_config.json"

GMAIL_IMAP = "imap.gmail.com"
GMAIL_SMTP = "smtp.gmail.com"
OUTLOOK_IMAP = "outlook.office365.com"
OUTLOOK_SMTP = "smtp.office365.com"


def _load_email_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_email_config(config: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _read_emails(imap_server: str, email_addr: str, password: str, limit: int = 5) -> str:
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_addr, password)
        mail.select("INBOX")

        status, messages = mail.search(None, "ALL")
        if status != "OK":
            return "No se pudo acceder a los correos."

        msg_ids = messages[0].split()
        recent = msg_ids[-limit:] if len(msg_ids) > limit else msg_ids

        lines = [f"Ultimos {len(recent)} correos:\n"]
        for mid in reversed(recent):
            status, data = mail.fetch(mid, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(data[0][1])
            subject = msg.get("Subject", "Sin asunto")
            sender = msg.get("From", "Desconocido")
            date = msg.get("Date", "")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")[:200]
                        except Exception:
                            body = "[No se pudo leer]"
                        break
            else:
                try:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:200]
                except Exception:
                    body = "[No se pudo leer]"

            lines.append(f"De: {sender}")
            lines.append(f"Asunto: {subject}")
            lines.append(f"Fecha: {date}")
            lines.append(f"{body.strip()}...")
            lines.append("---")

        mail.logout()
        return "\n".join(lines)
    except Exception as e:
        return f"Error al leer correos: {e}"


def _send_email(smtp_server: str, port: int, email_addr: str, password: str,
                 to: str, subject: str, body: str) -> str:
    try:
        msg = MIMEMultipart()
        msg["From"] = email_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(email_addr, password)
        server.sendmail(email_addr, to, msg.as_string())
        server.quit()
        return f"Correo enviado a {to}: '{subject}'"
    except Exception as e:
        return f"Error al enviar correo: {e}"


def email_manager(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "read")

    config = _load_email_config()

    if action == "setup":
        config["email"] = p.get("email", "")
        config["password"] = p.get("password", "")
        config["provider"] = p.get("provider", "gmail")
        _save_email_config(config)
        return "Configuracion de email guardada, senor."

    if not config.get("email") or not config.get("password"):
        return (
            "No hay cuenta de email configurada. Usa:\n"
            "email_manager(action='setup', email='tu@email.com', password='...', provider='gmail')"
        )

    email_addr = config["email"]
    password = config["password"]
    provider = config.get("provider", "gmail").lower()

    if provider == "outlook":
        imap_server = OUTLOOK_IMAP
        smtp_server = OUTLOOK_SMTP
    else:
        imap_server = GMAIL_IMAP
        smtp_server = GMAIL_SMTP

    if action == "read":
        limit = int(p.get("limit", 5))
        return _read_emails(imap_server, email_addr, password, limit)

    elif action == "send":
        to = p.get("to", "")
        subject = p.get("subject", "Sin asunto")
        body = p.get("body", "")
        if not to:
            return "Necesito el destinatario (to)."
        return _send_email(smtp_server, 587, email_addr, password, to, subject, body)

    elif action == "status":
        return f"Email configurado: {email_addr} ({provider})"

    else:
        return f"Accion desconocida: {action}. Usa: read, send, setup, status"
