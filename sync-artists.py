#!/usr/bin/env python3
"""Rebuild the collage from the street-artist folder.

Or drops photos into  ~/Desktop/Codex/גלריית דמויות אמנים/תמונות נפרדות/אמני מוזיקה ברחוב
and this script exports web-sized JPGs into assets/artists/ and rewrites the
card markup in index.html between the AUTO-CARDS markers.  Nothing else in the
file is touched.

The eight slots are artlistmusic.io's own, measured live at 1440px on 1.9.2026
(x, y, w, h in px; y is rebased below by -450, the top of their collage):

    slot  x     y     w    h     aspect  w%
    0     0     469   315  427   0.74    21.9   flush to the left edge
    1     245   557   191  240   0.80    13.3
    2     135   956   135  180   0.75     9.4
    3     1096  552   135  182   0.74     9.4
    4     660   643   270  368   0.73    18.8
    5     547   741   214  139   1.54    14.9   the one landscape
    6     1149  918   315  485   0.65    21.9   bleeds off the right edge
    7     987   936   191  240   0.80    13.3

Parallax, also measured: the y-drift each card accumulates over 1000px of
scroll, and its sideways drift.  Two families — four cards lag hard (0.30-0.43)
and four are nearly pinned (0.015-0.04).  That contrast is the whole effect.
"""
import os, re, glob, sys
from PIL import Image

SRC   = os.path.expanduser('~/Desktop/Codex/גלריית דמויות אמנים/תמונות נפרדות/אמני מוזיקה ברחוב')

# Files Or named one by one that live outside SRC. He picked these two out of
# the three in 'סוריאליזם גאומטרי' on 1.9 and left קולאז-02 out, so the list is
# explicit rather than a second folder glob.
EXTRA = [os.path.expanduser(
    '~/Desktop/Codex/גלריית דמויות אמנים/תמונות נפרדות/סוריאליזם גאומטרי/' + n)
    for n in ('קולאז-01-פרח-קוי-לימון.png',
              'קולאז-03-פטריות-חיפושית-תקליט.png')]
REPO  = os.path.dirname(os.path.abspath(__file__))
OUT   = os.path.join(REPO, 'assets/artists')
FIELD  = 1010.0
# Or, 1.9: "תגדיל משמעותית את כל התמונות" — one knob. artlist's own numbers are
# SCALE 1.0; everything below is theirs times this, positions scaled about each
# card's own centre so the composition keeps its shape as it grows.
SCALE  = 1.80
MSCALE = 1.45
INSET  = 260  # .cw headroom top and bottom, so parallax never clips a card  # desktop .cw inner height
MFIELD =  560.0  # phone .cw inner height

# ═══ artlistmusic.io's collage, copied off their own DOM ═══════════════════
#
# Or, 1.9: "אתה עדיין עובד במרכז... לך לדף של ארטליסט ותמדוד מה הם עשו, תעתיק
# מהקוד שלהם דרך גוגל מפתחים." Read straight out of DevTools at vw=1440:
#
#   the collage container   div.comp-mosldbbu-container
#       display:grid · width 1440px · height 1098.19px · starts at page y=457
#       — it is the FULL WINDOW WIDTH. Not a centred max-width column. That was
#       the bug: .cw here was max-width:1400px;margin:0 auto, so on a wide
#       screen every card was penned into the middle while artlist's run edge
#       to edge. Hence "אתה עדיין עובד במרכז".
#
#   each card    div.comp-*-container
#       display:grid · grid-area 1/1/2/2 — all eight share ONE cell —
#       justify-self:start · align-self:start · offset by its own margin,
#       e.g. the first is margin:106.75px 0 0. Which is absolute positioning
#       spelled differently, so left/top here is a faithful transcription.
#
#   each photo   img
#       inline: object-fit:cover; object-position:<their focal point>; width:100%
#       Wix also serves the file pre-cropped to the box (fp_0.32_0.56 in the URL).
#
# Boxes at 1440 (page y, then rebased to the container's 457):
#      x     y   local-y    w    h     object-position
#      0    469     12    315  427     32% 56%
#    245    557    100    191  240     52% 29%
#    135    956    499    135  180     47% 33%
#   1096    552     95    135  182     47% 26%
#    660    643    186    270  368     48% 33%
#    547    741    284    214  139     50% 50%
#   1149    918    461    315  485     50% 37%   ← pulled in to 1117, see below
#
# One deviation from their numbers: their slot 6 sits at x=1149 with a 315px
# card, so it runs 24px past a 1440 window. artlist can do that because their
# cards are square-cornered; Or's are rounded on purpose ("בכוונה עשיתי להם
# עיגול בפינות") and a rounded corner sliced by the window edge just looks
# broken. Moved to 1117 so it sits flush inside. Nothing else is changed.
#    987    936    479    191  240     48% 25%
#
# Everything is proportional to the window: at 1920 the big card measures
# 420x646 and at 2560 it is 560x862 — always 21.9% of the width. Verified at
# 1280/1440/1680/1920/2560.
CW, CH = 1440.0, 1098.19          # their container, at their reference width

