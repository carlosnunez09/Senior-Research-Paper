"""Export plotting CSVs for the paper from the final benchmark runs.

Run from anywhere:  python paper/make_plot_data.py
Writes paper/data/final_<backend>.csv (ladder, mean/min/max over runs),
paper/data/finalhold_<backend>_<target>.csv and paper/data/finalhold_per_run.csv (holds).
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "southfire server"
OUT = Path(__file__).resolve().parent / "data"
FINAL = ROOT.parent / "final runs" / "group run complete 2026-10-16_16-47"
METRICS = [("ping", "ping_mean_ms"), ("recv", "receive_per_client_sec"),
           ("resp", "responding_rate_pct"), ("tick", "server_tick_hz"),
           ("scpu", "server_cpu_mean_pct")]


def f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def write(path, header, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    print(path.name, len(rows), "rows")


def mean(values):
    return sum(values) / len(values)


def final_ladder():
    """Sum up the complete final ladder runs: mean, min and max per client count."""
    folders = sorted(FINAL.glob("group run [0-9][0-9] complete"))
    table = []
    for backend in ("cpp", "enet"):
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
        write(OUT / f"final_{backend}.csv", header, rows)
        for clients in (100, 150, 200, 250, 300):
            r = next(x for x in rows if x[0] == clients)
            table.append((backend, r))
    # LaTeX rows for the example table
    names = {"cpp": "C++ UDP", "enet": "Godot ENet"}
    lines = []
    last = None
    for backend, r in table:
        if last and backend != last:
            lines.append(chr(92) + "midrule")
        last = backend
        c, n, ok = r[0], r[1], r[2]
        resp, ping, recv, tick = r[9], r[3:6], r[6:9], r[12]
        lines.append(
            f"{names[backend]} & {c} & {resp:.1f} & {ping[0]:.0f} ({ping[1]:.0f}--{ping[2]:.0f}) & "
            f"{recv[0]:.1f} ({recv[1]:.1f}--{recv[2]:.1f}) & {tick:.1f} & {ok} of {n} \\\\"
        )
    (OUT / "final_table_rows.tex").write_text(chr(10).join(lines) + chr(10))
    (OUT / "final_n_runs.txt").write_text(str(len(folders)))
    print(len(folders), "final runs summed")



HOLD_FINAL = ROOT.parent / "final runs" / "hold"
HOLD_MAIN = HOLD_FINAL / "main hold batch" / "group run incomplete 2026-10-17_20-30"
HOLD_MAKEUP = HOLD_FINAL / "make-up ENet 270-300" / "group run complete 2026-10-18_21-46"
HOLD_TARGETS = (180, 260, 270, 300)


def complete_captures(folder):
    """Hold captures whose outcome is 'complete' inside one group-run folder."""
    import json
    found = {}
    for outcome in folder.glob("bench/*/hold_outcomes.json"):
        for x in json.load(open(outcome)):
            if x["status"] == "complete":
                found[(x["backend"], int(x["target_clients"]))] = (
                    outcome.parent / x["backend"] / f"target_{x['target_clients']}" / "rep_1")
    return found


def select_hold_runs():
    """Eight runs per backend and target: the main batch, with the ENet captures that runs 3 and 4
    were missing taken from the make-up batch (make-up run 1 for run 3, make-up run 2 for run 4)."""
    chosen = {}
    for number in range(1, 9):
        matches = sorted(HOLD_MAIN.glob(f"group run {number:02d} *"))
        folder = [m for m in matches if m.name.endswith("complete") or m.name.endswith("incomplete")][-1]
        for key, path in complete_captures(folder).items():
            chosen[(number,) + key] = path
    for number, name in ((3, "group run 01 complete"), (4, "group run 02 complete")):
        for key, path in complete_captures(HOLD_MAKEUP / name).items():
            chosen.setdefault((number,) + key, path)
    return chosen


def capture_timeline(path, backend, target):
    """One capture as 10 s states: ramp-up, settle and hold."""
    snap_key = "tick_rx_delta" if backend == "enet" else "complete_snapshots_delta"
    states = {}
    for r in csv.DictReader(open(path / "client_capture.csv")):
        states.setdefault(int(r["state_index"]), []).append(r)
    server = {}
    for r in csv.DictReader(open(path / "server_samples.csv")):
        server.setdefault(int(r["state_index"]), []).append(r)
    t0 = min(float(rows[0]["state_started_epoch_ms"]) for rows in states.values())
    hold_start = min(float(rows[0]["state_started_epoch_ms"]) for rows in states.values()
                     if rows[0]["phase"] == "hold")
    out = []
    for index in sorted(states):
        rows = states[index]
        n = len(rows)
        started = float(rows[0]["state_started_epoch_ms"])
        seconds = (float(rows[0]["state_ended_epoch_ms"]) - started) / 1000.0
        clients = int(rows[0]["global_clients_target"])
        responding = sum(int(float(r["responding"] or 0)) for r in rows)
        snaps = sum(float(r[snap_key] or 0) for r in rows)
        if backend == "enet":
            ping = sum(float(r["ping_ms"] or 0) for r in rows) / n
        else:
            weights = [float(r["rtt_samples"] or 0) for r in rows]
            total = sum(weights)
            ping = sum(float(r["rtt_mean_ms"] or 0) * w for r, w in zip(rows, weights)) / total if total else None
        samples = server.get(index, [])
        tick_hz = None
        if len(samples) >= 2:
            dt = (float(samples[-1]["epoch_ms"]) - float(samples[0]["epoch_ms"])) / 1000.0
            dtick = float(samples[-1]["tick"]) - float(samples[0]["tick"])
            tick_hz = dtick / dt if dt > 0 else None
        out.append({"minute_rel": (started - hold_start) / 60000.0, "phase": rows[0]["phase"],
                    "clients": clients, "responding_pct": 100.0 * responding / clients if clients else None,
                    "recv": snaps / n / seconds if seconds > 0 else None, "ping": ping, "tick": tick_hz})
    return out


def final_hold():
    chosen = select_hold_runs()
    per_run = []
    for backend in ("cpp", "enet"):
        for target in HOLD_TARGETS:
            timelines = [capture_timeline(chosen[(n, backend, target)], backend, target) for n in range(1, 9)]
            # align states by (phase, position inside the phase)
            slots = {}
            for tl in timelines:
                seen = {}
                for row in tl:
                    k = (row["phase"], seen.get(row["phase"], 0))
                    seen[row["phase"]] = k[1] + 1
                    slots.setdefault(k, []).append(row)
            order = sorted(slots, key=lambda k: mean([r["minute_rel"] for r in slots[k]]))
            header = ["minute_rel", "phase", "clients", "n_runs"]
            for short in ("responding_pct", "recv", "ping", "tick"):
                header += [short + "_mean", short + "_min", short + "_max"]
            rows = []
            for k in order:
                group = slots[k]
                row = [mean([r["minute_rel"] for r in group]), k[0], mean([r["clients"] for r in group]), len(group)]
                for short in ("responding_pct", "recv", "ping", "tick"):
                    values = [r[short] for r in group if r[short] is not None]
                    row += [mean(values), min(values), max(values)] if values else ["", "", ""]
                rows.append(row)
            write(OUT / f"finalhold_{backend}_{target}.csv", header, rows)
            for number, tl in enumerate(timelines, start=1):
                hold = [r for r in tl if r["phase"] == "hold"]
                def avg(key):
                    vals = [r[key] for r in hold if r[key] is not None]
                    return mean(vals) if vals else None
                per_run.append({"backend": backend, "target": target, "run": number,
                                "resp": avg("responding_pct"), "recv": avg("recv"),
                                "ping": avg("ping"), "tick": avg("tick")})
    write(OUT / "finalhold_per_run.csv", ["backend", "target", "run", "resp", "recv", "ping", "tick"],
          [[r["backend"], r["target"], r["run"], r["resp"], r["recv"], r["ping"], r["tick"]] for r in per_run])
    return per_run


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    final_ladder()
    final_hold()
