#!/usr/bin/env python3
"""Measure every run of text on a page against the pixels actually behind it.

    python3 tools/contrast-check.py <url-or-file://path> <label>

Why this exists: a normal contrast check composites a colour over the
background *colour* stack. The pages here sit on a painted plate — an <img> —
so that check passes while text is genuinely swallowed. Measured that way this
page read "clean"; measured the way below, the live page had runs at 3.28.

How it works: the page is screenshotted twice, the second time with every glyph
turned transparent, so the true background under each run of text is known. The
CSS colour of the text is then composited over the darkest and the brightest
tenth of that background, and the worse of the two is reported.

Two traps it handles, both of which cost a round of missed findings:
  · the form steps and the success screen are display:none until you walk them
  · the progress bar does not exist until #startBtn is pressed — a run that
    skips the click measures about a third of the page
"""
import asyncio, os, sys, tempfile
from playwright.async_api import async_playwright
from PIL import Image
if len(sys.argv) < 2:
    sys.exit("usage: contrast-check.py <url-or-file://path> [label]\n"
             "       CONTRAST_OUT=<dir> to keep the screenshots somewhere you choose")

URL  = sys.argv[1]
NAME = sys.argv[2] if len(sys.argv) > 2 else "page"
# ⚠️ never a session scratchpad: that path belongs to one run of one agent and
# is gone by the next boot, which would leave a tool in git that cannot even
# take its first screenshot.
OUT  = os.environ.get("CONTRAST_OUT") or tempfile.mkdtemp(prefix="contrast-")
os.makedirs(OUT, exist_ok=True)
def lin(v):
    v/=255.0
    return v/12.92 if v<=0.03928 else ((v+0.055)/1.055)**2.4
def lum(p): return 0.2126*lin(p[0])+0.7152*lin(p[1])+0.0722*lin(p[2])
def ratio(a,b):
    hi,lo=max(a,b),min(a,b); return (hi+0.05)/(lo+0.05)
HIDE="* , *::placeholder { color: transparent !important; -webkit-text-fill-color: transparent !important; }"
TEXTJS = """() => {
  const parse = c => { const m = c.match(/[0-9.]+/g).map(Number);
    return { r:m[0], g:m[1], b:m[2], a:m.length>3?m[3]:1 }; };
  const out = [];
  document.querySelectorAll('body *').forEach(e => {
    const d = [...e.childNodes].filter(n => n.nodeType===3 && n.textContent.trim());
    if (!d.length) return;
    const cs = getComputedStyle(e);
    if (cs.visibility==='hidden' || cs.display==='none' || +cs.opacity===0) return;
    const b = e.getBoundingClientRect(); if (b.width<6||b.height<6) return;
    const c = parse(cs.color);
    out.push({ t:d.map(n=>n.textContent.trim()).join(' ').slice(0,36),
      cls:String(e.className).slice(0,24)||e.tagName,
      x:Math.round(b.left), y:Math.round(b.top+window.scrollY),
      w:Math.round(b.width), h:Math.round(b.height),
      fs:parseFloat(cs.fontSize), bold:+cs.fontWeight>=600, fg:[c.r,c.g,c.b], fa:c.a });
  });
  document.querySelectorAll('input[placeholder],textarea[placeholder]').forEach(e => {
    const b = e.getBoundingClientRect(); if (b.width<6) return;
    const ph = getComputedStyle(e,'::placeholder'); const c = parse(ph.color);
    out.push({ t:'[placeholder] '+e.placeholder.slice(0,24), cls:'ph:'+(e.id||''),
      x:Math.round(b.left), y:Math.round(b.top+window.scrollY),
      w:Math.round(b.width), h:Math.round(b.height),
      fs:parseFloat(ph.fontSize), bold:false, fg:[c.r,c.g,c.b], fa:c.a });
  });
  return out;
}"""
SETTLE = """async () => {
  document.querySelectorAll('img').forEach(i => i.loading='eager');
  document.querySelectorAll('.step').forEach(s => s.classList.add('active'));
  const ss = document.querySelector('.success-screen'); if (ss) ss.classList.add('active');
  const pb = document.getElementById('progress'); if (pb) pb.style.display = 'block';
  document.querySelectorAll('.intro-screen').forEach(e => e.style.display = 'block');
  for (let y=0; y<document.body.scrollHeight; y+=400) { window.scrollTo(0,y); await new Promise(r=>setTimeout(r,45)); }
  window.scrollTo(0,0);
  await Promise.all([...document.querySelectorAll('img')].map(i=>i.decode().catch(()=>{})));
}"""
async def go(engine,w,tag):
    async with async_playwright() as p:
        br=await getattr(p,engine).launch()
        pg=await br.new_page(viewport={"width":w,"height":900}, device_scale_factor=1)
        await pg.goto(URL, wait_until="networkidle", timeout=60000)
        # ⚠️ the progress bar and the form steps only exist after Start is pressed;
        # forcing display on the container was not enough because a parent hides it.
        try:
            await pg.click('#startBtn', timeout=4000); await pg.wait_for_timeout(500)
        except Exception:
            pass
        await pg.evaluate(SETTLE); await pg.wait_for_timeout(1100)
        boxes=await pg.evaluate(TEXTJS)
        await pg.add_style_tag(content=HIDE); await pg.wait_for_timeout(500)
        pb=f"{OUT}/BG4_{tag}.png"; await pg.screenshot(path=pb, full_page=True)
        await br.close()
    B=Image.open(pb).convert("RGB"); W,H=B.size; bad=[]; n=0
    for x in boxes:
        x0,y0=max(0,x["x"]),max(0,x["y"]); x1,y1=min(W,x["x"]+x["w"]),min(H,x["y"]+x["h"])
        if x1-x0<6 or y1-y0<6: continue
        px=list(B.crop((x0,y0,x1,y1)).getdata())
        if len(px)<30: continue
        # font-size:0 is how a page hides a character behind a drawn icon. There
        # is nothing to read, so it is not a run of text and must not inflate
        # the count either.
        if x["fs"] < 1: continue
        n+=1
        Ls=sorted(lum(p) for p in px)
        fg=x["fg"]; a=x["fa"]; worst=99
        for bgl in (Ls[int(len(Ls)*0.10)], Ls[int(len(Ls)*0.90)]):
            comp=[fg[i]*a + (bgl**(1/2.2)*255)*(1-a) for i in range(3)]
            worst=min(worst, ratio(lum(comp), bgl))
        need=3.0 if (x["fs"]>=24 or (x["fs"]>=18.66 and x["bold"])) else 4.5
        if worst<need: bad.append((round(worst,2),need,x["fs"],x["cls"],x["t"]))
    return n,sorted(bad)
async def main():
    total=0
    for engine,w in (("webkit",1440),("webkit",390),("chromium",390)):
        n,bad=await go(engine,w,f"{NAME}_{engine}{w}")
        total+=len(bad)
        print(f"\n### {NAME} {engine}@{w} — {n} runs of text (every step + success screen open)")
        if not bad: print("   CLEAN")
        for r,need,fs,cls,t in bad[:12]:
            print(f'   {r:5.2f} (needs {need}) {fs:6.1f}px {cls:24s} "{t}"')
        if len(bad)>12: print(f"   ... and {len(bad)-12} more")
    # a non-zero exit makes this usable as a gate; a tool that only prints is a
    # tool somebody has to remember to read.
    return 1 if total else 0

sys.exit(asyncio.run(main()))