SLOTS = [
    dict(x=   0, y= 12, w=315, h=427, fp='32% 56%', py=0.30, px= 0.000),
    dict(x= 245, y=100, w=191, h=240, fp='52% 29%', py=0.42, px= 0.012),
    dict(x= 135, y=499, w=135, h=180, fp='47% 33%', py=0.03, px= 0.012),
    dict(x=1096, y= 95, w=135, h=182, fp='47% 26%', py=0.04, px=-0.015),
    dict(x= 660, y=186, w=270, h=368, fp='48% 33%', py=0.015,px= 0.000),
    dict(x= 547, y=284, w=214, h=139, fp='50% 50%', py=0.43, px= 0.002),
    dict(x=1117, y=461, w=315, h=485, fp='50% 37%', py=0.015,px= 0.000),
    dict(x= 987, y=479, w=191, h=240, fp='48% 25%', py=0.39, px=-0.012),
]

# Phone, measured on the same page at 390 (page y, rebased by their -520):
MW, MH = 390.0, 560.0
MSLOTS = [
    dict(x=  0, y= 23, w=116, h=195), dict(x= 88, y= 99, w= 82, h=116),
    dict(x= 29, y=323, w= 94, h=128), dict(x=278, y= 62, w= 77, h=102),
    dict(x=186, y=132, w=112, h=150), dict(x=140, y=307, w= 91, h= 65),
    dict(x=279, y=323, w=116, h=171), dict(x=217, y=352, w= 81, h=111),
]

# One knob, on top of their numbers. 1.00 is artlist exactly.
SCALE = 1.00

# Which slots to use when Or has fewer than eight photos.
#
# ⚠️ Or, 1.9: "אל תשים אותם ככה בזיגזג למטה... תפרוס את החלק שמתחת להירו".
# artlist's eight are really two groups, and this is visible in their own
# numbers: five sit in a shallow BAND right under the hero (y 19-291, spanning
# x 0 to 85) and three sit lower (y 468-506). An earlier pass here picked
# 0,1,4,6,7 — one from each group — which drew a diagonal chain down the page.
# So the band fills first, left to right, and the lower group only joins once
# there are enough photos to need it.
PREFIX = {
    1: [0], 2: [0, 3], 3: [0, 3, 4], 4: [0, 1, 3, 4],
    5: [0, 1, 3, 4, 5],          # exactly artlist's top band
    6: [0, 1, 3, 4, 5, 7],
    7: [0, 1, 3, 4, 5, 6, 7],
}

def spread(n):
    return PREFIX.get(n, list(range(len(SLOTS))))

def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'artist'

