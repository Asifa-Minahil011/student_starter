"""Draw the state-transition diagram (report Figure 1) FROM THE MODEL.

The accepted transitions are read from locker.model.RULES, so the picture always
matches the executable model. Only the box positions and the display text of the
guards are defined here.

Usage:  python -m experiments.make_diagram [--out report/figure1_state_diagram.png]
"""
import argparse
import math
import os
from collections import OrderedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from locker.model import RULES, LockerModel
from locker.transitions import TRANSITIONS

# box centres (x, y); extra states added in the future are placed on spare slots
POSITIONS = {"AVAILABLE": (2.4, 3.2), "RESERVED": (6.4, 5.7),
             "OCCUPIED": (10.2, 3.2), "MAINTENANCE": (2.4, 0.4)}
SPARE_SLOTS = [(6.4, 0.4), (10.2, 0.4), (6.4, 1.8), (10.2, 5.7)]
COLOURS = {"AVAILABLE": "#d9f0d3", "RESERVED": "#fff3c4",
           "OCCUPIED": "#cfe2f3", "MAINTENANCE": "#e6e6e6"}
# display text for each guard function (looked up by the function's name)
GUARD_TEXT = {"_always": "", "_reservation_code_ok": " [code = R-cid]",
              "_retrieval_code_ok": " [code = P-cid]", "_expired_flag_true": " [expired = True]"}
HALF_W, HALF_H = 1.15, 0.45


def _exit_distance(rel, u):
    """Distance along unit vector u from point `rel` (relative to box centre) to the box edge."""
    ts = []
    for r, d, h in ((rel[0], u[0], HALF_W), (rel[1], u[1], HALF_H)):
        if abs(d) > 1e-9:
            ts.append(((h if d > 0 else -h) - r) / d)
    return min(t for t in ts if t >= 0)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="report/figure1_state_diagram.png")
    args = ap.parse_args(argv)

    # group accepted rules by (source, target); merge labels of parallel edges
    edges = OrderedDict()
    for r in RULES:
        label = r.operation.value + GUARD_TEXT.get(r.guard.__name__, " [guard]")
        edges.setdefault((r.source.value, r.target.value), []).append(label)

    names = list(dict.fromkeys([n for e in edges for n in e] + list(POSITIONS)))
    pos, spare = dict(POSITIONS), list(SPARE_SLOTS)
    for n in names:
        if n not in pos:
            pos[n] = spare.pop(0)

    fig, ax = plt.subplots(figsize=(11, 6.6))
    ax.set_xlim(0, 12); ax.set_ylim(-0.7, 7); ax.axis("off")
    for n in names:
        x, y = pos[n]
        ax.add_patch(FancyBboxPatch((x - HALF_W, y - HALF_H), 2 * HALF_W, 2 * HALF_H,
                     boxstyle="round,pad=0.03,rounding_size=0.25",
                     fc=COLOURS.get(n, "#f0f0f0"), ec="#333", lw=1.6, zorder=3))
        ax.text(x, y, n, ha="center", va="center", fontsize=12, fontweight="bold", zorder=4)

    for (a, b), labels in edges.items():
        (ax_, ay), (bx, by) = pos[a], pos[b]
        length = math.hypot(bx - ax_, by - ay)
        u = ((bx - ax_) / length, (by - ay) / length)
        n = (-u[1], u[0])
        both = (b, a) in edges
        off = (0.35 * n[0], 0.35 * n[1]) if both else (0.0, 0.0)
        ta = _exit_distance(off, u)                                   # leave box a
        tb = _exit_distance(off, (-u[0], -u[1]))                      # enter box b
        p1 = (ax_ + off[0] + u[0] * ta, ay + off[1] + u[1] * ta)
        p2 = (bx + off[0] - u[0] * tb, by + off[1] - u[1] * tb)
        ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=20, lw=1.6,
                                     color="#222", shrinkA=0, shrinkB=0, zorder=6))
        shift = 0.95 if both else 0.0
        frac = 0.3 if (both and u[1] < 0) else 0.5        # keeps labels of opposite arrows apart
        mid = (p1[0] + (p2[0] - p1[0]) * frac + n[0] * shift,
               p1[1] + (p2[1] - p1[1]) * frac + n[1] * shift)
        ax.text(*mid, "\n".join(labels), ha="center", va="center", fontsize=10, zorder=7,
                bbox=dict(fc="white", ec="#bbb", boxstyle="round,pad=0.25"))

    x0, y0 = pos[LockerModel().state.value]                           # initial-state marker
    ax.add_patch(plt.Circle((x0 - 1.95, y0), 0.13, color="#222", zorder=3))
    ax.add_patch(FancyArrowPatch((x0 - 1.8, y0), (x0 - HALF_W, y0), arrowstyle="-|>",
                                 mutation_scale=18, lw=1.6, color="#222", zorder=6))

    rejected = len(TRANSITIONS) - len(RULES)
    ax.text(6, -0.5, "All other operation/state combinations, wrong codes and expired = False are "
            f"rejected: state and data stay unchanged (self-loops, {rejected} of {len(TRANSITIONS)} transitions).",
            ha="center", va="center", fontsize=9.5, style="italic")
    ax.set_title("Smart Parcel Locker: state-transition diagram (accepted transitions)", fontsize=13, pad=8)
    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=170)
    print("Wrote", args.out)


if __name__ == "__main__":
    main()