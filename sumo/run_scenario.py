"""Run the corridor under one signal controller and one demand level.

Examples
    python run_scenario.py --controller fixed --demand medium
    python run_scenario.py --controller twin  --demand high --gui
    python run_scenario.py --controller twin  --demand medium --record web/twin_medium.json

Controllers
    fixed     netconvert's fixed-time plan (90 s cycle, equal split)
    actuated  SUMO's built-in gap-based actuated control (local detectors only)
    twin         twin_controller.TwinController fed by detectors and exact vehicle states
    twin_camera  the same twin fed only by the virtual cameras in camera_sensor.py

Results go to out/<controller>_<demand>_tripinfo.xml and are summarised on screen.
"""
import argparse
import json
import os
import statistics
import xml.etree.ElementTree as ET

import sumolib
import traci

from twin_controller import TwinController
from camera_sensor import corridor_cameras

HERE = os.path.dirname(os.path.abspath(__file__))


def run(controller, demand, gui=False, record=None, seed=42, window=(600, 1200), quiet=True):
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    net = "corridor_actuated.net.xml" if controller == "actuated" else "corridor_fixed.net.xml"
    tag = f"{controller}_{demand}" if seed == 42 else f"{controller}_{demand}_s{seed}"
    tripinfo = os.path.join("out", f"{tag}_tripinfo.xml")
    binary = sumolib.checkBinary("sumo-gui" if gui else "sumo")
    adds = "detectors.add.xml,cameras.add.xml" if gui else "detectors.add.xml"
    cmd = [binary, "-n", net, "-r", f"routes_{demand}.rou.xml", "-a", adds,
           "--tripinfo-output", tripinfo, "--seed", str(seed), "--end", "2400",
           "--time-to-teleport", "300", "--no-step-log", "true"]
    if quiet:
        cmd += ["--no-warnings", "true"]
    cwd = os.getcwd()
    os.chdir(HERE)
    traci.start(cmd)
    twin = None
    if controller == "twin":
        twin = TwinController(source="detectors")
    elif controller == "twin_camera":
        twin = TwinController(source="camera", cameras=corridor_cameras(sumolib.net.readNet(net)))
    queue_series, frames, signals, cam_frames = [], [], [], []
    cam_seen = cam_truth = 0
    cam_err = []
    approach_lanes = [l for l in traci.lane.getIDList() if not l.startswith(":") and l.split("_")[1] in ("J1", "J2", "J3")]
    halting_acc = 0
    while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < 2400:
        traci.simulationStep()
        t = traci.simulation.getTime()
        if twin:
            twin.step(t)
        halting_acc += sum(traci.lane.getLastStepHaltingNumber(l) for l in approach_lanes)
        if int(t) % 60 == 0:
            queue_series.append(round(halting_acc / 60, 1))   # mean vehicles stopped in that minute
            halting_acc = 0
        if controller == "twin_camera" and int(t) % 5 == 0:
            # how good is the camera at J2? compare with ground truth on its approach lanes
            cam = twin.cameras["J2"]
            truth = {v for l in cam.lanes for v in traci.lane.getLastStepVehicleIDs(l)
                     if traci.lane.getLength(l) - traci.vehicle.getLanePosition(v) < cam.range - 15}
            dets = twin.detections.get("J2", [])
            cam_truth += len(truth)
            cam_seen += len([d for d in dets if d["track"] in truth])
            for d in dets:
                if d["track"] in truth:
                    tx, ty = traci.vehicle.getPosition(d["track"])
                    cam_err.append(((tx - d["x"]) ** 2 + (ty - d["y"]) ** 2) ** 0.5)
        if record and window[0] <= t < window[1]:
            if controller == "twin_camera":
                cam_frames.append([[round(d["x"], 1), round(d["y"], 1),
                                    -1 if d["speed"] is None else round(d["speed"], 1)]
                                   for d in twin.detections.get("J2", [])])
            fr = []
            for v in traci.vehicle.getIDList():
                x, y = traci.vehicle.getPosition(v)
                fr += [round(x), round(y), round(traci.vehicle.getSpeed(v))]
            frames.append(fr)
            signals.append([traci.trafficlight.getRedYellowGreenState(j) for j in ("J1", "J2", "J3")])
    not_finished = traci.simulation.getMinExpectedNumber()
    traci.close()
    os.chdir(cwd)

    trips = ET.parse(os.path.join(HERE, tripinfo)).getroot().findall("tripinfo")
    dur = [float(t.get("duration")) for t in trips]
    wait = [float(t.get("waitingTime")) for t in trips]
    loss = [float(t.get("timeLoss")) for t in trips]
    stops = [int(t.get("waitingCount")) for t in trips]
    eb = [float(t.get("duration")) for t in trips if t.get("id").startswith("eb_")]
    res = {
        "controller": controller, "demand": demand,
        "trips": len(trips), "unfinished": not_finished,
        "mean_travel_time_s": round(statistics.mean(dur), 1),
        "mean_wait_s": round(statistics.mean(wait), 1),
        "mean_time_loss_s": round(statistics.mean(loss), 1),
        "mean_stops": round(statistics.mean(stops), 2),
        "eastbound_corridor_time_s": round(statistics.mean(eb), 1) if eb else None,
        "queue_per_minute": queue_series,
    }
    if twin:
        res["twin_decisions"] = len(twin.log)
    if controller == "twin_camera" and cam_truth:
        res["camera_detection_rate"] = round(cam_seen / cam_truth, 3)
        res["camera_position_error_m"] = round(statistics.mean(cam_err), 2)
    if record:
        os.makedirs(os.path.dirname(os.path.abspath(record)), exist_ok=True)
        json.dump({"window": list(window), "frames": frames, "signals": signals,
                   "camera": cam_frames, "decisions": twin.log if twin else []}, open(record, "w"), separators=(",", ":"))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--controller", choices=["fixed", "actuated", "twin", "twin_camera"], default="twin")
    ap.add_argument("--demand", choices=["low", "medium", "high"], default="medium")
    ap.add_argument("--gui", action="store_true", help="open sumo-gui to watch")
    ap.add_argument("--record", help="write replay data (JSON) for the web page")
    a = ap.parse_args()
    r = run(a.controller, a.demand, a.gui, a.record)
    r.pop("queue_per_minute")
    for k, v in r.items():
        print(f"{k:28s} {v}")
