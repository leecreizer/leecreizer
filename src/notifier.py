"""알림: 콘솔 출력 + (설정 시) 텔레그램 전송."""
from __future__ import annotations

import datetime

import requests


class Notifier:
    def __init__(self, telegram_token: str = "", telegram_chat_id: str = ""):
        self.token = telegram_token
        self.chat_id = telegram_chat_id

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, message: str) -> None:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {message}", flush=True)
        if not self.telegram_enabled:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": message},
                timeout=5,
            )
        except requests.RequestException as e:
            print(f"[notifier] telegram 전송 실패: {e}", flush=True)
