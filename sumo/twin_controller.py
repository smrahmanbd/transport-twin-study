"""A small 'digital twin' signal controller for the corridor, driven through TraCI.

Every second the twin mirrors the live state of the corridor and decides,
junction by junction, whether to keep the current green or switch.

The mirror can be fed from two sources:
  source="detectors"  E2 lane-area detectors plus exact vehicle states from SUMO
                      (an ideal, perfectly instrumented corridor)
  source="camera"     only what the virtual cameras in camera_sensor.py report:
                      missed cars, occlusion, position noise, map-matching errors

What makes it a twin rather than a local actuated controller: it counts
vehicles still upstream that will reach the stop line within HORIZON seconds
(for example a platoon released by the previous junction) and holds green
for them.

Phase layout produced by netconvert for every junction:
    0: main street green   1: main street yellow
    2: side street green   3: side street yellow
"""
import traci

MAIN_GREEN, MAIN_YELLOW, SIDE_GREEN, SIDE_YELLOW = 0, 1, 2, 3
MIN_GREEN = {MAIN_GREEN: 12, SIDE_GREEN: 6}      # seconds
MAX_GREEN = {MAIN_GREEN: 60, SIDE_GREEN: 35}
HORIZON = 8.0                                    # seconds of look-ahead
SWITCH_RATIO, SWITCH_MARGIN = 2.0, 6.0           # switch if waiting > ratio * served + margin
# Settings chosen on training seeds 101-103 (medium and high demand), then tested on seeds 1-5.
MAIN_EDGES = {"J1": ["W_J1", "J2_J1"], "J2": ["J1_J2", "J3_J2"], "J3": ["J2_J3", "E_J3"]}
SIDE_EDGES = {"J1": ["N1_J1", "S1_J1"], "J2": ["N2_J2", "S2_J2"], "J3": ["N3_J3", "S3_J3"]}


class TwinController:
    def __init__(self, junctions=("J1", "J2", "J3"), source="detectors", cameras=None):
        self.junctions = junctions
        self.source = source
        self.cameras = {c.id.replace("cam_", ""): c for c in (cameras or [])}
        self.detections = {}
        self.green_since = {j: 0.0 for j in junctions}
        self.last_phase = {j: None for j in junctions}
        self.log = []                                    # decisions, for the lab page

    # ---- 1. sense: refresh the mirror ----
    def sense(self, t):
        if self.source == "camera":
            self.detections = {j: cam.detect(t) for j, cam in self.cameras.items()}

    # ---- 2. estimate: demand on a group of approach edges ----
    def demand(self, junction, edges):
        """Vehicles queued plus vehicles that will arrive within HORIZON seconds."""
        if self.source == "camera":
            total = 0.0
            for d in self.detections.get(junction, []):
                if d["lane"].rsplit("_", 1)[0] not in edges:
                    continue
                if d["speed"] is None or d["speed"] < 1.5:  # noisy tracker: slow means queued
                    total += 1.0 if d["dist_to_stop"] < 80 else 0.0
                elif d["dist_to_stop"] / d["speed"] <= HORIZON:
                    total += 1.0
            return total
        total = 0.0
        for e in edges:
            for lane_idx in range(traci.edge.getLaneNumber(e)):
                lane = f"{e}_{lane_idx}"
                total += traci.lanearea.getJamLengthVehicle(f"e2_{lane}")
                length = traci.lane.getLength(lane)
                for v in traci.lane.getLastStepVehicleIDs(lane):
                    speed = traci.vehicle.getSpeed(v)
                    if speed < 0.5:
                        continue                         # already counted as queued
                    dist = length - traci.vehicle.getLanePosition(v)
                    if dist / max(speed, 1.0) <= HORIZON:
                        total += 1.0
        return total

    # ---- 3. decide and act ----
    def step(self, t):
        self.sense(t)
        for j in self.junctions:
            phase = traci.trafficlight.getPhase(j)
            if phase != self.last_phase[j]:
                self.last_phase[j] = phase
                self.green_since[j] = t                  # a new phase just started
            if phase in (MAIN_YELLOW, SIDE_YELLOW):
                continue                                 # let the yellow run its 3 s
            elapsed = t - self.green_since[j]
            main, side = self.demand(j, MAIN_EDGES[j]), self.demand(j, SIDE_EDGES[j])
            served, waiting = (main, side) if phase == MAIN_GREEN else (side, main)
            switch = False
            if elapsed >= MAX_GREEN[phase] and waiting > 0:
                switch = True
            elif elapsed >= MIN_GREEN[phase]:
                if served < 0.5 and waiting > 0:
                    switch = True                        # nobody left to serve
                elif waiting > SWITCH_RATIO * served + SWITCH_MARGIN:
                    switch = True                        # the other side needs it more
            if switch:
                traci.trafficlight.setPhase(j, phase + 1)   # go to its yellow
                self.log.append((round(t), j, "main" if phase == MAIN_GREEN else "side",
                                 round(elapsed), round(main, 1), round(side, 1)))
            else:
                traci.trafficlight.setPhaseDuration(j, 2)   # keep green a little longer
