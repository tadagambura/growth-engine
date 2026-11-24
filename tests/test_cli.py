import json
from datetime import date

from gme import cli


def test_pause_resume_and_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GME_HOME", str(tmp_path))
    assert cli.main(["status"]) == 0
    assert json.loads(capsys.readouterr().out)["paused"] is False
    cli.main(["pause"])
    capsys.readouterr()
    assert cli.is_paused(tmp_path)
    cli.main(["status"])
    assert json.loads(capsys.readouterr().out)["paused"] is True
    cli.main(["resume"])
    assert not cli.is_paused(tmp_path)


def test_costume_command_and_apps_are_listed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GME_HOME", str(tmp_path))
    cli.main(["costume", "--date", "2027-01-02"])
    assert json.loads(capsys.readouterr().out)["costume"] == "newyear"
    s = cli.status(tmp_path, date(2026, 12, 1))
    assert set(s["apps"]) >= {"stackup", "loopday"} and s["costume"] == "christmas"


def test_voice_commands_exist_and_refuse_without_a_chosen_voice(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GME_HOME", str(tmp_path))
    import gme.voice as voice
    monkeypatch.setattr(voice, "make_client", lambda *_: object())     # no network, no key needed
    assert cli.main(["voice", "say", "hello", "--out", str(tmp_path / "x.mp3")]) == 1
    assert "no voice chosen" in capsys.readouterr().err
