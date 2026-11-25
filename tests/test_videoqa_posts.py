import shutil
import subprocess
from pathlib import Path

import pytest

from gme.config import load
from gme.planner import load_json
from gme.posts import build_post, hashtags, tracked_link, fit
from gme.scriptwriter import BeatText, Script, cta_text
from gme.videoqa import check_file, check_script

ROOT = Path(__file__).resolve().parent.parent
CONTENT = load_json(ROOT / "configs/content.json")
FORMATS = {f["id"]: f for f in load_json(ROOT / "configs/formats.json")["formats"]}
CFG = load(ROOT / "configs/apps/stackup.json")


def script(**over):
    fmt = FORMATS["explainer"]
    beats = [BeatText(b["beat"], f"{b['beat']} line." if b["beat"] != "cta" else cta_text(CONTENT, "waitlist", "StackUp"),
                      tuple(b["acts"]), b["layout"], float(b["seconds"])) for b in fmt["beats"]]
    return Script("explainer", "stackup:feature-01", over.get("beats", beats), "A caption. Nice.", "A title", "model")


def test_script_checks_pass_and_catch_missing_beats_double_cta_and_bad_words():
    cta = cta_text(CONTENT, "waitlist", "StackUp")
    assert check_script(script(), FORMATS["explainer"], CFG, cta) == []
    s = script()
    assert any("do not match" in p for p in check_script(Script(**{**s.__dict__, "beats": s.beats[:-1]}), FORMATS["explainer"], CFG, cta))
    s2 = script(); s2.beats[1] = BeatText("problem", "Guaranteed to get rich", (), "stage", 5)
    assert any("banned" in p for p in check_script(s2, FORMATS["explainer"], CFG, cta))
    s3 = script(); s3.beats[0] = BeatText("hook", "", (), "stage", 3)
    assert any("no text" in p for p in check_script(s3, FORMATS["explainer"], CFG, cta))


def test_posts_have_one_cta_a_tracked_link_and_at_most_three_hashtags():
    s = script()
    x = build_post("x", s, CFG, "2026-12-01", "Join the waitlist.")
    assert len(x) <= 280 and "utm_source=x" in x and "utm_content=2026-12-01" in x
    assert len([w for w in x.split() if w.startswith("#")]) <= CFG.hashtags_max
    tt = build_post("tiktok", s, CFG, "2026-12-01", "Join the waitlist. Link in bio.")
    assert "http" not in tt and "Join the waitlist" in tt
    long = Script(**{**s.__dict__, "caption": "word " * 200})
    assert len(build_post("x", long, CFG, "2026-12-01", "Join the waitlist.")) <= 280
    assert tracked_link(CFG, "reddit", "d1").startswith("https://kaoticchainz.com/stackup?utm_source=reddit")
    assert hashtags(CFG).startswith("#StackUp")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_file_checks_catch_wrong_size_blank_and_short_videos(tmp_path):
    bad = tmp_path / "bad.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=white:s=640x360:d=3", "-pix_fmt", "yuv420p",
                    str(bad)], check=True)
    problems = check_file(bad, voiced=False, min_s=15, max_s=60)
    assert problems     # too small, wrong size or short
    assert check_file(tmp_path / "missing.mp4", False, 15, 60) == ["video file is missing or too small"]
    good = tmp_path / "good.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=20", "-f", "lavfi", "-i",
                    "sine=frequency=300:duration=20", "-c:v", "libx264", "-b:v", "2M", "-pix_fmt", "yuv420p", "-shortest", str(good)], check=True)
    assert check_file(good, voiced=False, min_s=15, max_s=60) == []


def test_a_long_caption_ends_on_a_whole_sentence():
    assert fit("First one. Second one is much longer than that.", 20) == "First one."
    assert fit("One single sentence that cannot possibly fit", 20).endswith("\u2026")
