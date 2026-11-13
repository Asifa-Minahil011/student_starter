"""Short demonstration for the assignment (about 2-3 minutes).

Shows: (1) the executable model, (2) sequence generation by all three strategies,
(3) execution against the reference SUT, (4) detection of an injected fault,
(5) the experimental results.

Usage:  python -m experiments.demo            # runs straight through
        python -m experiments.demo --pause    # waits for Enter between sections (live demo)
"""
import argparse
import json
import os

from locker.generators import CoverageGuidedGenerator, RandomWalkGenerator, TransitionPairGenerator
from locker.metrics import calculate_coverage
from locker.model import LockerModel
from locker.mutants import MUTANTS
from locker.runner import SequenceRunner, format_command, format_sequence
from locker.transitions import PAIRS, TRANSITIONS
from locker.types import Command, Operation


def section(title, pause):
    print("\n" + "=" * 72 + f"\n{title}\n" + "=" * 72)
    if pause:
        input("(press Enter) ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pause", action="store_true")
    ap.add_argument("--results", default="results")
    a = ap.parse_args()

    # 1 ------------------------------------------------------------------
    section("1. Executable state-machine model", a.pause)
    model = LockerModel()
    print("Initial snapshot:", model.snapshot())
    script = [Command(Operation.RESERVE, customer_id="C7"),
              Command(Operation.DEPOSIT, code="WRONG"),
              Command(Operation.DEPOSIT, code="R-C7"),
              Command(Operation.RETRIEVE, code="P-C7"),
              Command(Operation.RETRIEVE, code="P-C7")]
    for cmd in script:
        res = model.step(cmd)
        print(f"{format_command(cmd):62s} -> accepted={res.accepted!s:5s} state={model.state.value}")
    print(f"\nModel: 4 states, {len(TRANSITIONS)} transitions, {len(PAIRS)} transition pairs.")

    # 2 ------------------------------------------------------------------
    section("2. Test generation: one short sample from each strategy", a.pause)
    for G in (RandomWalkGenerator, CoverageGuidedGenerator, TransitionPairGenerator):
        seq = max(G(seed=1, max_length=8).generate(5), key=len)   # longest of 5, for a readable sample
        print(f"[{G.name}]")
        for c in seq:
            print("   ", format_command(c))

    # 3 ------------------------------------------------------------------
    section("3. Execution against the reference SUT (500 sequences per strategy, seed 1)", a.pause)
    runner = SequenceRunner()
    generated = {}
    for G in (RandomWalkGenerator, CoverageGuidedGenerator, TransitionPairGenerator):
        seqs = G(seed=1, max_length=20).generate(500)
        generated[G.name] = seqs
        recs = [runner.run(s, f"{G.name}-{i}", G.name) for i, s in enumerate(seqs)]
        cov = calculate_coverage([r.trace for r in recs])
        fails = sum(r.outcome == "FAIL" for r in recs)
        print(f"{G.name:16s} failures={fails}  state={cov['state_coverage']}%  "
              f"transition={cov['transition_coverage']}%  pair={cov['pair_coverage']}%")

    # 4 ------------------------------------------------------------------
    section("4. Fault detection: mutant M03 (RETRIEVE accepted with any code)", a.pause)
    spec = next(m for m in MUTANTS if m.mutant_id == "M03")
    print("Defect:", spec.description)
    mutant_runner = SequenceRunner(sut_factory=spec.cls)
    for name, seqs in generated.items():
        for i, s in enumerate(seqs):
            rec = mutant_runner.run(s, f"{name}-{i}", name)
            if rec.outcome == "FAIL":
                print(f"\n[{name}] killed at test #{i + 1}")
                print("  sequence:", format_sequence(s[:rec.failure_step + 1]))
                print("  failure :", rec.failure_details)
                break

    # 5 ------------------------------------------------------------------
    section("5. Experimental results (from results/summary.json)", a.pause)
    path = os.path.join(a.results, "summary.json")
    if not os.path.exists(path):
        print("No results yet. Run:  python -m experiments.run_experiment")
        return
    s = json.load(open(path))
    print(f"{'strategy':16s} {'state%':>7s} {'trans%':>7s} {'pair%':>7s} {'mut.score%':>11s} {'gen s':>7s}")
    for name, e in s["strategies"].items():
        print(f"{name:16s} {e['state_coverage']['mean']:7.1f} {e['transition_coverage']['mean']:7.1f} "
              f"{e['pair_coverage']['mean']:7.1f} {e['mutation_score']['mean']:11.1f} "
              f"{e['generation_time_s']['mean']:7.2f}")
    print("\nMutants not detected by every strategy:")
    for mid, row in s["kill_matrix"].items():
        counts = {k: v for k, v in row.items() if k in ("random", "coverage", "pair")}
        if min(counts.values()) < len(s["config"]["seeds"]) and not row["equivalent"]:
            print(f"  {mid} {row['name']}: seeds detecting = {counts}")
    print("\nCharts are in", a.results + "/chart_*.png")


if __name__ == "__main__":
    main()