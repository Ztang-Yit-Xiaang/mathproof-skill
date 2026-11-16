"""Animate the three-loop diagram: a pulse of energy travels through the loops and arrows.

    python3 docs/assets/loops/animate_loops.py

Renders loops-{light,dark}.svg once with headless Chrome (set CHROME to its path if it is not in
the default macOS location), then draws the moving pulse with Pillow and writes
loops-{light,dark}.gif. Route of the pulse:

  proof construction -> Lean / experiments -> failure, repair, retest, reprove -> a lap of Loop 1
  -> feedback arrow -> a lap of Loop 2 (literature <-> conjectures flash) -> generalization
  -> restart arrow -> a lap of Loop 3 -> the ledger, which lights up.
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
SPEED = 70        # pixels per frame along the route
TRAIL = 240       # length of the glowing tail in pixels
FRAME_MS = 40
HOLD = 14         # frames the ledger glows at the end


def render_base(theme: str, w: int, h: int) -> Image.Image:
    svg = HERE / f"loops-{theme}.svg"
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "base.png"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", f"--window-size={w},{h}",
                        f"--screenshot={png}", svg.as_uri()], check=True, capture_output=True)
        return Image.open(png).convert("RGB")


def hexrgb(c: str) -> tuple[int, int, int]:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def rounded_rect(x, y, w, h, r, start_x, step=3.0):
    """Points around a rounded rectangle, clockwise on screen, from (start_x, bottom edge)."""
    pts = []
    # Walk: bottom edge leftwards, left edge up, top edge right, right edge down, bottom back.
    def arc(cx, cy, a0, a1):
        n = max(2, int(abs(a1 - a0) * r / step))
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    b = y + h
    pts.append((start_x, b))
    pts.append((x + r, b))
    arc(x + r, b - r, math.pi / 2, math.pi)
    pts.append((x, y + r))
    arc(x + r, y + r, math.pi, 1.5 * math.pi)
    pts.append((x + w - r, y))
    arc(x + w - r, y + r, 1.5 * math.pi, 2 * math.pi)
    pts.append((x + w, b - r))
    arc(x + w - r, b - r, 0, math.pi / 2)
    pts.append((start_x, b))
    return pts


def densify(pts, step=3.0):
    out = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / step))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(1, n + 1)]
    return out


def route(G, t):
    """The pulse's route as a list of (point, color, active loop)."""
    c1, c2, c3 = t["l1"], t["l2"], t["l3"]
    cx = G["W"] / 2
    X1, Y1, W1, H1, R1 = G["L1"]
    X2, Y2, W2, H2, R2 = G["L2"]
    X3, Y3, W3, H3, R3 = G["L3"]
    px, py, pw, ph = G["proof"]
    lx, ly, lw, lh = G["lean"]
    gx, gy, gw, gh = G["gen"]
    cyc_y = G["cycle_y"]
    cx0, cx1 = G["cycle_x"]
    lx_mid = lx + lw / 2
    segs = [
        ([(px + pw / 2, py + ph / 2), (px + pw / 2, py + ph), (lx_mid, ly)], c1, "L1"),
        ([(lx_mid, ly), (lx_mid, ly + lh), (cx0, cyc_y)], c1, "L1"),
        ([(cx0, cyc_y), (cx1, cyc_y), (cx1, Y1 + H1)], c1, "L1"),
        (rounded_rect(X1, Y1, W1, H1, R1, cx1), c1, "L1"),
        ([(cx1, Y1 + H1), (cx, Y1 + H1), (cx, Y2 + H2)], c2, "L2"),
        (rounded_rect(X2, Y2, W2, H2, R2, cx), c2, "L2"),
        ([(cx, Y2 + H2), (cx, gy), (cx, gy + gh), (cx, Y3 + H3)], c3, "L3"),
        (rounded_rect(X3, Y3, W3, H3, R3, cx), c3, "L3"),
        ([(cx, Y3 + H3), (cx, G["ledger"][1])], t["ink2"], "ledger"),
    ]
    out = []
    for pts, color, active in segs:
        for p in densify(pts):
            out.append((p, color, active))
    return out


