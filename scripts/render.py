"""Render a whiteboard lesson (lesson.json) to an MP4 with Arabic narration.

Usage:
  python render.py lesson.json -o lesson.mp4            full video
  python render.py lesson.json --preview previews/      one PNG per scene (final state), no audio

Needs: pip install edge-tts imageio-ffmpeg playwright
Browser: uses installed Microsoft Edge (or Chrome) through Playwright.
"""
import argparse
import asyncio
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "assets" / "fonts"
CACHE = HERE.parent / ".tts-cache"

FPS = 30
WIPE = 0.8          # seconds to erase the board between scenes
STEP_GAP = 0.35     # breath after each narrated step
LEAD_IN = 0.15      # pen starts slightly after the voice
END_HOLD = 1.5
RATE = 24000
VALID_TYPES = {"heading", "text", "bullet", "equation", "box", "drawing"}


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


# ---------- validation ----------

def validate(lesson):
    errs = []
    if not lesson.get("scenes"):
        errs.append("lesson has no scenes")
    for si, sc in enumerate(lesson.get("scenes", [])):
        if sc.get("layout", "stack") not in ("stack", "split", "title"):
            errs.append(f"scene {si}: unknown layout {sc.get('layout')}")
        if not sc.get("steps"):
            errs.append(f"scene {si}: no steps")
        for ti, st in enumerate(sc.get("steps", [])):
            shows = st.get("show")
            shows = shows if isinstance(shows, list) else ([shows] if shows else [])
            if not shows and not st.get("say"):
                errs.append(f"scene {si} step {ti}: needs 'say' or 'show'")
            for e in shows:
                if e.get("type") not in VALID_TYPES:
                    errs.append(f"scene {si} step {ti}: bad element type {e.get('type')}")
                elif e["type"] == "drawing":
                    if "<svg" not in e.get("svg", "") or "viewBox" not in e.get("svg", ""):
                        errs.append(f"scene {si} step {ti}: drawing needs an <svg> with a viewBox")
                elif not str(e.get("text", "")).strip():
                    errs.append(f"scene {si} step {ti}: {e['type']} has no text")
    return errs


# ---------- narration ----------

def tts_key(text, voice, rate):
    return hashlib.sha1(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:20]


async def synth_one(text, voice, rate, out_mp3, sem):
    import edge_tts
    err = "empty audio"
    async with sem:
        for attempt in range(4):
            try:
                await edge_tts.Communicate(text, voice, rate=rate).save(str(out_mp3))
                if out_mp3.stat().st_size > 0:
                    return
            except Exception as e:  # network hiccups are common; retry
                err = e
            await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"TTS failed for: {text[:40]}... ({err})")


def synthesize(texts, voice, rate):
    """Return {text: wav_path} for every narration line, using a local cache."""
    CACHE.mkdir(exist_ok=True)
    jobs, result = [], {}
    for t in set(texts):
        key = tts_key(t, voice, rate)
        wav = CACHE / f"{key}.wav"
        result[t] = wav
        if not wav.exists():
            jobs.append((t, CACHE / f"{key}.mp3", wav))

    async def run():
        sem = asyncio.Semaphore(5)
        await asyncio.gather(*(synth_one(t, voice, rate, mp3, sem) for t, mp3, _ in jobs))

    if jobs:
        print(f"  narration: generating {len(jobs)} lines ...", flush=True)
        asyncio.run(run())
        ff = ffmpeg_exe()
        for _, mp3, wav in jobs:
            subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(mp3), "-ar", str(RATE), "-ac", "1", str(wav)], check=True)
            mp3.unlink(missing_ok=True)
    return result


def wav_seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


# ---------- timing ----------

def natural_duration(e, svg_parts=0):
    if e["type"] == "drawing":
        return min(7.0, max(1.6, 0.55 * max(svg_parts, 3)))
    chars = len(str(e.get("text", ""))) + len(str(e.get("label", "")))
    base = {"heading": 0.055, "equation": 0.09}.get(e["type"], 0.045)
    extra = 0.6 if e["type"] in ("heading", "box") else 0.0
    return min(4.5, max(0.6, chars * base + extra))


def count_svg_parts(svg):
    import re
    return len(re.findall(r"<(path|line|polyline|polygon|circle|ellipse|rect|text)\b", svg))


def build_timeline(lesson, durations):
    """durations: {say_text: seconds}. Returns timeline + audio placements."""
    t = 0.0
    scenes, clips, uid = [], [], 0
    for si, sc in enumerate(lesson["scenes"]):
        start = t
        if si > 0:
            t += WIPE
        events = []
        for st in sc["steps"]:
            say = (st.get("say") or "").strip()
            audio = durations.get(say, 0.0) if say else 0.0
            if say:
                clips.append((t, say))
            shows = st.get("show")
            shows = shows if isinstance(shows, list) else ([shows] if shows else [])
            nat = [natural_duration(e, count_svg_parts(e.get("svg", ""))) for e in shows]
            budget = sum(nat)
            # Keep the drawing inside the sentence when the sentence is long enough.
            if audio > 0 and budget > audio - LEAD_IN:
                f = max(0.45, (audio - LEAD_IN) / budget)
                nat = [max(0.45, d * f) for d in nat]
            cursor = t + (LEAD_IN if audio else 0)
            for e, d in zip(shows, nat):
                events.append({"id": f"e{uid}", "el": e, "start": round(cursor, 3), "dur": round(d, 3)})
                uid += 1
                cursor += d
            t = max(t + audio, cursor) + STEP_GAP + float(st.get("pause", 0))
        t += 0.6  # let the finished board breathe before erasing
        scenes.append({"start": round(start, 3), "events": events})
    total = t + END_HOLD
    return {"scenes": scenes, "total": round(total, 3), "wipe": WIPE}, clips


