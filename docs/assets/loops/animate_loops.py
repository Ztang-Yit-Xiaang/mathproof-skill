"""Animate the three-loop diagram: energy flows along every arrow and lights up every box.

    python3 docs/assets/loops/animate_loops.py

Renders loops-{light,dark}.svg once with headless Chrome (set CHROME to its path if it is not in
the default macOS location), then draws the energy with Pillow and writes loops-{light,dark}.gif.

One pass of the animation:
  1. Proof construction lights up; pulses run down the arrow to Lean 4 and to R / Python.
  2. Both feed the repair cycle; failure, repair, retest, reprove light up in turn; a lap of Loop 1.
  3. New evidence flows up to Literature and Conjectures, which exchange pulses; a lap of Loop 2.
  4. Down the arrow into Generalization and its three directions; the restart arrow; a lap of Loop 3.
  5. Down into the ledger, whose records light up one by one.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_loops_svg as diagram  # noqa: E402

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
STEP = 3.0        # spacing of path samples, in pixels
SPEED = 66        # pixels per frame
TRAIL = 200       # glowing tail, in pixels
FRAME_MS = 40
HOLD = 16         # frames at the end while the ledger glows


def render_base(theme: str, w: int, h: int) -> Image.Image:
    svg = HERE / f"loops-{theme}.svg"
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "base.png"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp}/profile",
                        "--force-device-scale-factor=1", f"--window-size={w},{h}",
                        f"--screenshot={png}", svg.as_uri()], check=True, capture_output=True)
        return Image.open(png).convert("RGB")


def rgb(c: str) -> tuple[int, int, int]:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def densify(pts):
    out = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / STEP))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(1, n + 1)]
    return out


def lap(box, start_x):
    """Points once around a rounded rectangle, clockwise on screen, from (start_x, bottom)."""
    x, y, w, h, r = box
    b, pts = y + h, [(start_x, y + h), (x + r, y + h)]

    def arc(cx, cy, a0, a1):
        n = max(2, int(abs(a1 - a0) * r / STEP))
        pts.extend((cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n))
                   for i in range(n + 1))
    arc(x + r, b - r, math.pi / 2, math.pi)
    arc(x + r, y + r, math.pi, 1.5 * math.pi)
    arc(x + w - r, y + r, 1.5 * math.pi, 2 * math.pi)
    arc(x + w - r, b - r, 0, math.pi / 2)
    pts.append((start_x, b))
    return pts


def center(box):
    return box[0] + box[2] / 2, box[1] + box[3] / 2


class Timeline:
    def __init__(self):
        self.sparks = []   # (start frame, points, color)
        self.glows = []    # (start frame, end frame, box, color)

    def spark(self, start, pts, color):
        pts = densify(pts)
        self.sparks.append((start, pts, color))
        return start + len(pts) * STEP / SPEED   # frame when the head arrives

    def glow(self, start, box, color, hold=10):
        self.glows.append((start, start + hold, box, color))

    def chips_along(self, start, boxes, color, gap=3):
        for i, b in enumerate(boxes):
            self.glow(start + i * gap, b, color, 6)
        return start + len(boxes) * gap


# Glow colors. On the light theme the loop colors are too dark to read as light, so use vivid ones.
HOT = {"light": ("#22c55e", "#3b82f6", "#8b5cf6", "#64748b"), "dark": None}


def build(G, t, theme) -> Timeline:
    c1, c2, c3, ink = HOT[theme] or (t["l1"], t["l2"], t["l3"], t["ink2"])
    tl = Timeline()
    cx = G["W"] / 2
    X1, Y1, W1, H1, _ = G["L1"]
    X2, Y2, W2, H2, _ = G["L2"]
    X3, Y3, W3, H3, _ = G["L3"]
    proof = (*G["proof"], 12)
    lean, exp = (*G["lean"], 12), (*G["exp"], 12)
    lit, conj, gen = (*G["lit"], 12), (*G["conj"], 12), (*G["gen"], 12)
    chips = G["cycle_chips"]
    dot = lambda x, y, r=12: (x - r, y - r, 2 * r, 2 * r, r)  # noqa: E731

    # 1. Proof construction, then the arrow down to both checks.
    tl.glow(0, proof, c1, 12)
    pcx, pby = proof[0] + proof[2] / 2, proof[1] + proof[3]
    tl.glow(4, dot(pcx, pby + 12), c1, 6)
    lcx, ecx = center(lean)[0], center(exp)[0]
    t1 = tl.spark(4, [(pcx, pby), (pcx, pby + 12), (lcx, lean[1])], c1)
    tl.spark(4, [(pcx, pby), (pcx, pby + 12), (ecx, exp[1])], c1)
    tl.glow(t1, lean, c1, 12)
    tl.glow(t1, exp, c1, 12)

    # 2. Both checks feed the repair cycle, which runs left to right, then a lap of Loop 1.
    c0x, cy = center(chips[0])
    c3x = center(chips[-1])[0]
    t2 = tl.spark(t1 + 4, [(lcx, lean[1] + lean[3]), (c0x, chips[0][1])], c1)
    tl.spark(t1 + 4, [(ecx, exp[1] + exp[3]), (c0x + 30, chips[0][1])], c1)
    path = [(c0x, cy)] + [center(b) for b in chips[1:]]
    t3 = tl.spark(t2, path, c1)
    seg = (t3 - t2) / (len(chips) - 1)
    for i, b in enumerate(chips):
        tl.glow(t2 + i * seg, b, c1, 7)
    t4 = tl.spark(t3, [(c3x, cy), (c3x, Y1 + H1)], c1)
    t5 = tl.spark(t4, lap(G["L1"], c3x), c1)
    tl.glow(t4, G["L1"], c1, t5 - t4)

    # 3. New evidence: up to Literature and Conjectures, which exchange; then a lap of Loop 2.
    fx, fy = G["fb_icons"][0]
    tl.glow(t5, dot(fx, fy), c2, 8)
    lx, kx = center(lit)[0], center(conj)[0]
    mid = (lit[1] + lit[3] + Y1) / 2
    up = lambda x_side, x_to: [(cx, Y1 + H1), (cx, Y1 + H1 + 12), (x_side, Y1 + H1 + 12),  # noqa: E731
                               (x_side, mid), (x_to, mid), (x_to, lit[1] + lit[3])]
    t6 = tl.spark(t5, up(X2 + 10, lx), c2)
    tl.spark(t5, up(X2 + W2 - 10, kx), c2)
    tl.glow(t6, lit, c2, 12)
    tl.glow(t6, conj, c2, 12)
    sy = lit[1] + 52
    tl.glow(t6 + 2, dot((lit[0] + lit[2] + conj[0]) / 2, sy, 16), c2, 8)
    t7 = tl.spark(t6 + 2, [(lit[0] + lit[2], sy - 6), (conj[0], sy - 6)], c2)
    tl.spark(t6 + 2, [(conj[0], sy + 6), (lit[0] + lit[2], sy + 6)], c2)
    tl.glow(t7, lit, c2, 6)
    tl.glow(t7, conj, c2, 6)
    t8 = tl.spark(t7, lap(G["L2"], cx), c2)
    tl.glow(t7, G["L2"], c2, t8 - t7)

    # 4. Generalization, its three directions, the restart arrow, then a lap of Loop 3.
    tl.glow(t8, dot(cx, Y2 + H2 + 14), c3, 6)
    t9 = tl.spark(t8, [(cx, Y2 + H2), (cx, gen[1])], c3)
    tl.glow(t9, gen, c3, 14)
    tl.chips_along(t9 + 3, G["gen_chips"], c3)
    t10 = tl.spark(t9 + 4, [(cx, gen[1] + gen[3]), (cx, Y3 + H3)], c3)
    rx, ry = G["fb_icons"][1]
    tl.glow(t10 - 3, dot(rx, ry), c3, 8)
    t11 = tl.spark(t10, lap(G["L3"], cx), c3)
    tl.glow(t10, G["L3"], c3, t11 - t10)

    # 5. Into the ledger.
    t12 = tl.spark(t11, [(cx, Y3 + H3), (cx, G["ledger"][1])], ink)
    tl.glow(t12, G["ledger"], c1, HOLD)
    tl.chips_along(t12 + 2, G["ledger_chips"], c1, 2)
    tl.end = int(t12 + HOLD + 4)
    return tl


def outline(draw, box, color, alpha, width):
    x, y, w, h, r = box
    draw.rounded_rectangle([x, y, x + w, y + h], r, outline=(*rgb(color), alpha), width=width)


def frames_for(theme: str):
    t = diagram.THEMES[theme]
    diagram.draw(theme)
    G = {k: (list(v) if isinstance(v, list) else v) for k, v in diagram.GEO.items()}
    base = render_base(theme, G["W"], G["H"]).convert("RGBA")
    tl = build(G, t, theme)
    dark = theme == "dark"
    per = SPEED / STEP
    trail_n = int(TRAIL / STEP)

    frames = []
    for f in range(tl.end):
        halo = Image.new("RGBA", base.size, (0, 0, 0, 0))
        core = Image.new("RGBA", base.size, (0, 0, 0, 0))
        hd, cd = ImageDraw.Draw(halo), ImageDraw.Draw(core)
        for start, end, box, color in tl.glows:
            if not (start <= f <= end + 12):
                continue
            a = min(1.0, (f - start + 1) / 3) if f <= end else max(0.0, 1 - (f - end) / 12)
            outline(hd, box, color, int((200 if dark else 170) * a), 7)
            outline(cd, box, color, int(255 * a), 2)
        for start, pts, color in tl.sparks:
            head = int((f - start) * per)
            if head < 0 or head - trail_n >= len(pts):
                continue
            for j in range(trail_n, -1, -1):
                i = head - j
                if 0 <= i < len(pts):
                    x, y = pts[i]
                    k = 1 - j / trail_n
                    r = 2 + 6 * k
                    hd.ellipse([x - r, y - r, x + r, y + r], fill=(*rgb(color), int(220 * k * k)))
                    if j < trail_n * 0.45:
                        k2 = 1 - j / (trail_n * 0.45)
                        r2 = 1 + 2.4 * k2
                        cd.ellipse([x - r2, y - r2, x + r2, y + r2], fill=(*rgb(color), int(255 * k2)))
            if head < len(pts):
                x, y = pts[head]
                hot = (255, 255, 255, 240) if dark else (*rgb(color), 255)
                cd.ellipse([x - 4, y - 4, x + 4, y + 4], fill=hot)
        glow = halo.filter(ImageFilter.GaussianBlur(6))
        im = Image.alpha_composite(base, glow)
        if dark:
            im = Image.alpha_composite(im, glow)
        frames.append(Image.alpha_composite(im, core).convert("RGB"))
    return frames


def save_gif(frames, path: Path) -> None:
    # One palette for every frame, so colors don't flicker.
    picks = [frames[i] for i in (0, len(frames) // 4, len(frames) // 2, 3 * len(frames) // 4, -1)]
    sample = Image.new("RGB", (frames[0].width, frames[0].height * len(picks)))
    for i, f in enumerate(picks):
        sample.paste(f, (0, i * frames[0].height))
    pal = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=FRAME_MS, loop=0, optimize=True, disposal=1)


def main() -> None:
    for theme in diagram.THEMES:
        frames = frames_for(theme)
        out = HERE / f"loops-{theme}.gif"
        save_gif(frames, out)
        print(out.name, len(frames), "frames", out.stat().st_size // 1024, "KiB")


if __name__ == "__main__":
    main()
