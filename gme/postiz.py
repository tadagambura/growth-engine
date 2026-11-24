"""Postiz publisher: uploads the video, then creates the post on the platform's channel.

Follows the Postiz public API (docs read 24 Nov 2026): POST /upload (multipart) returns {id, path};
POST /posts takes {type, date, shortLink, tags, posts:[{integration:{id}, value:[{content, image:[{id,path}]}],
settings:{__type,...}}]} and returns [{postId, integration}]. The API key is sent raw in the Authorization
header. Everything network-facing goes through an injectable transport so it is tested without a server.
"""
from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .queue import Post

Transport = Callable[..., object]            # (method, path, json=None, file=None) -> parsed JSON


class PostizError(RuntimeError):
    pass


def http_transport(base_url: str, api_key: str) -> Transport:
    def call(method: str, path: str, json_body=None, file: Path | None = None):
        url = base_url.rstrip("/") + path
        headers = {"Authorization": api_key}
        data = None
        if file is not None:                           # multipart upload
            boundary = uuid.uuid4().hex
            ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file.name}\"\r\n"
                    f"Content-Type: {ctype}\r\n\r\n").encode() + file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310 (owner's own Postiz host)
                body = r.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            raise PostizError(f"{method} {path} -> HTTP {e.code}: {e.read()[:300]!r}") from None
    return call


def title_of(text: str, limit: int) -> str:
    first = text.strip().splitlines()[0] if text.strip() else "Kaotic Chainz"
    return first[:limit].strip() or "Kaotic Chainz"


def settings_for(platform: str, post: Post, cfg: dict) -> dict:
    s = {"__type": platform}
    if platform == "tiktok":
        s.update(title=title_of(post.text, 90), privacy_level="PUBLIC_TO_EVERYONE", duet=False, stitch=False, comment=True,
                 autoAddMusic="no", brand_content_toggle=False, brand_organic_toggle=False,
                 content_posting_method=cfg.get("tiktok_method", "DIRECT_POST"), video_made_with_ai=False)
    elif platform == "instagram":
        s.update(post_type="post")                       # one video as a post publishes as a Reel
    elif platform == "youtube":
        t = title_of(post.text, 100)
        s.update(title=t if len(t) >= 2 else "Kaotic Chainz", type=cfg.get("youtube_visibility", "public"), selfDeclaredMadeForKids="no")
    elif platform == "x":
        s.update(who_can_reply_post="everyone")
    elif platform == "pinterest":
        if not cfg.get("pinterest_board"):
            raise PostizError("pinterest needs pinterest_board in configs/postiz.json")
        s.update(board=cfg["pinterest_board"], title=title_of(post.text, 100))
    return s                                             # facebook, threads, bluesky need only __type


class PostizPublisher:
    def __init__(self, cfg: dict, transport: Transport):
        self.cfg, self._call = cfg, transport
        self._media: dict[str, dict] = {}               # upload each video once, reuse for every platform

    def _upload(self, path: str) -> dict:
        if path not in self._media:
            res = self._call("POST", "/upload", file=Path(path))
            if not isinstance(res, dict) or "id" not in res or "path" not in res:
                raise PostizError(f"unexpected upload response: {str(res)[:200]}")
            self._media[path] = {"id": res["id"], "path": res["path"]}
        return self._media[path]

    def publish(self, post: Post) -> str:
        channel = self.cfg.get("integrations", {}).get(post.platform, "")
        if not channel:
            raise PostizError(f"no Postiz channel id for {post.platform} in configs/postiz.json")
        if not post.media:
            raise PostizError("post has no video")
        media = self._upload(post.media)
        send = self.cfg.get("send", "now")
        body = {"type": send, "date": post.scheduled_for.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "shortLink": False, "tags": [],
                "posts": [{"integration": {"id": channel}, "value": [{"content": post.text, "image": [media]}],
                           "settings": settings_for(post.platform, post, self.cfg)}]}
        res = self._call("POST", "/posts", json_body=body)
        if not isinstance(res, list) or not res or "postId" not in res[0]:
            raise PostizError(f"unexpected create-post response: {str(res)[:200]}")
        return str(res[0]["postId"])

    def channels(self) -> list[dict]:
        return list(self._call("GET", "/integrations"))

    def delete(self, post_id: str) -> None:
        try:
            self._call("DELETE", f"/posts/{post_id}")
        except PostizError as e:
            if "HTTP 404" not in str(e):                 # 404 means already deleted
                raise
