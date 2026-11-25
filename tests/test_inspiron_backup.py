"""The off-machine backup script, run for real against stand-ins for rsync and ssh."""
import os
import shutil
import socket
import subprocess
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "deploy/n95/inspiron-backup.sh"
pytestmark = pytest.mark.skipif(not shutil.which("openssl"), reason="needs openssl")


@pytest.fixture
def site(tmp_path):
    gme, bin_dir, remote = tmp_path / "gme", tmp_path / "bin", tmp_path / "remote"
    for d in (gme / "data/videos", gme / "backups/2026-11-24", gme / "backups/2026-11-25", bin_dir, remote):
        d.mkdir(parents=True)
    (gme / "data/videos/a.mp4").write_text("video")
    (gme / "data/history.json").write_text("{}")
    (gme / "data/queue.db").write_text("queue")
    (gme / "secrets.env").write_text("SECRET=very-private\n")
    (gme / "generated.env").write_text("X=1\n")
    for name in ("postiz.dump", "gme.dump"):
        (gme / "backups/2026-11-24" / name).write_text("old")
        (gme / "backups/2026-11-25" / name).write_text("new " + name)
    # rsync stand-in: copy the source folder into remote/<destination folder>
    (bin_dir / "rsync").write_text(f'#!/bin/bash\nsrc="${{@: -2:1}}"; dst="${{@: -1}}"; mkdir -p "{remote}/${{dst#*:}}"; cp -r "$src." "{remote}/${{dst#*:}}"\n')
    (bin_dir / "ssh").write_text(f'#!/bin/sh\necho "$@" >> "{remote}/ssh.log"\n')
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "GME_HOME": str(gme), "BACKUP_HOST": "127.0.0.1",
           "BACKUP_PORT": str(server.getsockname()[1]), "HOME": str(tmp_path)}
    yield tmp_path, gme, remote, env
    server.close()


def make_cert(tmp, gme):
    key = tmp / "k.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=t",
                    "-keyout", str(key), "-out", str(gme / "backup-cert.pem")], check=True, capture_output=True)
    return key


def run(env):
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)


def test_without_a_certificate_only_videos_are_copied_and_it_says_so(site):
    _, _, remote, env = site
    result = run(env)
    assert result.returncode == 0, result.stderr
    assert (remote / "videos/a.mp4").exists()
    assert not (remote / "state").exists()
    assert "NOT copied" in result.stdout


def test_state_is_encrypted_and_restores_with_the_private_key(site):
    tmp, gme, remote, env = site
    key = make_cert(tmp, gme)
    result = run(env)
    assert result.returncode == 0, result.stderr
    [copy] = list((remote / "state").glob("gme-state-*.cms"))
    assert b"very-private" not in copy.read_bytes()
    plain = tmp / "plain.tar.gz"
    subprocess.run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER", "-in", str(copy), "-inkey", str(key),
                    "-out", str(plain)], check=True, capture_output=True)
    with tarfile.open(plain) as tar:
        names = set(tar.getnames())
        assert tar.extractfile("secrets.env").read() == b"SECRET=very-private\n"
        assert tar.extractfile("backups/2026-11-25/postiz.dump").read() == b"new postiz.dump"
    assert {"generated.env", "data/history.json", "data/queue.db", "backups/2026-11-25/gme.dump"} <= names
    assert not any("2026-11-24" in n or n.endswith(".mp4") for n in names)
    # the Inspiron was already on, so it is left on
    assert not (remote / "ssh.log").exists()


def test_a_missing_database_dump_fails_loudly(site):
    tmp, gme, remote, env = site
    make_cert(tmp, gme)  # a good certificate, so only the empty dump can be the cause
    (gme / "backups/2026-11-25/postiz.dump").write_text("")
    result = run(env)
    assert result.returncode == 1
    assert "no complete database dump" in result.stdout
    assert (remote / "videos/a.mp4").exists()
    assert not (remote / "state").exists()
