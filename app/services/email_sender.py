from __future__ import annotations

import logging
from typing import Protocol

import httpx

_logger = logging.getLogger("auth")


class EmailSender(Protocol):
    def send_magic_link(self, *, to: str, link: str) -> None: ...


class ConsoleEmailSender:
    def send_magic_link(self, *, to: str, link: str) -> None:
        message = f"magic link for {to}: {link}"
        _logger.info(message)
        print(message)


class ResendEmailSender:
    def __init__(self, api_key: str, from_addr: str) -> None:
        if not api_key:
            raise RuntimeError("RESEND_API_KEY is empty")
        self._api_key = api_key
        self._from_addr = from_addr

    def send_magic_link(self, *, to: str, link: str) -> None:
        if not self._api_key:
            raise RuntimeError("RESEND_API_KEY is empty")
        payload = {
            "from": self._from_addr,
            "to": [to],
            "subject": "Your maintenance-calendar sign-in link",
            "html": (
                f'<p>Click to sign in: <a href="{link}">{link}</a></p>'
                "<p>This link expires in 15 minutes.</p>"
            ),
            "text": f"Sign in: {link}\nThis link expires in 15 minutes.",
        }
        response = httpx.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        response.raise_for_status()


def build_email_sender(
    backend: str, *, api_key: str, from_addr: str
) -> EmailSender:
    backend_norm = backend.strip().lower()
    if backend_norm == "resend":
        return ResendEmailSender(api_key=api_key, from_addr=from_addr)
    return ConsoleEmailSender()
