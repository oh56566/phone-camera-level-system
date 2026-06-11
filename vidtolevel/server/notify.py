from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscordNotifier:
    webhook_url: str | None = None

    def send(self, content: str) -> None:
        if not self.webhook_url:
            return
        payload = json.dumps({"content": content}).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()

