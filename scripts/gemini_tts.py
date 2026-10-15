"""Gemini TTS: synthesize one line to a 24 kHz mono WAV.

Key comes from GEMINI_API_KEY (env) or a .env file in the working directory.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
STYLE = ("اقرأ الكلام ده بصوت مدرس مصري، بلهجة مصرية طبيعية، "
         "هادي وواضح وودود وبيشرح لطلبة صغيرين:")


def api_key():
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k
    for p in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    raise SystemExit("GEMINI_API_KEY not set (env or .env)")


def synth(text, voice, out_wav, style=STYLE, retries=5):
    body = {
        "contents": [{"parts": [{"text": f"{style}\n{text}" if style else text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": api_key()})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            pcm = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            with wave.open(str(out_wav), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(pcm)
            return
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code in (429, 500, 503) and attempt < retries - 1:
                time.sleep(8 * (attempt + 1)); continue
            raise RuntimeError(f"Gemini TTS {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, KeyError):
            if attempt == retries - 1:
                raise
            time.sleep(4 * (attempt + 1))


def _norm(s, lang):
    import re
    s = s.lower()
    if lang == "ar":
        s = re.sub(r"[ً-ْـ]", "", s)  # tashkeel, tatweel
        s = s.translate(str.maketrans("أإآىةؤئ", "اااياوي"))
    return re.sub(r"[^\w]", "", s)


def split_aligned(full_wav, lines, out_wavs, lang="ar", ffmpeg="ffmpeg"):
    """Cut one long narration into per-line clips.

    Whisper transcribes the audio with word times; the transcript is aligned to the script
    by characters; each line end maps to a time, snapped to the nearest pause.
    """
    import difflib
    import re
    import subprocess
    import numpy as np
    from faster_whisper import WhisperModel

    with wave.open(str(full_wav)) as w:
        rate, pcm = w.getframerate(), w.readframes(w.getnframes())
    total = len(pcm) / 2 / rate
    raw = subprocess.run([ffmpeg, "-loglevel", "error", "-i", str(full_wav), "-f", "s16le", "-ar", "16000",
                          "-ac", "1", "-"], capture_output=True).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(audio, language=lang, word_timestamps=True)
    hyp, times = "", []
    for s in segs:
        for wd in s.words:
            n = _norm(wd.word, lang)
            for c in range(len(n)):
                hyp += n[c]
                times.append(wd.start + (wd.end - wd.start) * (c + 1) / max(1, len(n)))
    ref, ends = "", []
    for line in lines:
        ref += _norm(line, lang)
        ends.append(len(ref))
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]

    def ref_to_time(r):
        # last matched char at or before r (interpolate inside unmatched gaps)
        prev = None
        for b in blocks:
            if b.a + b.size <= r:
                prev = (b.a + b.size - 1, b.b + b.size - 1)
            elif b.a < r:
                prev = (r - 1, b.b + (r - 1 - b.a))
                break
            else:
                nxt = (b.a, b.b)
                if prev is None:
                    return times[max(0, nxt[1] - 1)] if times else 0.0
                f = (r - 1 - prev[0]) / max(1, nxt[0] - prev[0])
                h = int(prev[1] + f * (nxt[1] - prev[1]))
                return times[min(len(times) - 1, h)]
        return times[min(len(times) - 1, prev[1])] if prev and times else total

    log = subprocess.run([ffmpeg, "-i", str(full_wav), "-af", "silencedetect=noise=-38dB:d=0.12", "-f", "null", "-"],
                         capture_output=True, text=True, errors="ignore").stderr
    sil = list(zip([float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)],
                   [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]))
    cuts, last = [], 0.0
    for e in ends[:-1]:
        t = ref_to_time(e)
        near = [(abs(s - t), s, en) for s, en in sil if s >= last and s - t < 0.8 and t - en < 0.8]
        if near:
            _, s, en = min(near)
            cuts.append((s + 0.05, max(s + 0.05, en - 0.05)))
        else:
            cuts.append((t + 0.05, t + 0.05))
        last = cuts[-1][1]
    bounds = [0.0] + [c for pair in cuts for c in pair] + [total]
    for k, out in enumerate(out_wavs):
        a, b = bounds[2 * k], bounds[2 * k + 1]
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(pcm[int(a * rate) * 2:int(b * rate) * 2])
    return len(cuts)


def synth_batch(lines, voice, out_wavs, style=STYLE, ffmpeg="ffmpeg", lang="ar", keep=None):
    """One request for all lines (free tier allows only a few requests a day), then split per line."""
    import tempfile
    full = Path(keep) if keep else Path(tempfile.mkdtemp()) / "all.wav"
    if not full.exists():
        lead = (style + "\n" if style else "") + \
            "Read every line below in order, and leave a clear one-second silence between lines.\n\n"
        synth("\n\n".join(lines), voice, full, style=lead.strip())
    return split_aligned(full, lines, out_wavs, lang=lang, ffmpeg=ffmpeg), len(lines)


if __name__ == "__main__":
    import sys
    text = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    for v in sys.argv[3].split(","):
        synth(text, v, out / f"gemini_{v}.wav")
        print("ok", v, flush=True)
