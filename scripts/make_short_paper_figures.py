#!/usr/bin/env python3
"""Figure 1: adoption and rejection flips per model with 95% CIs.

Reads analysis/hypotheses_v31.json (v3.1 judge, 500 scenarios x 4 models) and writes
paper/figures/flips_by_model.pdf. No numbers are typed in by hand.

Usage: .venv/bin/python scripts/make_short_paper_figures.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "analysis/hypotheses_v31.json"
OUT = REPO / "paper/figures/flips_by_model.pdf"

DISPLAY = {
    "claude-sonnet-4-6": "Sonnet",
    "gemini-3.5-flash": "Gemini",
    "llama3.1:8b": "Llama",
    "google/gemma-4-31B-it": "Gemma",
    "POOLED": "Pooled",
}
BLUE = "#0F4D92"
RED = "#B64342"


def main():
    models = json.load(open(SRC))["v3.1"]["models"]
    order = [k for k in DISPLAY if k in models]
    adopt = np.array([models[k]["ISB"]["pct"] for k in order])
    reject = np.array([models[k]["vigilance"]["pct"] for k in order])
    adopt_ci = np.array([models[k]["ISB"]["ci"] for k in order])
    reject_ci = np.array([models[k]["vigilance"]["ci"] for k in order])

    plt.rcParams.update({
        "font.family": ["DejaVu Sans", "sans-serif"],
        "font.size": 8, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "pdf.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=(3.25, 2.1))
    x = np.arange(len(order))
    w = 0.38
    ax.bar(x - w / 2, adopt, w, color=BLUE, label="adoption flip",
           yerr=[adopt - adopt_ci[:, 0], adopt_ci[:, 1] - adopt],
           error_kw=dict(lw=0.8, capsize=2, ecolor="black"))
    ax.bar(x + w / 2, reject, w, color=RED, label="rejection flip",
           yerr=[reject - reject_ci[:, 0], reject_ci[:, 1] - reject],
           error_kw=dict(lw=0.8, capsize=2, ecolor="black"))
    ax.axvline(len(order) - 1.5, color="0.7", lw=0.6, ls=":")
    ax.set_xticks(x)
    ax.set_xticklabels([DISPLAY[k] for k in order])
    ax.set_ylabel("% of scenario pairs")
    ax.set_ylim(0, 18)
    ax.legend(loc="upper left", handlelength=1.0, ncol=2, columnspacing=1.0)
    fig.tight_layout(pad=0.3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # no creation date in the PDF, so re-running gives a byte-identical file
    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.02, metadata={"CreationDate": None})
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
