"""Repeat every controller and demand level with several random seeds.

Usage:  python multi_seed.py        (runs in parallel; about 15 minutes on 4 cores)

One seed can flatter or punish a controller by chance. This script reports the
mean and the range over seeds 1-5 and writes ../data/robustness.json.
"""
import json
import os
import statistics
from concurrent.futures import ProcessPoolExecutor

from run_scenario import run

SEEDS = [1, 2, 3, 4, 5]
CONTROLLERS = ["fixed", "actuated", "twin", "twin_camera"]
DEMANDS = ["low", "medium", "high"]


def one(args):
    c, d, s = args
    r = run(c, d, seed=s)
    return c, d, s, r["mean_time_loss_s"], r["mean_stops"]


if __name__ == "__main__":
    jobs = [(c, d, s) for d in DEMANDS for c in CONTROLLERS for s in SEEDS]
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        rows = list(ex.map(one, jobs))
    out = []
    for d in DEMANDS:
        for c in CONTROLLERS:
            tl = [r[3] for r in rows if r[0] == c and r[1] == d]
            st = [r[4] for r in rows if r[0] == c and r[1] == d]
            out.append({"controller": c, "demand": d, "seeds": SEEDS,
                        "time_loss_mean": round(statistics.mean(tl), 1), "time_loss_min": min(tl), "time_loss_max": max(tl),
                        "stops_mean": round(statistics.mean(st), 2)})
            print(c, d, out[-1]["time_loss_mean"], (min(tl), max(tl)), out[-1]["stops_mean"], flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "robustness.json"), "w"), indent=1)
