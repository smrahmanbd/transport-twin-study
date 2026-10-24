"""Run every controller at every demand level and write the data the SUMO Lab web page uses.

Usage:  python export_web.py        (about 10 minutes)

Writes into ../data/:
  network.json        lane shapes, junction shapes, signal stop lines, camera positions
  results.json        KPIs and per-minute queues for 4 controllers x 3 demand levels
  replay_<ctrl>.json  10 minutes of vehicle positions and signal states (medium demand)
  calibration.json    GEH before and after calibration
"""
import json
import os
import shutil

import sumolib

from run_scenario import run

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CONTROLLERS = ["fixed", "actuated", "twin", "twin_camera"]
DEMANDS = ["low", "medium", "high"]


def export_network():
    net = sumolib.net.readNet(os.path.join(HERE, "corridor_fixed.net.xml"), withInternal=True)
    lanes = []
    for e in net.getEdges(withInternal=True):
        for l in e.getLanes():
            lanes.append({"id": l.getID(), "w": round(l.getWidth(), 1), "internal": e.getFunction() == "internal",
                          "s": [[round(x, 1), round(y, 1)] for x, y in l.getShape()]})
    junctions = [{"id": n.getID(), "s": [[round(x, 1), round(y, 1)] for x, y in n.getShape()]}
                 for n in net.getNodes() if n.getShape()]
    stops = {}
    for tls in net.getTrafficLights():
        links = {}
        for inc, out, idx in tls.getConnections():
            x, y = inc.getShape()[-1]
            links[idx] = [round(x, 1), round(y, 1)]
        stops[tls.getID()] = [links[i] for i in sorted(links)]
    cams = []
    for j in ("J1", "J2", "J3"):
        x, y = net.getNode(j).getCoord()
        cams.append({"id": f"cam_{j}", "x": x + 12, "y": y + 12, "range": 110})
    xs = [p[0] for l in lanes for p in l["s"]]
    ys = [p[1] for l in lanes for p in l["s"]]
    json.dump({"lanes": lanes, "junctions": junctions, "stops": stops, "cameras": cams,
               "bounds": [min(xs), min(ys), max(xs), max(ys)]},
              open(os.path.join(DATA, "network.json"), "w"), separators=(",", ":"))


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    export_network()
    results = []
    for d in DEMANDS:
        for c in CONTROLLERS:
            rec = os.path.join(DATA, f"replay_{c}.json") if d == "medium" else None
            r = run(c, d, record=rec)
            print(c, d, {k: v for k, v in r.items() if k != "queue_per_minute"}, flush=True)
            results.append(r)
    json.dump(results, open(os.path.join(DATA, "results.json"), "w"), indent=1)
    cal = os.path.join(HERE, "out", "calibration.json")
    if os.path.exists(cal):
        shutil.copy(cal, os.path.join(DATA, "calibration.json"))
