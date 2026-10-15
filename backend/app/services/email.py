"""Real email over SMTP (opt-in). Empty config -> ``email_enabled`` false."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def is_configured() -> bool:
    return bool(settings.email_enabled)


def _send_sync(to_address: str, subject: str, body_text: str) -> bool:
    if not is_configured():
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_address
    msg.set_content(body_text)

    host = settings.smtp_host
    port = settings.smtp_port
    username = settings.smtp_username
    password = settings.smtp_password
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                if settings.smtp_use_tls:
                    server.starttls()
                    server.ehlo()
                if username:
                    server.login(username, password)
                server.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 - mail send must never crash the request
        logger.warning("SMTP send to %s failed: %s", to_address, exc)
        return False


async def send_email(to_address: str, subject: str, body_text: str) -> bool:
    """Send mail in a worker thread so the event loop is not blocked."""
    if not is_configured():
        logger.info("Email not configured; skipping send to %s", to_address)
        return False
    return await asyncio.to_thread(_send_sync, to_address, subject, body_text)
