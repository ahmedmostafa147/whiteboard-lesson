// Whiteboard renderer. Builds every scene once, then render(t) sets the
// board to its exact state at time t, so each frame is deterministic.
(function () {
  const L = window.LESSON, TL = window.TIMELINE;
  const COLORS = ["ink", "blue", "red", "green", "orange", "purple"];
  const WIPE = TL.wipe;
  const pen = document.getElementById("pen");
  const eraser = document.getElementById("eraser");
  const scenesEl = document.getElementById("scenes");
  const els = {};   // id -> {kind, node, units, ...}
  const scenes = [];

  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const ease = (p) => p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
  const colorOf = (e, dflt) => "c-" + (COLORS.includes(e.color) ? e.color : dflt);

  // Wrap each word in a span so it can be revealed like handwriting.
  function words(parent, text) {
    const units = [];
    String(text).split(/(\s+)/).forEach((tok) => {
      if (!tok) return;
      if (/^\s+$/.test(tok)) { parent.appendChild(document.createTextNode(" ")); return; }
      const s = document.createElement("span");
      s.className = "w"; s.textContent = tok;
      parent.appendChild(s);
      units.push({ node: s, weight: tok.length + 1 });
    });
    return units;
  }

  // Like words(), but "3/5" becomes a stacked fraction.
  function mathWords(parent, text) {
    const units = [];
    String(text).trim().replace(/\s*\/\s*/g, "/").split(/\s+/).forEach((tok, i) => {
      if (i) parent.appendChild(document.createTextNode(" "));
      const s = document.createElement("span");
      s.className = "w";
      const m = tok.match(/^([^/]+)\/([^/]+)$/);
      if (m) {
        s.classList.add("frac");
        s.innerHTML = "<span class=\"num\"></span><span class=\"den\"></span>";
        s.firstChild.textContent = m[1]; s.lastChild.textContent = m[2];
      } else s.textContent = tok;
      parent.appendChild(s);
      units.push({ node: s, weight: tok.length + 1 });
    });
    return units;
  }

  function build(e, id) {
    const wrap = document.createElement("div");
    wrap.className = "el";
    let rec = { kind: e.type, units: [] };
    if (e.type === "heading") {
      wrap.classList.add("heading-wrap");
      const h = document.createElement("div");
      h.className = "heading " + colorOf(e, "blue");
      rec.units = words(h, e.text);
      const u = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      u.setAttribute("class", "uline"); u.setAttribute("viewBox", "0 0 400 26");
      u.setAttribute("preserveAspectRatio", "none");
      u.innerHTML = '<path d="M398 14 C 300 4, 220 22, 140 12 S 30 8, 2 16" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" opacity="0.55"/>';
      h.appendChild(u);
      rec.uline = u.querySelector("path");
      wrap.appendChild(h);
    } else if (e.type === "text") {
      wrap.classList.add("text", colorOf(e, "ink"));
      rec.units = words(wrap, e.text);
    } else if (e.type === "bullet") {
      wrap.classList.add("bullet", colorOf(e, "ink"));
      const d = document.createElement("span");
      d.className = "dot";
      if (e.marker) { d.classList.add("num"); d.textContent = e.marker; }
      d.style.color = "var(--" + (COLORS.includes(e.dotColor) ? e.dotColor : "blue") + ")";
      wrap.appendChild(d);
      rec.dot = d;
      const t = document.createElement("span");
      rec.units = words(t, e.text);
      wrap.appendChild(t);
    } else if (e.type === "equation") {
      wrap.classList.add("equation", colorOf(e, "red"));
      const ltr = e.dir !== "rtl";
      if (ltr) wrap.classList.add("ltr");
      rec.ltr = ltr;
      rec.units = mathWords(wrap, e.text);
    } else if (e.type === "box") {
      wrap.classList.add("box", colorOf(e, "green"));
      const b = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      b.setAttribute("class", "boxsvg"); b.setAttribute("preserveAspectRatio", "none");
      b.setAttribute("viewBox", "0 0 1000 200");
      b.innerHTML = '<path d="M20 6 L980 10 Q994 12 994 26 L990 180 Q988 194 974 194 L24 190 Q8 188 8 172 L12 22 Q12 8 20 6 Z" fill="currentColor" fill-opacity="0" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/>';
      wrap.appendChild(b);
      rec.frame = b.querySelector("path");
      const inner = document.createElement("div");
      inner.className = "inner";
      if (e.label) {
        const l = document.createElement("span");
        l.className = "label"; rec.units.push(...words(l, e.label)); inner.appendChild(l);
      }
      const t = document.createElement("span");
      t.style.color = "var(--ink)";
      rec.units.push(...words(t, e.text));
      inner.appendChild(t);
      wrap.appendChild(inner);
    } else if (e.type === "drawing") {
      wrap.classList.add("drawing-wrap");
      const d = document.createElement("div");
      d.className = "drawing";
      d.innerHTML = e.svg;
      const svg = d.querySelector("svg");
      if (svg) {
        svg.setAttribute("height", e.height || 420);
        svg.removeAttribute("width");
        svg.style.height = (e.height || 420) + "px";
        svg.style.width = "auto";
        svg.style.maxWidth = "100%";
      }
      wrap.appendChild(d);
      if (e.caption) {
        const c = document.createElement("div");
        c.className = "caption"; c.textContent = e.caption; wrap.appendChild(c);
        rec.caption = c;
      }
      rec.svg = svg;
    }
    if (e.dir === "ltr" && e.type !== "drawing") { wrap.setAttribute("dir", "ltr"); rec.ltr = true; }
    rec.node = wrap;
    els[id] = rec;
    return wrap;
  }

  // Measure everything that depends on real layout: stroke lengths, word weights.
  function prepare(rec) {
    let total = 0;
    rec.units.forEach((u) => { total += u.weight; });
    rec.unitTotal = total;
    if (rec.kind === "drawing" && rec.svg) {
      const parts = [];
      rec.svg.querySelectorAll("path,line,polyline,polygon,circle,ellipse,rect,text").forEach((n) => {
        if (n.closest("defs")) return;
        if (n.tagName === "text") { parts.push({ n, text: true, w: 60 }); return; }
        const cs = getComputedStyle(n);
        const stroked = cs.stroke && cs.stroke !== "none" && parseFloat(cs.strokeWidth) > 0;
        let len = 0;
        try { len = n.getTotalLength(); } catch (err) { len = 0; }
        const fillOp = cs.fill && cs.fill !== "none" ? parseFloat(cs.fillOpacity || 1) : 0;
        parts.push({ n, stroked: stroked && len > 0, len, fillOp, w: stroked && len > 0 ? Math.max(40, len) : 60 });
      });
      let acc = 0, sum = parts.reduce((a, p) => a + p.w, 0) || 1;
      parts.forEach((p) => { p.a = acc / sum; acc += p.w; p.b = acc / sum; });
      rec.parts = parts;
    }
  }

  function buildAll() {
    const tl = TL.scenes;
    L.scenes.forEach((sc, si) => {
      const s = document.createElement("div");
      const layout = sc.layout || "stack";
      s.className = "scene layout-" + layout;
      const content = document.createElement("div");
      content.className = "content";
      let colText = content, colDraw = content;
      if (layout === "split") {
        colText = document.createElement("div"); colText.className = "col-text";
        colDraw = document.createElement("div"); colDraw.className = "col-draw";
        content.appendChild(colText); content.appendChild(colDraw);
      }
      tl[si].events.forEach((ev) => {
        const node = build(ev.el, ev.id);
        (ev.el.type === "drawing" ? colDraw : colText).appendChild(node);
      });
      s.appendChild(content);
      scenesEl.appendChild(s);
      scenes.push({ node: s, content, tl: tl[si] });
    });
    document.querySelector("#footer .title").textContent = L.title || "";
    document.getElementById("watermark").textContent = L.watermark || "";
  }

  // Give underline/box outlines a viewBox in real pixels so strokes and
  // dash lengths are exact (no stretched SVG).
  function fitFrames(rec) {
    const svg = rec.uline ? rec.uline.ownerSVGElement : rec.frame ? rec.frame.ownerSVGElement : null;
    if (!svg) return;
    const w = Math.max(10, svg.clientWidth), h = Math.max(10, svg.clientHeight);
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    if (rec.uline) {
      rec.uline.setAttribute("d", `M${w - 2} ${h * 0.55} C ${w * 0.7} ${h * 0.15}, ${w * 0.45} ${h * 0.85}, ${w * 0.25} ${h * 0.45} S ${w * 0.05} ${h * 0.4}, 2 ${h * 0.6}`);
    } else {
      const k = 14;
      rec.frame.setAttribute("d", `M${w - k} 4 L${k + 4} 7 Q4 8 5 ${k + 6} L8 ${h - k} Q9 ${h - 4} ${k + 6} ${h - 5} L${w - k} ${h - 3} Q${w - 3} ${h - 4} ${w - 4} ${h - k - 4} L${w - 5} ${k} Q${w - 6} 3 ${w - k} 4 Z`);
    }
    delete (rec.uline || rec.frame).__len;
  }

  // Shrink a scene that would spill off the board; report how much.
  window.layoutReport = function () {
    const report = [];
    scenes.forEach((sc, i) => {
      sc.node.style.display = "block";
      const avail = sc.node.clientHeight - 96 - 120;
      const availW = sc.node.clientWidth - 280;
      const h = sc.content.scrollHeight, w = sc.content.scrollWidth;
      let scale = Math.min(1, avail / h, availW / w);
      if (scale < 1) sc.content.style.transform = "scale(" + scale.toFixed(3) + ")";
      // Short boards sit a bit lower instead of hugging the top edge.
      else if (!sc.node.classList.contains("layout-title") && h < avail * 0.6)
        sc.content.style.paddingTop = Math.round((avail - h) * 0.3) + "px";
      sc.tl.events.forEach((ev) => { fitFrames(els[ev.id]); prepare(els[ev.id]); });
      sc.node.style.display = "none";
      report.push({ scene: i, contentHeight: h, available: avail, scale: +scale.toFixed(3) });
    });
    return report;
  };

  function revealUnits(rec, p, ltr) {
    // Returns screen point of the "pen" for the current word, or null.
    let target = p * rec.unitTotal, acc = 0, penAt = null;
    rec.units.forEach((u) => {
      const local = clamp((target - acc) / u.weight);
      acc += u.weight;
      const hidden = (1 - local) * 100;
      u.node.style.clipPath = local >= 1 ? "none" :
        (ltr ? `inset(-20% ${hidden}% -30% -5%)` : `inset(-20% -5% -30% ${hidden}%)`);
      if (local > 0 && local < 1) {
        const r = u.node.getBoundingClientRect();
        const x = ltr ? r.left + r.width * local : r.right - r.width * local;
        penAt = { x, y: r.top + r.height * 0.62 };
      }
    });
    return penAt;
  }

  function setDash(path, p) {
    const len = path.__len || (path.__len = path.getTotalLength());
    path.style.strokeDasharray = len;
    path.style.strokeDashoffset = len * (1 - p);
  }

  function apply(rec, p) {
    // p in [0,1] is this element's drawing progress.
    const n = rec.node;
    n.style.visibility = p <= 0 ? "hidden" : "visible";
    if (p <= 0) return null;
    let penAt = null;
    if (rec.kind === "heading") {
      penAt = revealUnits(rec, clamp(p / 0.8), rec.ltr);
      const up = clamp((p - 0.8) / 0.2);
      setDash(rec.uline, up);
      if (up > 0 && up < 1) {
        const r = rec.uline.getBoundingClientRect();
        penAt = { x: r.right - r.width * up, y: r.top + r.height * 0.6 };
      }
    } else if (rec.kind === "box") {
      const fp = clamp(p / 0.3);
      setDash(rec.frame, fp);
      rec.frame.style.fillOpacity = 0.07 * fp;
      if (fp < 1) {
        const len = rec.frame.__len, pt = rec.frame.getPointAtLength(len * fp);
        const m = rec.frame.getScreenCTM();
        const sp = new DOMPoint(pt.x, pt.y).matrixTransform(m);
        penAt = { x: sp.x, y: sp.y };
      } else penAt = revealUnits(rec, clamp((p - 0.3) / 0.7), rec.ltr);
      if (fp < 1) revealUnits(rec, 0, false);
    } else if (rec.kind === "bullet") {
      rec.dot.style.opacity = clamp(p / 0.12);
      penAt = revealUnits(rec, clamp((p - 0.12) / 0.88), rec.ltr);
    } else if (rec.kind === "drawing") {
      if (!rec.parts) return null;
      rec.parts.forEach((part) => {
        const lp = clamp((p - part.a) / Math.max(1e-6, part.b - part.a));
        const s = part.n.style;
        if (part.text) { s.opacity = ease(lp); return; }
        if (part.stroked) {
          s.strokeDasharray = part.len;
          s.strokeDashoffset = part.len * (1 - lp);
          s.fillOpacity = part.fillOp * clamp((lp - 0.85) / 0.15);
          if (lp > 0 && lp < 1) {
            const pt = part.n.getPointAtLength(part.len * lp);
            const sp = new DOMPoint(pt.x, pt.y).matrixTransform(part.n.getScreenCTM());
            penAt = { x: sp.x, y: sp.y };
          }
        } else {
          s.opacity = ease(lp);
        }
      });
      if (rec.caption) rec.caption.style.opacity = clamp((p - 0.9) / 0.1);
    } else {
      penAt = revealUnits(rec, p, rec.ltr);
    }
    return p < 1 ? penAt : null;
  }

  function showPen(at, color) {
    if (!at) { pen.style.display = "none"; return; }
    pen.style.display = "block";
    pen.style.setProperty("--pen", "var(--" + color + ")");
    pen.style.transform = `translate(${at.x - 8}px, ${at.y - 112}px)`;
  }

  function sceneAt(t) {
    const tl = TL.scenes;
    for (let i = tl.length - 1; i >= 0; i--) if (t >= tl[i].start) return i;
    return 0;
  }

  function stateAt(si, t) {
    const sc = scenes[si];
    let penAt = null, penColor = "blue";
    sc.tl.events.forEach((ev) => {
      const rec = els[ev.id];
      const p = clamp((t - ev.start) / ev.dur);
      const at = apply(rec, p);
      if (at) { penAt = at; penColor = ev.el.color || (ev.el.type === "heading" ? "blue" : ev.el.type === "equation" ? "red" : ev.el.type === "box" ? "green" : "ink"); }
    });
    return { penAt, penColor };
  }

  window.render = function (t) {
    const si = sceneAt(t);
    const tl = TL.scenes[si];
    scenes.forEach((s) => { s.node.style.display = "none"; s.node.style.clipPath = "none"; });
    eraser.style.display = "none";

    const cur = scenes[si];
    cur.node.style.display = "block";
    const st = stateAt(si, t);

    // Wipe the previous scene off the board at the start of this one.
    if (si > 0 && t < tl.start + WIPE) {
      const prev = scenes[si - 1];
      prev.node.style.display = "block";
      stateAt(si - 1, t);
      const wp = ease(clamp((t - tl.start) / WIPE));
      prev.node.style.clipPath = `inset(0 ${wp * 100}% 0 0)`;
      cur.node.style.display = "none";
      const x = 1920 - wp * 1920;
      eraser.style.display = "block";
      eraser.style.left = (x - 85) + "px";
      eraser.style.top = (430 + Math.sin(wp * 18) * 160) + "px";
      showPen(null);
    } else {
      showPen(st.penAt, st.penColor);
    }
    document.querySelector("#footer .bar").style.width = (clamp(t / TL.total) * 100) + "%";
  };

  buildAll();
})();
