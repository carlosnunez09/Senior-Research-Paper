"""Export plotting CSVs for the paper from the granular ladder runs (both patches applied).

Run from the repo root:  python paper/make_granular_data.py
Reads  final runs/granular enet-cpp-cppgodot/group run complete*/group run NN complete/bench/*/analysis/granular_<backend>_by_state.csv
Writes paper/data/granular_<backend>.csv (mean/min/max over runs per client count),
       paper/data/granular_summary.json (first failure per run, passing counts, table rows).
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "data"
ROOT = next((HERE.parent / "final runs" / "granular enet-cpp-cppgodot").glob("group run complete*"))
BACKENDS = ("cpp", "enet", "cppgodot")
METRICS = [("ping", "ping_mean_ms"), ("p95", "ping_p95_ms"), ("recv", "receive_per_client_sec"),
           ("resp", "responding_rate_pct"), ("tick", "server_tick_hz"), ("loss", "loss_events"),
           ("scpu", "server_cpu_mean_pct")]
TABLE_COUNTS = (100, 150, 200, 250, 300)


def mean(v):
    return sum(v) / len(v)


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def main():
    folders = sorted(ROOT.glob("group run [0-9][0-9] complete"))
    summary = {"n_runs": len(folders), "backends": {}}
    for backend in BACKENDS:
        runs = []
        for folder in folders:
            path = next(folder.glob(f"bench/*/analysis/granular_{backend}_by_state.csv"))
            runs.append({int(r["clients_target"]): r for r in csv.DictReader(open(path))})
        header = ["clients_target", "n_runs", "pass_runs"]
        for short, _ in METRICS:
            header += [short + "_mean", short + "_min", short + "_max"]
        rows = []
        for clients in sorted(runs[0]):
            states = [run[clients] for run in runs if clients in run]
            row = [clients, len(states), sum(1 for r in states if r["status"] == "PASS")]
            for _, column in METRICS:
                values = [float(r[column]) for r in states]
                row += [mean(values), min(values), max(values)]
            rows.append(row)
        with open(OUT / f"granular_{backend}.csv", "w", newline="") as handle:
            w = csv.writer(handle)
            w.writerow(header)
            w.writerows(rows)
        # first failing state from 10 clients upward, per run (1 client is a warm-up artefact)
        first_fail = []
        for run in runs:
            fails = [c for c in sorted(run) if c >= 10 and run[c]["status"] != "PASS"]
            first_fail.append(fails[0] if fails else None)
        table = {}
        for c in TABLE_COUNTS:
            states = [run[c] for run in runs]
            table[c] = {k: [mean([float(s[col]) for s in states]),
                            min(float(s[col]) for s in states),
                            max(float(s[col]) for s in states)] for k, col in METRICS}
            table[c]["passing"] = sum(1 for s in states if s["status"] == "PASS")
        summary["backends"][backend] = {
            "first_fail_per_run": first_fail,
            "states_passing_per_run": [sum(1 for c in run if run[c]["status"] == "PASS") for run in runs],
            "states_total": len(runs[0]),
            "table": table,
        }
        print(backend, len(rows), "rows; first failure per run:", first_fail)
    (OUT / "granular_summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
