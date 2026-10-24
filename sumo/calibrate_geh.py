"""Calibrate the corridor demand against 'field' counts and report GEH.

Usage:  python calibrate_geh.py

1. A hidden 'field' run stands in for the real world: side streets carry 40 %
   more traffic than the model assumes, eastbound 15 % less, westbound 10 % more, and a different seed.
2. The model runs with its assumed demand. Loop counts are compared with GEH.
3. Simple calibration: every flow from an entry is scaled by the ratio of field
   to model counts at that entry's loop. The model is rerun and checked again.
"""
import json
import math
import os
import re
import xml.etree.ElementTree as ET

import sumolib
import traci

import make_routes as mr

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRIES = ["W_J1", "E_J3", "N1_J1", "S1_J1", "N2_J2", "S2_J2", "N3_J3", "S3_J3"]
PEAK = (300, 1500)


def scaled_routes(path, factors):
    """Write medium-demand routes with a scale factor per entry edge."""
    src = open(os.path.join(HERE, "routes_medium.rou.xml")).read()
    def fix(m):
        line, entry, rate = m.group(0), m.group(1), int(m.group(2))
        return line.replace(f'vehsPerHour="{rate}"', f'vehsPerHour="{round(rate * factors.get(entry, 1.0))}"')
    out = re.sub(r'<flow [^>]*from="([^"]+)"[^>]*vehsPerHour="(\d+)"[^>]*/>', fix, src)
    open(os.path.join(HERE, path), "w").write(out)


def counts(routes, seed):
    """Run fixed-time control and return hourly flow at every loop during the peak."""
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    cwd = os.getcwd()
    os.chdir(HERE)
    traci.start([sumolib.checkBinary("sumo"), "-n", "corridor_fixed.net.xml", "-r", routes,
                 "-a", "detectors.add.xml", "--seed", str(seed), "--end", "1800",
                 "--no-step-log", "true", "--no-warnings", "true"])
    while traci.simulation.getTime() < 1800:
        traci.simulationStep()
    traci.close()
    root = ET.parse("out/e1_counts.xml").getroot()
    os.chdir(cwd)
    total = {}
    for iv in root.findall("interval"):
        if PEAK[0] <= float(iv.get("begin")) < PEAK[1]:
            det = iv.get("id").replace("e1_", "")
            total[det] = total.get(det, 0) + int(float(iv.get("nVehContrib")))
    hours = (PEAK[1] - PEAK[0]) / 3600
    by_edge = {}
    for lane, n in total.items():
        edge = lane.rsplit("_", 1)[0]
        by_edge[edge] = by_edge.get(edge, 0) + n / hours
    return by_edge


def geh(m, c):
    return math.sqrt(2 * (m - c) ** 2 / (m + c)) if m + c > 0 else 0.0


def table(model, field):
    rows = []
    for e in sorted(field):
        rows.append({"loop": e, "model": round(model.get(e, 0)), "field": round(field[e]),
                     "geh": round(geh(model.get(e, 0), field[e]), 2)})
    passed = sum(r["geh"] < 5 for r in rows)
    return rows, round(100 * passed / len(rows))


if __name__ == "__main__":
    truth = {e: 1.40 for e in ENTRIES if e[0] in "NS"}
    truth.update({"W_J1": 0.85, "E_J3": 1.10})
    scaled_routes("routes_field.rou.xml", truth)
    field = counts("routes_field.rou.xml", seed=7)

    model = counts("routes_medium.rou.xml", seed=42)
    before, pass_before = table(model, field)

    factors = {e: field[e] / model[e] for e in ENTRIES if model.get(e)}
    scaled_routes("routes_calibrated.rou.xml", factors)
    model2 = counts("routes_calibrated.rou.xml", seed=42)
    after, pass_after = table(model2, field)

    print(f"{'loop':8s} {'model':>6s} {'field':>6s} {'GEH':>5s}   after: {'model':>6s} {'GEH':>5s}")
    for b, a in zip(before, after):
        print(f"{b['loop']:8s} {b['model']:6d} {b['field']:6d} {b['geh']:5.2f}          {a['model']:6d} {a['geh']:5.2f}")
    print(f"GEH < 5 on {pass_before}% of loops before, {pass_after}% after calibration")
    json.dump({"before": before, "after": after, "pass_before": pass_before, "pass_after": pass_after,
               "factors": {k: round(v, 3) for k, v in factors.items()}},
              open(os.path.join(HERE, "out", "calibration.json"), "w"), indent=1)
