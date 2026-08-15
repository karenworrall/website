"""Accessibility audit: WCAG 2.1 contrast plus structural checks.

Backgrounds are measured, not inferred. Computed styles cannot tell you what
is behind a fixed overlay, a translucent panel or a gradient, so instead the
page is rendered a second time with every glyph made transparent, and the
pixel at each text element's centre is sampled from that render. Sampling is
done per scroll position so fixed elements land where they really sit.
"""
import io
import pathlib
import re

from PIL import Image
from playwright.sync_api import sync_playwright

URL = (pathlib.Path(__file__).parent / "preview.html").resolve().as_uri()
VW, VH = 1440, 1000


def parse_color(s):
    s = s.strip()
    m = re.match(r"color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*/\s*([\d.]+))?\)", s)
    if m:
        r, g, b = (float(m.group(i)) * 255 for i in (1, 2, 3))
        return r, g, b, float(m.group(4)) if m.group(4) else 1.0
    m = re.match(r"rgba?\(([^)]+)\)", s)
    if m:
        parts = [p.strip() for p in m.group(1).replace("/", ",").split(",")]
        r, g, b = (float(p) for p in parts[:3])
        return r, g, b, float(parts[3]) if len(parts) > 3 else 1.0
    return None


def composite(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def luminance(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(fg, bg):
    l1, l2 = luminance(fg), luminance(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


COLLECT = """
() => [...document.querySelectorAll('body *')]
  .filter(el => {
    if (el.closest('.palette-switch')) return false;
    if (!el.textContent.trim()) return false;
    if ([...el.childNodes].every(n => n.nodeType !== 3 || !n.textContent.trim())) return false;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  })
  .map((el, i) => {
    el.dataset.a11y = i;
    const s = getComputedStyle(el);
    return { i, sel: el.tagName.toLowerCase() +
        (typeof el.className === 'string' && el.className.trim()
          ? '.' + el.className.trim().split(/\\s+/).slice(0,2).join('.') : ''),
      text: el.textContent.trim().replace(/\\s+/g,' ').slice(0, 44),
      color: s.color, size: parseFloat(s.fontSize), weight: parseInt(s.weight || s.fontWeight) };
  })
"""

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    pg = b.new_page(viewport={"width": VW, "height": VH})
    pg.goto(URL, wait_until="networkidle")
    pg.add_style_tag(content="html{scroll-behavior:auto !important}")
    pg.evaluate("document.querySelectorAll('.reveal,.reveal-group').forEach(e=>e.classList.add('is-in'))")
    pg.wait_for_timeout(500)

    items = {it["i"]: it for it in pg.evaluate(COLLECT)}

    # Second render with glyphs blanked, so each sample is pure background.
    pg.add_style_tag(content="""
      *, *::before, *::after { color: transparent !important;
        text-shadow: none !important; -webkit-text-stroke: 0 !important; }
      svg { visibility: hidden !important; }
    """)
    pg.wait_for_timeout(300)

    height = pg.evaluate("document.body.scrollHeight")
    samples = {}
    y = 0
    while y < height + VH:
        pg.evaluate(f"window.scrollTo(0,{y})")
        pg.wait_for_timeout(120)
        shot = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
        boxes = pg.evaluate("""
          () => [...document.querySelectorAll('[data-a11y]')].map(el => {
            const r = el.getBoundingClientRect();
            return { i:+el.dataset.a11y, x:r.left + r.width/2, y:r.top + r.height/2,
                     vis: r.top >= 0 && r.bottom <= window.innerHeight };
          })
        """)
        for bx in boxes:
            if bx["vis"] and bx["i"] not in samples:
                px = shot.getpixel((min(max(int(bx["x"]), 0), VW - 1),
                                    min(max(int(bx["y"]), 0), VH - 1)))
                samples[bx["i"]] = (px[0], px[1], px[2], 1.0)
        y += VH - 120

    fails, passes, skipped = [], 0, 0
    for i, it in items.items():
        fg = parse_color(it["color"])
        bg = samples.get(i)
        if fg is None or bg is None:
            skipped += 1
            continue
        fg_c = composite(fg, bg) if fg[3] < 1 else fg
        r = ratio(fg_c, bg)
        large = it["size"] >= 24 or (it["size"] >= 18.66 and (it["weight"] or 400) >= 700)
        need = 3.0 if large else 4.5
        if r < need:
            fails.append((round(r, 2), need, it["sel"], round(it["size"], 1), it["text"]))
        else:
            passes += 1

    print(f"CONTRAST — {passes} pass, {len(fails)} fail, {skipped} not sampled\n")
    seen = set()
    for r, need, sel, size, text in sorted(fails):
        key = (sel, r)
        n = sum(1 for f in fails if (f[2], f[0]) == key)
        if key in seen:
            continue
        seen.add(key)
        print(f"  {r:5.2f} (need {need})  {size:5.1f}px  {sel:26} x{n:<3} e.g. {text}")

    print("\nSTRUCTURE")
    checks = pg.evaluate("""
    () => ({
      h1: document.querySelectorAll('h1').length,
      headings: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h=>h.tagName),
      imgsNoAlt: [...document.querySelectorAll('img')].filter(i=>!i.hasAttribute('alt')).length,
      linksNoName: [...document.querySelectorAll('a')]
        .filter(a=>!(a.textContent.trim()||a.getAttribute('aria-label')||a.title)).length,
      btnsNoName: [...document.querySelectorAll('button')]
        .filter(b=>!(b.textContent.trim()||b.getAttribute('aria-label')||b.title)).length,
      svgExposed: [...document.querySelectorAll('svg')]
        .filter(s=>!s.hasAttribute('aria-hidden') && !s.closest('[aria-label]'))
        .map(s=>s.parentElement.className||s.parentElement.tagName)
    })
    """)
    prev, skips = 0, []
    for h in checks["headings"]:
        lvl = int(h[1])
        if prev and lvl > prev + 1:
            skips.append(f"{prev}->{lvl}")
        prev = lvl
    print(f"  h1 count            : {checks['h1']}")
    print(f"  heading skips       : {skips or 'none'} ({' '.join(checks['headings'])})")
    print(f"  images missing alt  : {checks['imgsNoAlt']}")
    print(f"  links w/o name      : {checks['linksNoName']}")
    print(f"  buttons w/o name    : {checks['btnsNoName']}")
    print(f"  svg exposed to AT   : {checks['svgExposed'] or 'none'}")
    b.close()
