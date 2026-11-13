"""Create charts from results/*.csv and results/summary.json.

Usage:  python -m experiments.make_charts [--results results]
"""
import argparse
import csv
import json
import os
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ORDER = ["random_walk", "coverage_guided", "transition_pair"]
COLORS = {"random_walk": "#4C78A8", "coverage_guided": "#F58518", "transition_pair": "#54A24B"}


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def by_strategy(rows, key):
    d = defaultdict(list)
    for r in rows:
        d[r["strategy"]].append(float(r[key]))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    runs = read(os.path.join(a.results, "runs_summary.csv"))
    growth = read(os.path.join(a.results, "coverage_growth.csv"))
    summary = json.load(open(os.path.join(a.results, "summary.json")))
    strategies = [s for s in ORDER if s in {r["strategy"] for r in runs}]

    # 1. coverage (grouped bars, mean +/- stdev over seeds)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    metrics = [("state_coverage", "State"), ("transition_coverage", "Transition"),
               ("pair_coverage", "Transition-pair")]
    width = 0.8 / len(strategies)
    for i, s in enumerate(strategies):
        means = [statistics.mean(by_strategy(runs, m)[s]) for m, _ in metrics]
        sds = [statistics.pstdev(by_strategy(runs, m)[s]) for m, _ in metrics]
        ax.bar([x + i * width for x in range(len(metrics))], means, width, yerr=sds,
               label=s, color=COLORS[s], capsize=3)
    ax.set_xticks([x + width * (len(strategies) - 1) / 2 for x in range(len(metrics))])
    ax.set_xticklabels([n for _, n in metrics]); ax.set_ylabel("Coverage (%)")
    ax.set_ylim(0, 105); ax.set_title("Model coverage by strategy (mean +/- sd over seeds)")
    ax.legend(loc="lower right"); fig.tight_layout()
    fig.savefig(os.path.join(a.results, "chart_coverage.png"), dpi=150); plt.close(fig)

    # 2. mutation score
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ms = by_strategy(runs, "mutation_score")
    ax.bar(strategies, [statistics.mean(ms[s]) for s in strategies],
           yerr=[statistics.pstdev(ms[s]) for s in strategies],
           color=[COLORS[s] for s in strategies], capsize=4)
    ax.set_ylabel("Mutation score (%)"); ax.set_ylim(0, 105)
    ax.set_title("Mutation score (equivalent mutants excluded)")
    fig.tight_layout(); fig.savefig(os.path.join(a.results, "chart_mutation_score.png"), dpi=150); plt.close(fig)

    # 3. time
    fig, ax = plt.subplots(figsize=(7, 4.5))
    gen = by_strategy(runs, "generation_time_s"); exe = by_strategy(runs, "execution_time_s")
    mut = by_strategy(runs, "mutation_time_s")
    g = [statistics.mean(gen[s]) for s in strategies]; e = [statistics.mean(exe[s]) for s in strategies]
    m = [statistics.mean(mut[s]) for s in strategies]
    ax.bar(strategies, g, label="generation", color="#9ecae1")
    ax.bar(strategies, e, bottom=g, label="execution (reference SUT)", color="#fdae6b")
    ax.bar(strategies, m, bottom=[a_ + b_ for a_, b_ in zip(g, e)], label="mutation runs", color="#a1d99b")
    ax.set_ylabel("Seconds (mean per 500 sequences)"); ax.set_title("Time per strategy")
    ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(a.results, "chart_time.png"), dpi=150); plt.close(fig)

    # 4. kill matrix heatmap (seeds detecting each mutant)
    km = summary["kill_matrix"]
    ids = list(km.keys())
    keymap = {"random": "random_walk", "coverage": "coverage_guided", "pair": "transition_pair"}
    cols = [k for k in keymap if k in next(iter(km.values()))]
    n_seeds = len(summary["config"]["seeds"])
    data = [[km[i][c] for c in cols] for i in ids]
    fig, ax = plt.subplots(figsize=(6, 7))
    im = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=n_seeds, aspect="auto")
    ax.set_xticks(range(len(cols))); ax.set_xticklabels([keymap[c] for c in cols], rotation=20)
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels([f"{i}{' (equiv.)' if km[i]['equivalent'] else ''}" for i in ids])
    for y, row in enumerate(data):
        for x, v in enumerate(row):
            ax.text(x, y, f"{v}/{n_seeds}", ha="center", va="center", fontsize=9)
    ax.set_title("Mutant detection: seeds that killed each mutant")
    fig.colorbar(im, ax=ax, shrink=0.6); fig.tight_layout()
    fig.savefig(os.path.join(a.results, "chart_kill_matrix.png"), dpi=150); plt.close(fig)

    # 5. coverage growth
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, metric, title in ((axes[0], "transition_coverage", "Transition coverage"),
                              (axes[1], "pair_coverage", "Transition-pair coverage")):
        for s in strategies:
            pts = defaultdict(list)
            for r in growth:
                if r["strategy"] == s:
                    pts[int(r["sequences"])].append(float(r[metric]))
            xs = sorted(pts)
            ax.plot(xs, [statistics.mean(pts[x]) for x in xs], marker="o", label=s, color=COLORS[s])
        ax.set_xscale("log"); ax.set_xlabel("Number of sequences"); ax.set_ylabel("Coverage (%)")
        ax.set_title(title + " growth"); ax.grid(alpha=0.3)
    axes[0].legend(); fig.tight_layout()
    fig.savefig(os.path.join(a.results, "chart_coverage_growth.png"), dpi=150); plt.close(fig)
    print("Charts written to", a.results)


if __name__ == "__main__":
    main()