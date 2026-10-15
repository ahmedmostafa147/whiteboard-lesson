---
name: whiteboard-lesson
description: Turn a textbook page (photo, PDF page, or pasted text) into a narrated whiteboard-animation explainer video (MP4) in Arabic, with a marker that writes text and draws diagrams in sync with an Egyptian voice. Use when a teacher or user asks for a lesson video, whiteboard explanation, "فيديو شرح", "اشرحلي الدرس ده فيديو", or gives a page from a school book and wants it explained as a video.
---

# Whiteboard lesson video

Input: one or more textbook pages (images/PDF/text), optionally the grade, subject, and target length.
Output: `<lesson>.mp4` (1920x1080, 30fps), narrated, with a marker that writes the board as the teacher talks.

The pipeline: **you** write `lesson.json` (the teaching plan), `scripts/render.py` does narration, animation and encoding.

## Workflow

1. **Read the page carefully.** Extract the real content: the definitions, rules, examples, figures, and exercises. Never invent facts that aren't on the page or that are not standard curriculum knowledge for that grade. If a figure on the page matters (a diagram, map, shape), plan to redraw it as SVG.
2. **Plan the explanation like a good Egyptian teacher.** Hook → idea → example → common mistake → summary. Aim for 4–7 scenes and 1.5–4 minutes unless asked otherwise. One idea per scene.
3. **Write `lesson.json`** following `references/lesson-format.md`. Read that file before writing your first lesson; it has the schema, element types, SVG rules, and narration rules (including the TTS pitfalls).
4. **Preview** (fast, no audio):
   ```
   python <skill>/scripts/render.py lesson.json --preview previews/
   ```
   Open every `previews/scene_XX.png` and check: nothing overlaps or is cut off, diagrams look right, Arabic reads correctly, fractions stack, nothing is shrunk (the script warns `content too tall`). Fix the JSON and re-preview until every scene is clean.
5. **Render:**
   ```
   python <skill>/scripts/render.py lesson.json -o lesson.mp4
   ```
   Takes roughly 1.5× the video length. Narration is cached, so re-renders after visual fixes are faster.
6. Report the output path, length, and a one-line outline of the scenes.

## Requirements

Before the first render, check `python -c "import edge_tts, imageio_ffmpeg, playwright, faster_whisper"`; if it fails, run `pip install edge-tts imageio-ffmpeg playwright faster-whisper` yourself. Uses the installed Microsoft Edge or Chrome (no extra browser download). Narration: if `GEMINI_API_KEY` is set (env or a `.env` file in the working folder), use Gemini voices (`"voice": "gemini:Charon"`); they sound far more natural. Otherwise fall back to Microsoft's free voices (`ar-EG-ShakirNeural`, `ar-EG-SalmaNeural`). Gemini makes one request per lesson, so the free tier covers about 10 videos a day.

## Quality bar

- Every scene preview must be checked before the full render. No overlapping, clipped, or shrunk scenes.
- The board must support the narration, not repeat it word for word: short phrases on the board, full sentences in the voice.
- Math must be correct. Re-check every number, equation, and example answer before rendering.
