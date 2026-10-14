# lesson.json format

```json
{
  "title": "الكسور — رياضيات رابعة ابتدائي",
  "voice": "ar-EG-ShakirNeural",
  "rate": "-4%",
  "scenes": [
    {
      "layout": "title | stack | split",
      "steps": [
        { "say": "sentence the teacher says", "show": { "type": "heading", "text": "..." } },
        { "say": "...", "show": [ {element}, {element} ] },
        { "say": "...", "pause": 0.5 }
      ]
    }
  ]
}
```

- `title` is shown small in the footer. `voice` is optional (default Shakir, male). Use `ar-EG-SalmaNeural` for a female voice. For an English lesson, use `en-US-AndrewNeural` or `en-GB-SoniaNeural`.
- Every scene is one clean board. The previous board is wiped with an eraser before the next scene.
- A **step** is one spoken sentence plus what gets written while it is said. `show` can be one element, a list (drawn one after another during that sentence), or missing (just talking). `pause` adds extra silence after the step, in seconds.
- Writing speed adapts to the sentence length, so the pen finishes while the voice is still on that idea.

## Layouts

- `title`: centered. Use only for the opening scene (heading + one text line).
- `stack` (default): elements top to bottom, right-aligned.
- `split`: text column on the right, all `drawing` elements in a column on the left. Use whenever a scene has a diagram.

## Capacity (to avoid shrunk scenes)

The board fits about **5 lines** in `stack` plus a heading. In `split`, the text column is narrower (~30 Arabic characters per line). If the preview warns `content too tall`, split the scene in two. Keep board text short: phrases, not paragraphs.

## Element types

| type | fields | notes |
|---|---|---|
| `heading` | `text`, `color?` | Scene title with a hand-drawn underline. One per scene, first. |
| `text` | `text`, `color?`, `dir?` | A plain line. |
| `bullet` | `text`, `color?`, `dotColor?`, `marker?`, `dir?` | `marker` replaces the dot with a number, e.g. `"١"`. |
| `equation` | `text`, `color?`, `dir?` | Centered, large. `a/b` (no spaces needed) renders as a **stacked fraction**. Default `dir` is `ltr`. Use `"dir": "rtl"` for equations written with Arabic symbols (`س + ٣ = ٧`). |
| `box` | `text`, `label?`, `color?` | Hand-drawn box for a rule or warning, e.g. label `"خلي بالك"` or `"القاعدة"`. |
| `drawing` | `svg`, `height?`, `caption?` | Inline SVG drawn stroke by stroke. Default height is 420px. |

Colors: `ink` `blue` `red` `green` `orange` `purple`. Use them consistently, e.g. red for the key number and green for rules.

`dir: "ltr"` on text, bullet, or heading is for English or French content. It writes left to right with a left-aligned layout.

## SVG drawings

The pen traces each shape in **document order**, so order the shapes the way a teacher would draw them: outline first, then divisions, labels last.

- Must have a `viewBox`. Use single quotes for attributes inside the JSON string.
- Use stroked shapes: `path`, `line`, `polyline`, `polygon`, `circle`, `ellipse`, `rect`. Give each a `stroke` and `stroke-width` of 5–7. A fill is fine; it fades in after the outline is drawn. Use `fill-opacity` around 0.5 for shading.
- `text` elements fade in. Use `font-family='Tajawal'` and a `font-size` of about 28–40 in viewBox units. Arabic labels work.
- Keep it simple: about 3–25 shapes. No `<image>`, filters, gradients, or `<use>`.
- Marker palette: `#1d4ed8` blue, `#c62828` red, `#15803d` green, `#d97706` orange, `#23262b` ink, and light fills like `#fde68a`, `#bfdbfe`, `#bbf7d0`.
- Arrows: draw them as `path`/`line` plus a small `polyline` head (markers are not traced).

## Narration rules (the voice is Microsoft's Egyptian neural TTS)

- Write the way an Egyptian teacher talks: light Egyptian Arabic for the explanation and exact book terms for definitions (البسط، المقام، الفعل المضارع...). Keep it warm and clear, without slang or jokes that a teacher wouldn't use.
- Each `say` is 1–2 short sentences (under ~25 words). Long sentences sound flat.
- **Add tashkeel to ambiguous words** so the voice says them right, for example `كَسْر` (not كاسر), `البَسْط`, `مَقام`, `عُمْر`, `حَرَكة`. Without tashkeel the TTS guesses and is often wrong.
- Avoid words the voice mangles: `النهارده` → say `في الدرس ده`. Prefer `إزاي`, `يعني`, `خلي بالك`, `يلا نجرب`.
- Write numbers in the narration as words when the reading matters (`ثلاثة أخماس`, `خمسة وعشرين في المية`). Symbols like `/`, `=`, `%` should never be in `say`.
- Don't read the board aloud verbatim. The board has the short version and the voice explains it.
