# Whiteboard Lesson — Claude Skill

<div dir="rtl">

Skill لـ Claude بتحوّل أي صفحة من كتاب مدرسي لـ **فيديو شرح وايت بورد كامل**: قلم بيكتب ويرسم على السبورة، وصوت مصري بيشرح في نفس اللحظة.

## بتعمل إيه

- تقرا الصفحة (صورة أو PDF أو نص) وتكتب خطة شرح زي المدرس.
- تكتب الكلام وترسم الأشكال على السبورة خطوة بخطوة، متزامنة مع الصوت.
- كسور مكتوبة فوق بعض، ومعادلات بالعربي، ورسومات علمية، وشغالة بالعربي والإنجليزي.
- أصوات طبيعية جداً من Gemini (رجالي وحريمي، عربي وإنجليزي)، وتقدر توجّه طريقة الكلام. ولو مفيش مفتاح، بتشتغل بأصوات Microsoft المجانية.
- الناتج فيديو MP4 بجودة 1080p.

## التسطيب

محتاج [Claude Code](https://claude.com/claude-code)، وPython 3.10 أو أحدث، ومتصفح Edge أو Chrome.

```bash
git clone https://github.com/ahmedmostafa147/whiteboard-lesson ~/.claude/skills/whiteboard-lesson
```

المكتبات بتتسطب لوحدها أول مرة. ولو حابب تسطّبها بنفسك:

```bash
pip install edge-tts imageio-ffmpeg playwright faster-whisper
```

### صوت Gemini (اختياري، ومجاني)

اعمل مفتاح من [Google AI Studio](https://aistudio.google.com/apikey) وحطه في ملف `.env` في الفولدر اللي شغال فيه:

```
GEMINI_API_KEY=your-key
```

كل فيديو بياخد طلب واحد بس، فالحساب المجاني بيكفي حوالي 10 فيديوهات في اليوم.

## الاستخدام

افتح Claude Code، وارفع صورة الصفحة، واكتب:

> حوّل الصفحة دي لفيديو شرح وايت بورد

أو اطلبها بالاسم: `/whiteboard-lesson`

### اسمك على الفيديوهات

اكتب اسمك في `config.json`، وهيظهر تحت في نص كل فيديو:

```json
{ "watermark": "Your Name" }
```

</div>

## How it works

1. Claude reads the page and writes `lesson.json`, a teaching plan of scenes and steps. Each step is one spoken sentence plus what gets written or drawn during it ([format](references/lesson-format.md)).
2. `scripts/render.py` generates the narration (Gemini TTS in one request per lesson, split into sentences with Whisper alignment, or Microsoft Edge TTS without a key), times every pen stroke to the voice, renders each frame of an HTML/SVG whiteboard deterministically in a headless browser, and encodes the result with ffmpeg.

```bash
python scripts/render.py examples/01-fractions.json --preview previews/   # one PNG per scene
python scripts/render.py examples/01-fractions.json -o fractions.mp4      # full video
```

## License

Code is MIT. Fonts (El Messiri, Tajawal) are under the SIL Open Font License.

Built by **Ahmed Mustafa**.
