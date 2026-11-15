"""Render the two README / website demo GIFs.

    python3 docs/demo/render_gifs.py

Needs Pillow and the Menlo font (macOS). The terminal text is the real output of the
session in docs/demo/session.json (recorded with the commands shown), with long lines cut
with "…" and the JSON of `check` and `status` shortened to its main fields. Nothing here runs Lean.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
W, H = 720, 500
PAD = 18
TITLE_H = 30
FONT = "/System/Library/Fonts/Menlo.ttc"
SIZE = 13
LINE = 19

BG = (21, 24, 29)
BAR = (32, 36, 43)
INK = (233, 231, 226)
DIM = (134, 138, 148)
GREEN = (108, 199, 154)
BLUE = (143, 179, 236)
AMBER = (226, 180, 94)
RED = (240, 138, 128)
PURPLE = (196, 160, 236)

font = ImageFont.truetype(FONT, SIZE)
bold = ImageFont.truetype(FONT, SIZE, index=1)
title_font = ImageFont.truetype(FONT, 12)


def window(title: str) -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, TITLE_H], fill=BAR)
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (98, 197, 84)]):
        d.ellipse([14 + 20 * i, 10, 26 + 20 * i, 22], fill=c)
    tw = d.textlength(title, font=title_font)
    d.text(((W - tw) / 2, 8), title, font=title_font, fill=DIM)
    return im


# A line is a list of (text, color, bold) spans.
def draw_lines(im: Image.Image, lines: list[list[tuple]], top: int = TITLE_H + 12) -> None:
    d = ImageDraw.Draw(im)
    rows = (H - top - PAD) // LINE
    for r, spans in enumerate(lines[-rows:]):
        x = PAD
        for text, color, is_bold in spans:
            f = bold if is_bold else font
            d.text((x, top + r * LINE), text, font=f, fill=color)
            x += d.textlength(text, font=f)


def S(text, color=INK, b=False):
    return (text, color, b)


class Movie:
    def __init__(self, title: str):
        self.title = title
        self.frames: list[Image.Image] = []
        self.durations: list[int] = []
        self.lines: list[list[tuple]] = []

    def snap(self, ms: int, extra: list[list[tuple]] | None = None) -> None:
        im = window(self.title)
        draw_lines(im, self.lines + (extra or []))
        self.frames.append(im)
        self.durations.append(ms)

    def comment(self, text: str, hold: int = 700) -> None:
        self.lines.append([S(text, AMBER, True)])
        self.snap(hold)

    def type(self, cmd: str, prompt: str = "$ ", step: int = 4) -> None:
        for i in range(0, len(cmd) + 1, step):
            self.snap(45, [[S(prompt, GREEN, True), S(cmd[:i] + "▌")]])
        self.lines.append([S(prompt, GREEN, True), S(cmd)])
        self.snap(350)

    def out(self, spans_list: list[list[tuple]], each: int = 90, hold: int = 900) -> None:
        for spans in spans_list:
            self.lines.append(spans)
            self.snap(each)
        self.durations[-1] = hold

    def blank(self) -> None:
        self.lines.append([S("")])

    def save(self, path: Path) -> None:
        pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in self.frames]
        pal[0].save(path, save_all=True, append_images=pal[1:], duration=self.durations,
                    loop=0, optimize=True, disposal=1)


def plain(text: str, color=INK) -> list[tuple]:
    return [S(text, color)]


def terminal_gif(session: dict) -> Movie:
    m = Movie("Terminal: using MathProof Skill")
    m.comment("# 1. Ask Claude Code, with the skill installed")
    m.type("/mathproof-skill Audit this and verify in Lean: if f'(x0)=0,", prompt="> ")
    m.lines[-1] = [S("> ", BLUE, True), S("/mathproof-skill ", PURPLE, True),
                   S("Audit this and verify in Lean: if f'(x0)=0,")]
    m.out([plain("  then f has a global minimum at x0.")], hold=500)
    m.out([
        [S("  Verdict ", DIM), S("INVALID", RED, True), S("  first unsupported step: 'critical, so minimum'", DIM)],
        [S("  Counterexample ", DIM), S("f(x) = -x²", INK, True), S(" at 0:  f(1) = -1 < 0 = f(0)", DIM)],
        [S("  Lean file: lean/MathProofSkill/Evals/Optimization001.lean", DIM)],
    ], each=250, hold=1300)
    m.blank()
    m.comment("# 2. The skill records the claim in a ledger")
    m.type("mathproof init demo")
    m.out([plain(l, DIM) for l in session["init"]], hold=400)
    m.type("mathproof claim add --id demo/critical-point --kind theorem ...")
    m.out([plain(l, DIM) for l in session["claim"]], hold=500)
    m.blank()
    m.comment("# 3. The Lean kernel checks the refutation")
    m.type("mathproof check --polarity negation --decl claim_false Optimization001.lean")
    m.out([[S(l, GREEN if "pass" in l else DIM)] for l in session["check"]], each=200, hold=900)
    m.blank()
    m.comment("# 4. The status is derived from the ledger, never typed in")
    m.type("mathproof status --claim demo/critical-point")
    m.out([[S(l, BLUE)] for l in session["status"]], each=120, hold=2600)
    return m


def theorem_gif(session: dict) -> Movie:
    lean = (HERE.parents[1] / "lean/MathProofSkill/Evals/Optimization001.lean").read_text(encoding="utf-8").splitlines()
    m = Movie("Open the theorem: Optimization001.lean")
    m.type("mathproof report --claim demo/critical-point")
    report = [l if len(l) <= 86 else l[:85] + "…" for l in session["report"]]
    m.out([[S(l, INK if l.startswith(("#", "**")) else DIM, l.startswith(("#", "**")))] for l in report],
          each=110, hold=1800)
    m.lines = []
    m.type("open lean/MathProofSkill/Evals/Optimization001.lean")
    m.lines = []
    kw = ("def ", "theorem ", "namespace ", "open ", "end ", "import ")
    for i, l in enumerate(lean, 1):
        l = l if len(l) <= 80 else l[:79] + "…"
        num = S(f"{i:>3}  ", DIM)
        s = l.strip()
        if s.startswith(("/-", "#", "Informal", "Expected", "-/")):
            spans = [num, S(l, DIM)]
        elif s.startswith(kw):
            k = next(k for k in kw if s.startswith(k))
            spans = [num, S(l[: l.index(k) + len(k)], PURPLE, True), S(l[l.index(k) + len(k):], INK)]
        elif "have" in l or "intro" in l or "norm_num" in l:
            spans = [num, S(l, BLUE)]
        else:
            spans = [num, S(l, INK)]
        m.lines.append(spans)
        m.snap(140)
    m.durations[-1] = 1200
    m.lines.append([S("")])
    m.lines.append([S("  ✓ kernel-passed-local  ", GREEN, True), S("axioms: propext, Classical.choice, Quot.sound", DIM)])
    m.snap(3200)
    return m


def main() -> None:
    session = json.loads((HERE / "session.json").read_text(encoding="utf-8"))
    terminal_gif(session).save(HERE / "terminal-steps.gif")
    theorem_gif(session).save(HERE / "open-theorem.gif")
    for name in ("terminal-steps.gif", "open-theorem.gif"):
        p = HERE / name
        print(name, Image.open(p).n_frames, "frames", p.stat().st_size // 1024, "KiB")


if __name__ == "__main__":
    main()