def glow_outline(draw, box, color, alpha, width=6):
    x, y, w, h, r = box
    draw.rounded_rectangle([x, y, x + w, y + h], r, outline=(*hexrgb(color), alpha), width=width)


def frames_for(theme: str):
    t = diagram.THEMES[theme]
    diagram.draw(theme)
    G = dict(diagram.GEO)
    base = render_base(theme, G["W"], G["H"])
    path = route(G, t)
    step = 3.0
    per_frame = int(SPEED / step)
    heads = list(range(0, len(path), per_frame)) + [len(path) - 1] * HOLD
    trail_n = int(TRAIL / step)
    dark = theme == "dark"
    boxes = {"L1": G["L1"], "L2": G["L2"], "L3": G["L3"], "ledger": G["ledger"]}
    lit, conj = G["lit"], G["conj"]

    frames = []
    for k, head in enumerate(heads):
        _, color, active = path[head]
        halo = Image.new("RGBA", base.size, (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)
        # The loop the pulse is in glows softly.
        pulse = 0.6 + 0.4 * math.sin(k / 3)
        box_color = {"L1": t["l1"], "L2": t["l2"], "L3": t["l3"], "ledger": t["ink3"]}[active]
        glow_outline(hd, boxes[active], box_color, int((110 if dark else 80) * pulse), 8)
        if active == "L2":  # literature <-> conjectures exchange
            sx = lit[0] + lit[2] + 45
            for i, d in enumerate((-1, 1)):
                ph = ((k * 6 + i * 45) % 90) / 90
                x = sx + d * (ph - 0.5) * 70
                hd.ellipse([x - 7, lit[1] + 40 - 7 + i * 12, x + 7, lit[1] + 40 + 7 + i * 12],
                           fill=(*hexrgb(t["l2"]), int(200 * math.sin(math.pi * ph))))
        if k >= len(heads) - HOLD:  # the ledger lights up at the end
            fade = 1 - (k - (len(heads) - HOLD)) / HOLD
            glow_outline(hd, boxes["ledger"], t["l1"], int(160 * fade), 10)
        # Tail: fading, thinning dots behind the head.
        for j in range(trail_n, -1, -1):
            i = head - j
            if i < 0:
                continue
            (x, y), c, _ = path[i]
            f = 1 - j / trail_n
            r = 2 + 6 * f
            hd.ellipse([x - r, y - r, x + r, y + r], fill=(*hexrgb(c), int(230 * f * f)))
        glow = halo.filter(ImageFilter.GaussianBlur(7))
        core = Image.new("RGBA", base.size, (0, 0, 0, 0))
        cd = ImageDraw.Draw(core)
        for j in range(int(trail_n * 0.45), -1, -1):
            i = head - j
            if i < 0:
                continue
            (x, y), c, _ = path[i]
            f = 1 - j / (trail_n * 0.45)
            r = 1 + 2.6 * f
            cd.ellipse([x - r, y - r, x + r, y + r], fill=(*hexrgb(c), int(255 * f)))
        if k < len(heads) - HOLD:
            (x, y), c, _ = path[head]
            hot = (255, 255, 255, 235) if dark else (*hexrgb(c), 255)
            cd.ellipse([x - 4, y - 4, x + 4, y + 4], fill=hot)
        im = Image.alpha_composite(base.convert("RGBA"), glow)
        if dark:  # a second pass makes the glow read on a dark background
            im = Image.alpha_composite(im, glow)
        im = Image.alpha_composite(im, core)
        frames.append(im.convert("RGB"))
    return frames


def save_gif(frames, path: Path) -> None:
    # One palette for every frame, so colors don't flicker.
    sample = Image.new("RGB", (frames[0].width, frames[0].height * 3))
    for i, f in enumerate((frames[0], frames[len(frames) // 2], frames[-HOLD])):
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
