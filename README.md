# Smart Parcel Locker: Model-Based Testing Framework

An executable state-machine model of a parcel-locker compartment, three
test-generation strategies, an automated runner with a test oracle, 14 injected
faults (mutants) and a reproducible experiment comparing the strategies.

## 1. Requirements
* Python **3.10 or newer** (developed on 3.12, Ubuntu 24.04 / WSL)
* `matplotlib` (only for the charts and the diagram); everything else is the standard library

## 2. Setup (Ubuntu / WSL)
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip unzip
unzip student_submission.zip       # use your ZIP's file name
cd student_starter                 # the project root (contains locker/ and tests/)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt    # installs matplotlib
```
Always run commands from the project root. On Windows use `python -m venv venv`
and `venv\Scripts\activate`.

## 3. Verify the installation
```bash
python -m unittest discover -s tests          # expect: Ran 60 tests ... OK  (about 10 s)
```

## 4. Project layout
| Path | Purpose |
|---|---|
| `locker/types.py`, `locker/sut.py` | provided types and reference System Under Test (not modified) |
| `locker/model.py` | independent table-driven executable model (derived from `data/requirements.md`) |
| `locker/transitions.py` | catalogue of the 35 transitions and 305 transition pairs, generated from the model |
| `locker/generators.py` | Strategy A random walk, B coverage-directed, C transition-pair |
| `locker/runner.py` | executes a sequence on SUT and model in lockstep, records every `TestRecord` |
| `locker/oracle.py` | model-independent invariant checks on the SUT |
| `locker/metrics.py` | state / transition / transition-pair coverage, mutation score, redundancy |
| `locker/mutants.py` | 14 mutants (12 real, 2 equivalent) with witness sequences |
| `locker/mutation.py` | runs sequences against mutants |
| `experiments/run_experiment.py` | full experiment, writes `results/` |
| `experiments/make_charts.py` | charts from `results/` |
| `experiments/make_diagram.py` | draws the state-transition diagram (report Figure 1) from the model |
| `experiments/demo.py` | short demonstration |
| `tests/` | smoke tests (provided) and unit tests for every module |
| `report/behaviour_table.md` | behaviour table, assumptions, invariants |
| `report/report.pdf` | technical report |
| `results/` | raw results and charts (generated) |

## 5. Running each test-generation strategy
Each strategy can be run on its own through the experiment runner. It generates the
sequences, executes them on the reference SUT, measures coverage and runs all mutants.

```bash
python -m experiments.run_experiment --strategy random   --seeds 1 --out results_random
python -m experiments.run_experiment --strategy coverage --seeds 1 --out results_coverage
python -m experiments.run_experiment --strategy pair     --seeds 1 --out results_pair
```
Options: `--seeds 1 2 3`, `--count 500` (sequences per run), `--max-length 20`, `--out DIR`.

From Python:
```python
from locker.generators import RandomWalkGenerator, CoverageGuidedGenerator, TransitionPairGenerator
sequences = RandomWalkGenerator(seed=1, max_length=20).generate(500)   # list of list[Command]
```

## 6. Running the mutation experiments and reproducing the reported results
```bash
python -m experiments.run_experiment      # 3 strategies x seeds 1-5 x 500 sequences, 14 mutants
python -m experiments.make_charts         # PNG charts in results/ (report Figures 2-6)
python -m experiments.make_diagram        # state diagram in report/ (report Figure 1)
python -m experiments.demo                # short demonstration (--pause for a live demo)
```
Protocol: 3 strategies, 500 sequences each, maximum length 20, seeds 1-5, 14 mutants.
All randomness comes from `random.Random(seed)`, so coverage and mutation results
are reproducible exactly; only the timing columns vary between machines.

Outputs in `results/`: `raw_tests.csv` (every executed test), `runs_summary.csv`
(per strategy and seed), `mutation_results.csv` (per mutant, strategy and seed),
`coverage_growth.csv`, `summary.json` (means, standard deviations, kill matrix,
configuration) and `chart_*.png`.

## 7. Key design decisions
* **Independent oracle.** `model.py` is built from the requirements only; it never imports
  or inspects the SUT. `oracle.py` adds invariant checks evaluated on the SUT's own
  snapshots, so a mistake shared by model and SUT can still be detected.
* **Compared after every step:** the `accepted` flag and the complete snapshot. Message
  strings are not compared because the requirements do not define them.
* **Transition** = `(source state, operation, outcome)` with outcome one of `accepted`,
  `rejected_precondition`, `rejected_guard`; rejected transitions are self-loops. This gives
  35 transitions (7 accepted, 3 guard-rejected, 25 precondition-rejected).
* **Transition pair** = two transitions `t1, t2` with `target(t1) == source(t2)`, counted only
  between consecutive steps of the same sequence (305 pairs).
* **Mutation score** = killed / (total - equivalent) x 100. Equivalent mutants (M13, M14) are
  listed separately with the reason.
* Assumptions and invariants are documented in `report/behaviour_table.md`.

## 8. Use of AI tools
AI assistance (Claude) was used for [list what: e.g. drafting the model, generators,
runner, mutants, experiment and diagram scripts, README and a first draft of the report].
I reviewed the code and text, ran the full test suite and the experiments on my own
machine, and can explain and modify every module. [Edit this paragraph so it describes
exactly what you did and what you changed yourself.]