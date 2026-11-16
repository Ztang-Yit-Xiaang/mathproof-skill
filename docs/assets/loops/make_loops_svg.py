"""Draw the three-loop architecture diagram as light and dark SVGs for the README.

    python3 docs/assets/loops/make_loops_svg.py

The website draws the same diagram in HTML and CSS (section #loops of docs/index.html).
Keep the two in step when either changes.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
W = 960
FONT = "Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
SERIF = "'Source Serif 4', Georgia, 'Times New Roman', serif"

THEMES = {
    "light": dict(bg="#fbfaf7", surface="#ffffff", sunk="#f3f1ec", ink="#1b1d22", ink2="#4a4f5a", ink3="#7a808c",
                  line="#e4e1d9", l1="#1f7a4d", l1s="#eef7f1", l2="#1d3b6a", l2s="#eef2f9", l3="#5b3fa0",
                  l3s="#f4f0fb", ok="#1f7a4d", oks="#e5f3eb", warn="#97650d", warns="#fbf1dc"),
    "dark": dict(bg="#111317", surface="#181b21", sunk="#14161b", ink="#e9e7e2", ink2="#b4b6bd", ink3="#868a94",
                 line="#2a2e37", l1="#6cc79a", l1s="#132119", l2="#8fb3ec", l2s="#141c29", l3="#b9a0f0",
                 l3s="#1c1729", ok="#6cc79a", oks="#16281f", warn="#e2b45e", warns="#2b2312"),
}

ICONS = {
    "cycle": '<path d="M13.5 6.5A5.5 5.5 0 0 0 3.2 4.6M2.5 9.5a5.5 5.5 0 0 0 10.3 1.9M2.6 2.2v2.8h2.8M13.4 13.8V11h-2.8"/>',
    "book": '<path d="M2 3.2c2-.9 4-.9 6 .4 2-1.3 4-1.3 6-.4v9.6c-2-.9-4-.9-6 .4-2-1.3-4-1.3-6-.4z M8 3.6v9.6"/>',
    "bulb": '<path d="M8 1.8a4.4 4.4 0 0 0-2.6 8c.5.4.8 1 .8 1.6v.4h3.6v-.4c0-.6.3-1.2.8-1.6A4.4 4.4 0 0 0 8 1.8zM6.4 14.2h3.2"/>',
    "shield": '<path d="M8 1.5l5.5 2.2v4c0 3.3-2.3 5.7-5.5 6.8-3.2-1.1-5.5-3.5-5.5-6.8v-4z M5.6 8.2l1.7 1.7 3.2-3.4"/>',
    "flask": '<path d="M6 1.8h4M6.6 1.8v4.4L2.9 12.6c-.6 1 .1 2 1.2 2h7.8c1.1 0 1.8-1 1.2-2L9.4 6.2V1.8M4.6 10h6.8"/>',
    "spark": '<path d="M8 1.5v3M8 11.5v3M1.5 8h3M11.5 8h3M3.4 3.4l2.1 2.1M10.5 10.5l2.1 2.1M3.4 12.6l2.1-2.1M10.5 5.5l2.1-2.1"/>',
    "db": '<ellipse cx="8" cy="3.6" rx="5.3" ry="2"/><path d="M2.7 3.6v8.8c0 1.1 2.4 2 5.3 2s5.3-.9 5.3-2V3.6M2.7 8c0 1.1 2.4 2 5.3 2s5.3-.9 5.3-2"/>',
    "down": '<path d="M8 2v11M4 9l4 4 4-4"/>',
    "swap": '<path d="M2 5.5h11l-2.5-2.5M14 10.5H3l2.5 2.5"/>',
}


GEO: dict = {}  # layout of the last drawing, used by animate_loops.py


class SVG:
    def __init__(self, t: dict):
        self.t = t
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def rect(self, x, y, w, h, r, fill, stroke=None, sw=1.0, dash=None):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{st}{da}/>')

    def text(self, x, y, s, size=13, fill=None, weight=400, anchor="start", family=FONT, spacing=None):
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
                 f'fill="{fill or self.t["ink"]}" text-anchor="{anchor}"{ls}>{escape(s)}</text>')

    def icon(self, name, x, y, color, size=16):
        k = size / 16
        self.add(f'<g transform="translate({x} {y}) scale({k})" fill="none" stroke="{color}" stroke-width="1.5" '
                 f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g>')

    def pill(self, x_right, y, label, kind):
        t = self.t
        fg, bg, dash = {"now": (t["ok"], t["oks"], None), "part": (t["warn"], t["warns"], None),
                        "plan": (t["ink3"], t["sunk"], "3 3")}[kind]
        w = len(label) * 6.9 + 20
        x = x_right - w
        self.rect(x, y, w, 22, 11, bg, t["line"] if dash else None, 1, dash)
        self.text(x + w / 2, y + 15, label.upper(), 10.5, fg, 700, "middle", spacing="0.6")
        return x

    def ring(self, cx, cy, label, color):
        t = self.t
        self.add(f'<circle cx="{cx}" cy="{cy}" r="16" fill="{t["surface"]}" stroke="{color}" stroke-width="1.5"/>')
        # Two arcs around the badge suggest a cycle.
        self.add(f'<path d="M{cx} {cy-22} A22 22 0 0 1 {cx+21.3} {cy-5.5}" fill="none" stroke="{color}" '
                 f'stroke-width="1.5" stroke-linecap="round" opacity=".55"/>')
        self.add(f'<path d="M{cx} {cy+22} A22 22 0 0 1 {cx-21.3} {cy+5.5}" fill="none" stroke="{color}" '
                 f'stroke-width="1.5" stroke-linecap="round" opacity=".55"/>')
        self.text(cx, cy + 5.5, label, 15, color, 700, "middle", SERIF)

    def header(self, x, y, w, num, title, sub, color, pill, kind):
        self.ring(x + 22, y + 22, num, color)
        self.text(x + 54, y + 19, title, 18, self.t["ink"], 600, family=SERIF)
        self.text(x + 54, y + 39, sub, 13, self.t["ink2"])
        self.pill(x + w, y + 6, pill, kind)

    def node(self, x, y, w, h, title, lines, color, icon=None, center=False, ghost=False, pill=None):
        t = self.t
        self.rect(x, y, w, h, 12, t["surface"], t["line"], 1, "4 4" if ghost else None)
        tx = x + w / 2 if center else x + 16
        anchor = "middle" if center else "start"
        if icon:
            tw = len(title) * 7.6
            ix = (tx - tw / 2 - 22) if center else tx
            self.icon(icon, ix, y + 13, color)
            if not center:
                tx += 24
        self.text(tx if not (icon and center) else tx + 11, y + 26, title, 14.5, t["ink"], 600, anchor)
        for i, line in enumerate(lines):
            self.text(x + w / 2 if center else x + 16, y + 46 + 18 * i, line, 12.5, t["ink2"], 400, anchor)
        if pill:
            label, kind = pill
            w2 = len(label) * 6.9 + 20
            self.pill(x + 16 + w2, y + h - 34, label, kind)

    def feedback(self, cx, y, s, color):
        tw = len(s) * 6.05
        self.icon("cycle", cx - tw / 2 - 12, y - 12, color)
        self.text(cx + 10, y, s, 12.5, self.t["ink2"], 400, "middle")

    def chips(self, cx, y, labels):
        t = self.t
        widths = [len(s) * 6.6 + 18 for s in labels]
        x = cx - (sum(widths) + 8 * (len(labels) - 1)) / 2
        for s, w in zip(labels, widths):
            self.rect(x, y, w, 22, 6, t["sunk"])
            self.text(x + w / 2, y + 15, s, 11.5, t["ink2"], 500, "middle")
            x += w + 8


def draw(theme: str) -> str:
    t = THEMES[theme]
    g = SVG(t)

    # Loop 3, the outer box.
    X3, Y3, W3, H3 = 16, 16, W - 32, 830
    g.rect(X3, Y3, W3, H3, 20, t["l3s"], t["l3"], 1.5)
    g.header(X3 + 22, Y3 + 18, W3 - 44, "3", "Research frontier",
             "Turn proved results into broader theorems and new questions.", t["l3"], "Planned · M3", "plan")

    # Loop 2.
    X2, Y2, W2, H2 = X3 + 22, Y3 + 82, W3 - 44, 560
    g.rect(X2, Y2, W2, H2, 18, t["l2s"], t["l2"], 1.5)
    g.header(X2 + 20, Y2 + 16, W2 - 40, "2", "Hypotheses and knowledge",
             "Are we proving the right theorem, under the right assumptions?", t["l2"], "Partly today", "part")
    nx, ny, nw, nh = X2 + 20, Y2 + 80, (W2 - 40 - 90) / 2, 112
    g.node(nx, ny, nw, nh, "Literature", ["Find, compare and reconcile published theorems,",
                                          "with the exact statement and its hypotheses."],
           t["l2"], "book", pill=("Today · RESEARCH mode", "now"))
    g.icon("swap", nx + nw + 33, ny + 40, t["l2"], 24)
    g.text(nx + nw + 45, ny + 82, "FEEDBACK", 10, t["ink3"], 600, "middle", spacing="0.8")
    g.node(nx + nw + 90, ny, nw, nh, "Conjectures", ["Propose and revise assumptions and claims;",
                                                    "a revision is a new, linked claim."],
           t["l2"], "bulb", ghost=True, pill=("Planned · M2", "plan"))

    # Loop 1.
    X1, Y1, W1, H1 = X2 + 20, ny + nh + 18, W2 - 40, 300
    g.rect(X1, Y1, W1, H1, 16, t["surface"], t["l1"], 1.5)
    g.header(X1 + 20, Y1 + 16, W1 - 40, "1", "Proof and falsification",
             "Can we prove or disprove this exact claim?", t["l1"], "Working today", "now")
    px, pw = X1 + 20, W1 - 40
    g.node(px, Y1 + 78, pw, 62, "Proof construction",
           ["Split the claim into lemmas and implications, then attack each step."], t["l1"], center=True)
    g.icon("down", px + pw / 2 - 7, Y1 + 145, t["ink3"], 14)
    fw = (pw - 12) / 2
    g.node(px, Y1 + 164, fw, 80, "Lean 4 + Mathlib", ["Proof or refutation, checked by the kernel;",
                                                      "sorry and custom axioms are rejected."],
           t["l1"], "shield", center=True)
    g.node(px + fw + 12, Y1 + 164, fw, 80, "R / Python experiments", ["Seeded falsification tests, hashed and",
                                                                     "re-runnable. Evidence, never proof."],
           t["l1"], "flask", center=True)
    # failure -> repair -> retest -> reprove
    steps = ["failure", "repair", "retest", "reprove"]
    widths = [len(s) * 7 + 22 for s in steps]
    total = sum(widths) + 26 * 3 + 26
    x = px + pw / 2 - total / 2
    cy = Y1 + 262
    g.icon("cycle", x, cy + 3, t["l1"])
    x += 26
    for i, (s, w) in enumerate(zip(steps, widths)):
        g.rect(x, cy, w, 24, 12, t["surface"], t["l1"], 1)
        g.text(x + w / 2, cy + 16, s, 12, t["ink2"], 500, "middle")
        x += w
        if i < 3:
            g.text(x + 13, cy + 16, "→", 13, t["l1"], 600, "middle")
            x += 26

    g.feedback(X2 + W2 / 2, Y1 + H1 + 30, "New evidence → revise the conjecture and search the literature again", t["l2"])

    # Generalization.
    gy = Y2 + H2 + 14
    g.icon("down", X3 + W3 / 2 - 7, gy, t["l3"], 14)
    g.node(X2, gy + 22, W2, 104, "Generalization",
           ["Probe which hypotheses are really needed, then propose stronger results."], t["l3"], "spark",
           center=True, ghost=True)
    g.chips(X2 + W2 / 2, gy + 84, ["weaken assumptions", "strengthen conclusions", "explore extensions"])
    g.feedback(X3 + W3 / 2, gy + 152, "A new theorem family or question → restart the whole cycle", t["l3"])

    # The ledger, shared by all loops.
    RY = Y3 + H3 + 26
    g.add(f'<line x1="{W/2}" y1="{Y3+H3+2}" x2="{W/2}" y2="{RY-2}" stroke="{t["ink3"]}" stroke-width="2" '
          f'stroke-dasharray="2 4" stroke-linecap="round"/>')
    g.rect(X3, RY, W3, 112, 16, t["surface"], t["line"], 1)
    g.add(f'<rect x="{X3+28}" y="{RY+18}" width="34" height="34" rx="9" fill="{t["surface"]}" '
          f'stroke="{t["ink3"]}" stroke-width="1.5"/>')
    g.icon("db", X3 + 35, RY + 25, t["ink2"], 20)
    g.text(X3 + 76, RY + 36, "Theorem and evidence ledger", 18, t["ink"], 600, family=SERIF)
    g.text(X3 + 76, RY + 56, "Shared by all three loops. Append-only and hash-chained; every status is derived from it.",
           13, t["ink2"])
    g.pill(X3 + W3 - 22, RY + 24, "Working today", "now")
    g.chips(W / 2, RY + 74, ["claims", "proofs", "counterexamples", "failed attempts", "assumptions",
                             "citations", "experiment records", "fidelity reviews"])

    H = RY + 112 + 16
    GEO.update(W=W, H=H, L3=(X3, Y3, W3, H3, 20), L2=(X2, Y2, W2, H2, 18), L1=(X1, Y1, W1, H1, 16),
               ledger=(X3, RY, W3, 112, 16), proof=(px, Y1 + 78, pw, 62), lean=(px, Y1 + 164, fw, 80),
               exp=(px + fw + 12, Y1 + 164, fw, 80), lit=(nx, ny, nw, nh), conj=(nx + nw + 90, ny, nw, nh),
               gen=(X2, gy + 22, W2, 104), cycle_y=cy + 12, cycle_x=(px + pw / 2 - total / 2 + 26, x),
               fb2_y=Y1 + H1 + 30, fb3_y=gy + 152)
    body = "\n  ".join(g.parts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Three nested loops: proof and falsification inside hypotheses and knowledge inside the '
            f'research frontier, all sharing one ledger">\n  <rect width="{W}" height="{H}" rx="18" fill="{t["bg"]}"/>\n'
            f'  {body}\n</svg>\n')


def main() -> None:
    for theme in THEMES:
        (HERE / f"loops-{theme}.svg").write_text(draw(theme), encoding="utf-8")
        print(f"loops-{theme}.svg")


if __name__ == "__main__":
    main()