def mix_audio(clips, wavs, total, out_wav):
    n = int(math.ceil(total * RATE))
    buf = bytearray(n * 2)
    for start, text in clips:
        with wave.open(str(wavs[text])) as w:
            data = w.readframes(w.getnframes())
        off = int(start * RATE) * 2
        end = min(len(buf), off + len(data))
        buf[off:end] = data[: end - off]
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(bytes(buf))


# ---------- page ----------

def write_page(lesson, timeline, workdir):
    html = (HERE / "board.html").read_text(encoding="utf-8")
    html = (html.replace("__FONTS__", FONTS.as_uri())
                .replace("__SCRIPT__", (HERE / "board.js").as_uri())
                .replace("__LESSON__", json.dumps(lesson, ensure_ascii=False))
                .replace("__TIMELINE__", json.dumps(timeline, ensure_ascii=False)))
    page = workdir / "board.html"
    page.write_text(html, encoding="utf-8")
    return page


def open_browser(p):
    for channel in ("msedge", "chrome", None):
        try:
            return p.chromium.launch(channel=channel) if channel else p.chromium.launch()
        except Exception:
            continue
    sys.exit("No Chromium browser found (install Edge/Chrome, or run: playwright install chromium)")


def load(page, path):
    page.goto(path.as_uri())
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(150)
    report = page.evaluate("window.layoutReport()")
    for r in report:
        if r["scale"] < 0.72:
            print(f"  WARNING scene {r['scene']}: content too tall, shrunk to {r['scale']:.0%}. Split this scene.")
    return report


def scene_end(timeline, i):
    sc = timeline["scenes"]
    nxt = sc[i + 1]["start"] if i + 1 < len(sc) else timeline["total"]
    return nxt - 0.05


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lesson")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--preview", default=None, help="folder for per-scene PNGs (fast, no audio)")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--rate", default=None, help='speech rate, e.g. "-5%%"')
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--watermark", default=None, help="name shown bottom-center (default: config.json)")
    args = ap.parse_args()

    lesson_path = Path(args.lesson).resolve()
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    errs = validate(lesson)
    if errs:
        print("lesson.json problems:\n  - " + "\n  - ".join(errs))
        sys.exit(1)

    cfg_path = HERE.parent / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    lesson["watermark"] = args.watermark if args.watermark is not None else lesson.get("watermark", cfg.get("watermark", ""))
    voice = args.voice or lesson.get("voice", "ar-EG-ShakirNeural")
    rate = args.rate or lesson.get("rate", "-4%")
    says = [st["say"].strip() for sc in lesson["scenes"] for st in sc["steps"] if (st.get("say") or "").strip()]

    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if args.preview:
            durations = {s: len(s) * 0.07 for s in says}  # rough; previews show final frames only
            timeline, _ = build_timeline(lesson, durations)
        else:
            print("[1/3] narration", flush=True)
            wavs = synthesize(says, voice, rate)
            durations = {s: wav_seconds(w) for s, w in wavs.items()}
            timeline, clips = build_timeline(lesson, durations)
            mix_audio(clips, wavs, timeline["total"], tmp / "audio.wav")

        page_path = write_page(lesson, timeline, tmp)
        with sync_playwright() as p:
            browser = open_browser(p)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            load(page, page_path)

            if args.preview:
                out = Path(args.preview); out.mkdir(parents=True, exist_ok=True)
                for i in range(len(timeline["scenes"])):
                    page.evaluate(f"window.render({scene_end(timeline, i)})")
                    page.screenshot(path=str(out / f"scene_{i:02d}.png"))
                print(f"previews -> {out}  ({len(timeline['scenes'])} scenes)")
                browser.close()
                return

            out = Path(args.out or lesson_path.with_suffix(".mp4"))
            frames = int(math.ceil(timeline["total"] * args.fps))
            print(f"[2/3] drawing {frames} frames ({timeline['total']:.0f}s)", flush=True)
            ff = subprocess.Popen(
                [ffmpeg_exe(), "-y", "-loglevel", "error",
                 "-f", "image2pipe", "-framerate", str(args.fps), "-c:v", "mjpeg", "-i", "-",
                 "-i", str(tmp / "audio.wav"),
                 "-vf", "scale=out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart", str(out)],
                stdin=subprocess.PIPE)
            for f in range(frames):
                page.evaluate(f"window.render({f / args.fps:.4f})")
                ff.stdin.write(page.screenshot(type="jpeg", quality=92))
                if f % (args.fps * 10) == 0:
                    print(f"  {f / args.fps:5.0f}s / {timeline['total']:.0f}s", flush=True)
            ff.stdin.close()
            browser.close()
            print("[3/3] encoding", flush=True)
            if ff.wait() != 0:
                sys.exit("ffmpeg failed")
            print(f"done -> {out}")


if __name__ == "__main__":
    main()
