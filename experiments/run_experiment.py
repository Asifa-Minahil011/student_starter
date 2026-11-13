"""Experiment runner (Task 5).

Default protocol (assignment minimum): 3 strategies x 5 seeds x 500 sequences,
max length 20, all mutants. Everything is written to results/ as CSV/JSON.

Usage (from the project root):
    python -m experiments.run_experiment                       # full experiment
    python -m experiments.run_experiment --strategy pair       # one strategy only
    python -m experiments.run_experiment --strategy random --seeds 1 2 --count 100
"""
import argparse
import csv
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime

from locker.generators import CoverageGuidedGenerator, RandomWalkGenerator, TransitionPairGenerator
from locker.metrics import CoverageTracker, calculate_coverage, mutation_summary, redundancy
from locker.mutants import MUTANTS
from locker.mutation import evaluate_all
from locker.runner import SequenceRunner
from locker.transitions import PAIRS, TRANSITIONS

STRATEGIES = {"random": RandomWalkGenerator,
              "coverage": CoverageGuidedGenerator,
              "pair": TransitionPairGenerator}
CHECKPOINTS = (1, 2, 5, 10, 25, 50, 100, 250, 500)


def snap_str(s):
    return "" if s is None else f"{s.state.value}|{s.customer_id}|{s.reservation_code}|{s.retrieval_code}"


def run_one(key, seed, count, max_length):
    """Generate, execute on the reference SUT, measure coverage, then run all mutants."""
    gen = STRATEGIES[key](seed, max_length)

    t = time.perf_counter()
    sequences = gen.generate(count)
    gen_time = time.perf_counter() - t

    runner = SequenceRunner()
    t = time.perf_counter()
    records = [runner.run(seq, f"{gen.name}-s{seed}-{i:04d}", gen.name)
               for i, seq in enumerate(sequences)]
    exec_time = time.perf_counter() - t

    cov = calculate_coverage([r.trace for r in records])
    red = redundancy(sequences)

    growth, tracker = [], CoverageTracker()
    for i, r in enumerate(records, 1):
        tracker.add_trace(r.trace)
        if i in CHECKPOINTS or i == len(records):
            s = tracker.summary()
            growth.append({"strategy": gen.name, "seed": seed, "sequences": i,
                           "transition_coverage": s["transition_coverage"],
                           "pair_coverage": s["pair_coverage"]})

    t = time.perf_counter()
    mutant_rows = evaluate_all(sequences, gen.name)
    mutation_time = time.perf_counter() - t
    for m in mutant_rows:
        m["seed"] = seed
    ms = mutation_summary([{"name": m["mutant_id"], "killed": m["killed"],
                            "equivalent": m["equivalent"]} for m in mutant_rows])

    row = {"strategy": gen.name, "seed": seed, "sequences": len(sequences),
           "max_length": max_length,
           "avg_length": round(sum(map(len, sequences)) / len(sequences), 2),
           **cov,
           "duplicate_sequences": red["duplicates"], "unique_sequences": red["unique"],
           "reference_failures": sum(r.outcome == "FAIL" for r in records),
           "mutants_total": ms["total"], "mutants_considered": ms["non_equivalent_considered"],
           "mutants_killed": len(ms["detected"]), "mutants_survived": len(ms["survived"]),
           "survivors": ";".join(ms["survived"]), "equivalent_mutants": ";".join(ms["equivalent"]),
           "mutation_score": ms["mutation_score"],
           "generation_time_s": round(gen_time, 4), "execution_time_s": round(exec_time, 4),
           "mutation_time_s": round(mutation_time, 4)}
    return row, records, mutant_rows, growth


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def aggregate(runs):
    """Per-strategy mean / stdev over seeds, plus the mutant x strategy kill matrix."""
    out = {"strategies": {}, "kill_matrix": {}}
    metrics = ["state_coverage", "transition_coverage", "pair_coverage", "mutation_score",
               "generation_time_s", "execution_time_s", "mutation_time_s",
               "duplicate_sequences", "avg_length"]
    for name in sorted({r["strategy"] for r in runs}):
        rs = [r for r in runs if r["strategy"] == name]
        entry = {"seeds": [r["seed"] for r in rs]}
        for m in metrics:
            vals = [r[m] for r in rs]
            entry[m] = {"mean": round(statistics.mean(vals), 3),
                        "stdev": round(statistics.pstdev(vals), 3),
                        "min": min(vals), "max": max(vals)}
        out["strategies"][name] = entry
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", choices=list(STRATEGIES) + ["all"], default="all")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--count", type=int, default=500, help="sequences per strategy and seed")
    ap.add_argument("--max-length", type=int, default=20)
    ap.add_argument("--out", default="results")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    keys = list(STRATEGIES) if args.strategy == "all" else [args.strategy]
    runs, raw_tests, mutation_rows, growth_rows = [], [], [], []

    for key in keys:
        for seed in args.seeds:
            row, records, mrows, growth = run_one(key, seed, args.count, args.max_length)
            runs.append(row); mutation_rows += mrows; growth_rows += growth
            for r in records:
                d = r.to_dict()
                d["seed"] = seed
                d["expected_final"] = snap_str(r.expected_final)
                d["actual_final"] = snap_str(r.actual_final)
                raw_tests.append(d)
            print(f"{row['strategy']:16s} seed={seed}  state={row['state_coverage']:6.2f}%  "
                  f"trans={row['transition_coverage']:6.2f}%  pairs={row['pair_coverage']:6.2f}%  "
                  f"mutation={row['mutation_score']:6.2f}%  gen={row['generation_time_s']:.2f}s  "
                  f"exec={row['execution_time_s']:.2f}s  dups={row['duplicate_sequences']}")

    summary = aggregate(runs)
    # kill matrix: mutant -> strategy -> number of seeds that detected it
    for m in MUTANTS:
        summary["kill_matrix"][m.mutant_id] = {
            "name": m.name, "equivalent": m.equivalent, "category": m.category,
            **{key: sum(1 for r in mutation_rows
                        if r["mutant_id"] == m.mutant_id and r["strategy"] == STRATEGIES[key].name
                        and r["killed"]) for key in keys}}
    summary["config"] = {"strategies": keys, "seeds": args.seeds, "sequences_per_run": args.count,
                         "max_length": args.max_length, "model_states": 4,
                         "model_transitions": len(TRANSITIONS), "model_transition_pairs": len(PAIRS),
                         "mutants_total": len(MUTANTS),
                         "mutants_equivalent": sum(m.equivalent for m in MUTANTS),
                         "python": sys.version.split()[0], "platform": platform.platform(),
                         "run_at": datetime.now().isoformat(timespec="seconds")}

    write_csv(os.path.join(args.out, "raw_tests.csv"), raw_tests)
    write_csv(os.path.join(args.out, "runs_summary.csv"), runs)
    write_csv(os.path.join(args.out, "mutation_results.csv"), mutation_rows)
    write_csv(os.path.join(args.out, "coverage_growth.csv"), growth_rows)
    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote results to {args.out}/  (raw_tests.csv, runs_summary.csv, "
          f"mutation_results.csv, coverage_growth.csv, summary.json)")


if __name__ == "__main__":
    main()