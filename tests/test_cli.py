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
