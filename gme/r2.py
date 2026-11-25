"""Temporary public copies of videos live in Cloudflare R2; this removes the old ones.

Postiz uploads each video there so platforms can download it. The engine keeps the originals, so a copy is
only needed around the time of posting. Only .mp4 files are ever deleted: channel pictures stay.
Talks to R2's S3 API with a standard-library AWS Signature V4.
"""
from __future__ import annotations

import hashlib
import hmac
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Callable

NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
Transport = Callable[[str, str, dict], bytes]          # (method, url, headers) -> body


def _http(method: str, url: str, headers: dict) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method=method), timeout=60) as r:  # noqa: S310
        return r.read()


def sign(method: str, host: str, path: str, query: dict, key_id: str, secret: str, now: datetime,
         region: str = "auto") -> tuple[str, dict]:
    stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    empty = hashlib.sha256(b"").hexdigest()
    qs = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(str(v), safe='-_.~')}" for k, v in sorted(query.items()))
    uri = urllib.parse.quote(path, safe="/-_.~")
    signed = "host;x-amz-content-sha256;x-amz-date"
    canonical = f"{method}\n{uri}\n{qs}\nhost:{host}\nx-amz-content-sha256:{empty}\nx-amz-date:{stamp}\n\n{signed}\n{empty}"
    scope = f"{day}/{region}/s3/aws4_request"
    to_sign = f"AWS4-HMAC-SHA256\n{stamp}\n{scope}\n{hashlib.sha256(canonical.encode()).hexdigest()}"
    k = f"AWS4{secret}".encode()
    for part in (day, region, "s3", "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers = {"x-amz-content-sha256": empty, "x-amz-date": stamp,
               "Authorization": f"AWS4-HMAC-SHA256 Credential={key_id}/{scope}, SignedHeaders={signed}, Signature={sig}"}
    return f"https://{host}{uri}" + (f"?{qs}" if qs else ""), headers


class Media:
    def __init__(self, account_id: str, key_id: str, secret: str, bucket: str, transport: Transport = _http):
        self.host, self.bucket = f"{account_id}.r2.cloudflarestorage.com", bucket
        self.key_id, self.secret, self._call = key_id, secret, transport

    def _request(self, method: str, path: str, query: dict, now: datetime) -> bytes:
        url, headers = sign(method, self.host, path, query, self.key_id, self.secret, now)
        return self._call(method, url, headers)

    def objects(self, now: datetime) -> list[tuple[str, datetime]]:
        out, token = [], None
        while True:
            query = {"list-type": "2", **({"continuation-token": token} if token else {})}
            root = ET.fromstring(self._request("GET", f"/{self.bucket}", query, now))
            for c in root.iter(f"{NS}Contents"):
                when = datetime.fromisoformat(c.findtext(f"{NS}LastModified").replace("Z", "+00:00"))
                out.append((c.findtext(f"{NS}Key"), when))
            token = root.findtext(f"{NS}NextContinuationToken")
            if not token:
                return out

    def prune(self, now: datetime | None = None, days: int = 7) -> list[str]:
        """Delete videos older than `days`; returns what was removed."""
        now = now or datetime.now(timezone.utc)
        old = [k for k, when in self.objects(now) if k.lower().endswith(".mp4") and now - when > timedelta(days=days)]
        for key in old:
            self._request("DELETE", f"/{self.bucket}/{key}", {}, now)
        return old


def from_secrets(sec: dict) -> Media | None:
    names = ("CLOUDFLARE_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    return Media(*(sec[n] for n in names)) if all(sec.get(n) for n in names) else None
