"""The key-entry script, run for real against a throwaway secrets file."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "deploy/n95/set-keys.sh"


def run(tmp_path, typed, *keys):
    secrets = tmp_path / "secrets.env"
    if not secrets.exists():
        secrets.write_text("DOMAIN=example.com\nYOUTUBE_CLIENT_ID=\nKEEP=me=too\n")
    env = {**os.environ, "KEYS_FILE": str(secrets), "SKIP_N95": "1"}
    result = subprocess.run(["bash", str(SCRIPT), *keys], input=typed, env=env, capture_output=True, text=True, timeout=30)
    return result, secrets


def test_keys_replace_or_add_lines_and_leave_the_rest(tmp_path):
    result, secrets = run(tmp_path, "  abc-123.apps.example \nS3cret_x\n", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET")
    assert result.returncode == 0, result.stderr
    lines = secrets.read_text().splitlines()
    assert sorted(lines) == sorted(["DOMAIN=example.com", "KEEP=me=too", "YOUTUBE_CLIENT_ID=abc-123.apps.example",
                                    "YOUTUBE_CLIENT_SECRET=S3cret_x"])
    assert "S3cret_x" not in result.stdout + result.stderr
    assert secrets.stat().st_mode & 0o777 == 0o600


def test_enter_keeps_the_old_value(tmp_path):
    result, secrets = run(tmp_path, "\n", "YOUTUBE_CLIENT_ID")
    assert result.returncode == 0 and "nothing changed" in result.stdout
    assert secrets.read_text() == "DOMAIN=example.com\nYOUTUBE_CLIENT_ID=\nKEEP=me=too\n"


def test_something_that_is_not_a_key_changes_nothing(tmp_path):
    result, secrets = run(tmp_path, "good123\nbad'; rm -rf x\n", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET")
    assert result.returncode == 1
    assert "good123" not in secrets.read_text()
