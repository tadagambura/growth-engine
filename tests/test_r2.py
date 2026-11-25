from datetime import datetime, timezone

from gme import r2

NOW = datetime(2026, 12, 20, tzinfo=timezone.utc)
LIST = b"""<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
<Contents><Key>old.mp4</Key><LastModified>2026-12-01T00:00:00.000Z</LastModified></Contents>
<Contents><Key>new.mp4</Key><LastModified>2026-12-18T00:00:00.000Z</LastModified></Contents>
<Contents><Key>avatar.webp</Key><LastModified>2026-11-01T00:00:00.000Z</LastModified></Contents>
</ListBucketResult>"""


def test_only_old_videos_are_deleted():
    calls = []

    def fake(method, url, headers):
        calls.append((method, url))
        assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=id/20261220/auto/s3/")
        return LIST if method == "GET" else b""

    assert r2.Media("acc", "id", "secret", "b", fake).prune(NOW) == ["old.mp4"]
    assert [c for c in calls if c[0] == "DELETE"] == [("DELETE", "https://acc.r2.cloudflarestorage.com/b/old.mp4")]


def test_no_settings_means_no_cleanup():
    assert r2.from_secrets({"R2_BUCKET": "b"}) is None