def export():
    files = sorted(f for f in glob.glob(SRC + '/*')
                   if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')))
    files += [f for f in EXTRA if os.path.exists(f)]
    for f in EXTRA:
        if not os.path.exists(f):
            print(f'  ⚠️  named but not found: {os.path.basename(f)}')
    out = []
    for i, f in enumerate(files, 1):
        im = Image.open(f).convert('RGBA')
        if max(im.size) > 1400:
            s = 1400 / max(im.size)
            im = im.resize((round(im.width*s), round(im.height*s)), Image.LANCZOS)
        name = f'artist-{i:02d}.webp'
        # ⚠️ Or, 1.9: "בכוונה עשיתי להם עיגול בפינות". The corners are baked
        # into the source as alpha — measured: corner alpha 0, a 53-60px
        # transparent run in from each edge. An earlier pass here converted to
        # RGB JPEG, which filled those corners black and squared every photo.
        # WebP keeps the alpha and is smaller than PNG.
        im.save(os.path.join(OUT, name), 'WEBP', quality=86, method=6)
        out.append((name, im.width / im.height, os.path.basename(f)))
    return out

def cards(imgs):
    if not imgs:
        return '    <!-- no artist photos yet -->\n'
    n = min(len(imgs), len(SLOTS))
    chosen = spread(n)
    # widest BOX takes the widest photo, so a 3:2 street shot lands in the one
    # landscape slot instead of being cropped to a tall portrait
    order_slots = sorted(chosen, key=lambda si: -SLOTS[si]['w'] / SLOTS[si]['h'])
    order_imgs = sorted(range(len(imgs)), key=lambda p: -imgs[p][1])
    assign = {si: order_imgs[k % len(order_imgs)]
              for k, si in enumerate(order_slots)}
    lines = []
    for si in chosen:
        d, m = SLOTS[si], MSLOTS[si]
        name, _, orig = imgs[assign[si]]
        cx, cy = d['x'] + d['w'] / 2, d['y'] + d['h'] / 2
        w, h = d['w'] * SCALE, d['h'] * SCALE
        lines.append(
            f'    <div class="cimg" data-py="{d["py"]}" data-px="{d["px"]}"\n'
            f'         style="--x:{100*(cx-w/2)/CW:.3f}%;--y:{100*(cy-h/2)/CH:.3f}%;'
            f'--w:{100*w/CW:.3f}%;--ar:{d["w"]/d["h"]:.4f};--fp:{d["fp"]};'
            f'--mx:{100*m["x"]/MW:.3f}%;--my:{100*m["y"]/MH:.3f}%;'
            f'--mw:{100*m["w"]/MW:.3f}%;--mar:{m["w"]/m["h"]:.4f}">\n'
            f'      <img src="assets/artists/{name}" alt="" '
            f'loading="{"eager" if si in (0,1,4) else "lazy"}" decoding="async">\n'
            f'    </div>  <!-- slot {si} · {orig} -->')
    return '\n'.join(lines) + '\n'


def field_heights(*_):
    """artlist's container is 1440x1098 at their reference width and everything
    in it is proportional, so the field is just that ratio of the window."""
    return round(CH), round(MH)


def main():
    imgs = export()
    p = os.path.join(REPO, 'index.html')
    s = open(p, encoding='utf-8').read()
    a, b = '<!-- AUTO-CARDS:START -->', '<!-- AUTO-CARDS:END -->'
    if a not in s or b not in s:
        sys.exit('markers missing in index.html')
    i, j = s.index(a) + len(a), s.index(b)
    s = s[:i] + '\n' + cards(imgs) + '  ' + s[j:]
    fa, fb = '/* AUTO-FIELD:START */', '/* AUTO-FIELD:END */'
    k, l = s.index(fa) + len(fa), s.index(fb)
    s = s[:k] + (f"\n.collage{{height:clamp(700px,{100*CH/CW:.2f}vw,1500px)}}"
                 f"\n@media (max-width:820px)"
                 f"{{.collage{{height:clamp(480px,{100*MH/MW:.2f}vw,760px)}}}}\n") + s[l:]
    open(p, 'w', encoding='utf-8').write(s)
    print(f'{len(imgs)} photo(s) exported; {min(len(imgs), len(SLOTS))} of '
          f'{len(SLOTS)} artlist slots filled')
    for name, ar, orig in imgs:
        print(f'  {name}  ar={ar:.2f}  ← {orig}')

if __name__ == '__main__':
    main()
