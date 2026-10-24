"""A virtual traffic camera for SUMO.

It imitates what a pole-mounted camera plus a computer-vision detector
(for example YOLO with a tracker) would report, including its flaws:

  * limited field of view and range
  * detection probability that falls with distance
  * occlusion: a car hidden behind a nearer car on the same line of sight
  * position noise, and speed estimated from successive noisy positions
  * map matching: the camera only knows x, y; it must work out the lane itself

The twin never sees SUMO's ground truth when it uses cameras; it only sees
the detections returned by CameraSensor.detect().
"""
import math
import random

import sumolib
import traci


class CameraSensor:
    def __init__(self, cam_id, x, y, heading_deg, fov_deg, range_m, net, lanes,
                 p_near=0.98, p_far=0.80, noise_m=1.0, seed=7):
        self.id, self.x, self.y = cam_id, x, y
        self.heading = math.radians(heading_deg)
        self.fov = math.radians(fov_deg)
        self.range = range_m
        self.net = net
        self.lanes = lanes                    # approach lanes this camera is trusted to watch
        self.p_near, self.p_far, self.noise = p_near, p_far, noise_m
        self.rng = random.Random(seed)
        self.prev = {}                        # track id -> (t, x, y) for speed estimates

    def _visible(self, x, y):
        dx, dy = x - self.x, y - self.y
        dist = math.hypot(dx, dy)
        if dist > self.range or dist < 1:
            return None
        ang = math.atan2(dy, dx) - self.heading
        ang = (ang + math.pi) % (2 * math.pi) - math.pi
        if abs(ang) > self.fov / 2:
            return None
        return dist, math.atan2(dy, dx)

    def detect(self, t):
        """Return a list of detections: dict(track, x, y, speed, lane, dist_to_stop)."""
        seen = []
        for v in traci.vehicle.getIDList():
            x, y = traci.vehicle.getPosition(v)
            vis = self._visible(x, y)
            if vis:
                seen.append((vis[0], vis[1], v, x, y))
        seen.sort()                                           # nearest first
        out, used_bearings = [], []
        for dist, bearing, v, x, y in seen:
            # occlusion: a nearer car within ~1.5 degrees blocks the view (cars are low; pole is 8 m)
            if any(abs(bearing - b) < math.radians(1.5) and dist - d > 6 for d, b in used_bearings):
                continue
            used_bearings.append((dist, bearing))
            p = self.p_near - (self.p_near - self.p_far) * dist / self.range
            if self.rng.random() > p:
                continue                                      # missed detection
            nx = x + self.rng.gauss(0, self.noise)
            ny = y + self.rng.gauss(0, self.noise)
            # speed from the tracker: distance between successive noisy positions
            speed = None
            if v in self.prev:
                pt, px, py = self.prev[v]
                if t - pt > 0:
                    speed = math.hypot(nx - px, ny - py) / (t - pt)
            self.prev[v] = (t, nx, ny)
            # map matching: nearest watched lane to the noisy position
            lane, pos, best = None, 0.0, 4.0
            for ln, d in self.net.getNeighboringLanes(nx, ny, 4.0):
                if ln.getID() in self.lanes and d < best:
                    lane, best = ln, d
            if lane is None:
                continue                                      # inside the junction or off the approaches
            pos, _ = lane.getClosestLanePosAndDist((nx, ny))
            out.append({"track": v, "x": nx, "y": ny, "speed": speed,
                        "lane": lane.getID(), "dist_to_stop": lane.getLength() - pos})
        # forget tracks not seen for 3 s
        self.prev = {k: val for k, val in self.prev.items() if t - val[0] <= 3}
        return out


def corridor_cameras(net):
    """One fisheye-style camera on a corner pole at each junction, watching all approaches."""
    cams = []
    for i, j in enumerate(("J1", "J2", "J3")):
        node = net.getNode(j)
        x, y = node.getCoord()            # netconvert shifts coordinates, so read them from the net
        lanes = {l.getID() for e in node.getIncoming() for l in e.getLanes()}
        cams.append(CameraSensor(f"cam_{j}", x + 12, y + 12, heading_deg=-135, fov_deg=360,
                                 range_m=110, net=net, lanes=lanes, seed=100 + i))
    return cams


def write_gui_additional(net, path="cameras.add.xml"):
    """Draw the cameras and their coverage in sumo-gui."""
    lines = ["<additional>"]
    for j in ("J1", "J2", "J3"):
        x, y = net.getNode(j).getCoord()
        cx, cy = x + 12, y + 12
        lines.append(f'  <poi id="cam_{j}" type="camera" color="255,200,0" layer="10" x="{cx}" y="{cy}" width="6" height="6"/>')
        ring = " ".join(f"{cx + 110 * math.cos(a / 18 * math.pi):.1f},{cy + 110 * math.sin(a / 18 * math.pi):.1f}" for a in range(36))
        lines.append(f'  <poly id="fov_{j}" type="camera_range" color="255,200,0,40" fill="1" layer="-1" shape="{ring}"/>')
    lines.append("</additional>")
    open(path, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    write_gui_additional(sumolib.net.readNet("corridor_fixed.net.xml"))
    print("wrote cameras.add.xml (load it in sumo-gui to see the cameras)")
