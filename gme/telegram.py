"""Telegram alerts and approvals (Bot API over HTTPS, standard library only).

Security: only messages from the owner's chat are ever acted on. Anything else is ignored,
so a stranger who finds the bot can't approve a post. The bot token never appears in repr or logs.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Callable

from .queue import Post

Transport = Callable[[str, dict], dict]


def _http(token: str) -> Transport:
    def call(method: str, payload: dict) -> dict:
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
                                     data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https host)
            return json.loads(r.read())
    return call


class TelegramBot:
    def __init__(self, token: str, chat_id: int, transport: Transport | None = None):
        self._chat_id = int(chat_id)
        self._call = transport or _http(token)

    def __repr__(self) -> str:
        return f"TelegramBot(chat_id={self._chat_id})"

    def send(self, text: str) -> dict:
        return self._call("sendMessage", {"chat_id": self._chat_id, "text": text[:4000]})

    def request_approval(self, post: Post) -> dict:
        body = (f"Approve this {post.platform} post for {post.app_id}?\n"
                f"Scheduled: {post.scheduled_for:%a %d %b %H:%M} UTC\n\n{post.text}")
        keyboard = {"inline_keyboard": [[{"text": "Approve", "callback_data": f"approve:{post.id}"},
                                         {"text": "Reject", "callback_data": f"reject:{post.id}"}]]}
        return self._call("sendMessage", {"chat_id": self._chat_id, "text": body[:4000], "reply_markup": keyboard})

    def decisions(self, updates: list[dict]) -> list[tuple[str, int]]:
        """Turn getUpdates results into (action, post_id) pairs. Ignores anyone but the owner."""
        out: list[tuple[str, int]] = []
        for u in updates:
            cb = u.get("callback_query")
            if not cb or cb.get("message", {}).get("chat", {}).get("id") != self._chat_id:
                continue
            action, _, raw_id = str(cb.get("data", "")).partition(":")
            if action in {"approve", "reject"} and raw_id.isdigit():
                out.append((action, int(raw_id)))
        return out

    def poll(self, offset: int | None = None) -> tuple[list[dict], int | None]:
        payload: dict = {"timeout": 0, "allowed_updates": ["callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        updates = self._call("getUpdates", payload).get("result", [])
        return updates, (updates[-1]["update_id"] + 1 if updates else offset)


def apply_decisions(bot: TelegramBot, queue, decisions: list[tuple[str, int]], now) -> list[str]:
    """Apply owner decisions to the queue and report back. Stale or repeated taps are reported, not fatal."""
    notes: list[str] = []
    for action, post_id in decisions:
        try:
            post = queue.approve(post_id, now) if action == "approve" else queue.reject(post_id, now)
            notes.append(f"{action}d post {post.id} ({post.app_id}/{post.platform})")
        except Exception as e:
            notes.append(f"could not {action} post {post_id}: {e}")
    if notes:
        bot.send("\n".join(notes))
    return notes
