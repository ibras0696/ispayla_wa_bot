from __future__ import annotations

from typing import Iterable, Sequence

import logging
import requests

from ...config import get_settings


class WhatsKeyboardClient:
    """Мини-клиент для отправки интерактивных кнопок Green API."""

    def __init__(self, base_url: str, api_token: str, id_instance: str):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.id_instance = id_instance

    def __call__(
        self,
        chat_id: str,
        body: str,
        buttons: Sequence[str | dict],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict:
        payload = {
            "chatId": chat_id,
            "body": body,
            "buttons": self._build_buttons(buttons),
        }
        if header:
            payload["header"] = header
        if footer:
            payload["footer"] = footer

        url = (
            f"{self.base_url}"
            f"/waInstance{self.id_instance}"
            f"/sendInteractiveButtonsReply/{self.api_token}"
        )
        resp = requests.post(
            url=url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        logging.debug("WA keyboard response: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _build_buttons(buttons: Iterable[str | dict]) -> list[dict]:
        built: list[dict] = []
        for index, button in enumerate(buttons, start=1):
            if isinstance(button, dict):
                button_id = str(button.get("buttonId") or index)
                text = button.get("buttonText") or ""
            else:
                button_id = str(index)
                text = str(button)
            built.append({"buttonId": button_id, "buttonText": text})
        return built


settings = get_settings()
keyboard_sender = WhatsKeyboardClient(
    base_url=settings.base_url,
    api_token=settings.api_token,
    id_instance=settings.id_instance,
)
