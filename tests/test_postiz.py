import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gme.postiz import PostizError, PostizPublisher, settings_for, title_of
from gme.queue import Post

CFG = {"integrations": {"tiktok": "ch-tt", "youtube": "ch-yt", "x": "ch-x", "pinterest": "ch-pin", "bluesky": "ch-bs", "instagram": "ch-ig",
                        "facebook": "ch-fb", "threads": "ch-th"}, "pinterest_board": "board-1", "send": "now"}


def post(platform="x", media="/tmp/v.mp4", text="Hook line\n\nBody #Tag"):
    return Post(1, "stackup", platform, text, media, datetime(2026, 12, 1, 17, 30, tzinfo=timezone.utc), "approved", (), None, None)


class Fake:
    def __init__(self):
        self.calls = []

    def __call__(self, method, path, json_body=None, file=None):
        self.calls.append((method, path, json_body, file))
        if path == "/upload":
            return {"id": "m1", "path": "https://cdn.example/v.mp4", "status": "ready"}
        if path == "/posts":
            return [{"postId": "p-9", "integration": json_body["posts"][0]["integration"]["id"]}]
        if path == "/integrations":
            return [{"id": "ch-x", "identifier": "x"}]
        return {}


def test_video_is_uploaded_once_then_posted_to_each_channel_with_the_right_settings(tmp_path):
    video = tmp_path / "v.mp4"; video.write_bytes(b"v")
    f = Fake(); pub = PostizPublisher(CFG, f)
    ids = [pub.publish(post(p, str(video))) for p in ("x", "tiktok", "youtube")]
    assert ids == ["p-9"] * 3
    assert [c[1] for c in f.calls].count("/upload") == 1                       # one upload, reused
    body = next(c[2] for c in f.calls if c[1] == "/posts" and c[2]["posts"][0]["integration"]["id"] == "ch-tt")
    assert body["type"] == "now" and body["date"] == "2026-12-01T17:30:00.000Z" and body["shortLink"] is False
    item = body["posts"][0]
    assert item["value"][0]["image"] == [{"id": "m1", "path": "https://cdn.example/v.mp4"}]
    assert item["settings"]["__type"] == "tiktok" and item["settings"]["privacy_level"] == "PUBLIC_TO_EVERYONE"
    assert item["settings"]["content_posting_method"] == "DIRECT_POST"
    yt = next(c[2] for c in f.calls if c[1] == "/posts" and c[2]["posts"][0]["integration"]["id"] == "ch-yt")["posts"][0]["settings"]
    assert yt["title"] == "Hook line" and yt["type"] == "public" and yt["selfDeclaredMadeForKids"] == "no"


def test_missing_channel_board_media_or_bad_response_raise_clear_errors(tmp_path):
    with pytest.raises(PostizError, match="no Postiz channel id"):
        PostizPublisher({"integrations": {}}, Fake()).publish(post("x", "a.mp4"))
    with pytest.raises(PostizError, match="no video"):
        PostizPublisher(CFG, Fake()).publish(post("x", None))
    with pytest.raises(PostizError, match="pinterest_board"):
        settings_for("pinterest", post("pinterest"), {})
    with pytest.raises(PostizError, match="unexpected upload"):
        PostizPublisher(CFG, lambda *a, **k: {}).publish(post("x", str(tmp_path / "v.mp4")))


def test_titles_and_simple_platform_settings():
    assert title_of("A" * 200, 90) == "A" * 90 and title_of("", 90) == "Kaotic Chainz"
    assert settings_for("bluesky", post("bluesky"), CFG) == {"__type": "bluesky"}
    assert settings_for("instagram", post("instagram"), CFG)["post_type"] == "post"
    assert settings_for("x", post("x"), CFG)["who_can_reply_post"] == "everyone"


def test_channels_and_delete_treat_404_as_already_gone():
    f = Fake(); pub = PostizPublisher(CFG, f)
    assert pub.channels()[0]["identifier"] == "x"

    def gone(*a, **k):
        raise __import__("gme.postiz", fromlist=["PostizError"]).PostizError("DELETE /posts/1 -> HTTP 404: b''")
    PostizPublisher(CFG, gone).delete("1")


def test_the_shipped_config_is_off_until_postiz_is_connected():
    cfg = json.loads((Path(__file__).resolve().parent.parent / "configs/postiz.json").read_text())
    assert cfg["enabled"] is False and set(cfg["integrations"]) == {"tiktok", "instagram", "youtube", "facebook", "threads", "bluesky", "x", "pinterest"}
