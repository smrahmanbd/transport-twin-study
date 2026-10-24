"""Write the traffic demand for the corridor scenario.

Usage:  python make_routes.py            (writes low, medium and high demand files)

Demand follows a simple peak: 0-300 s at 60 %, 300-1500 s at 100 % (the peak),
1500-1800 s at 60 %. The level multiplies every flow: low 0.6, medium 1.0, high 1.3.
"""

LEVELS = {"low": 0.6, "medium": 1.0, "high": 1.3}

# (flow id, from edge, to edge, vehicles per hour at the medium peak)
FLOWS = [
    ("eb",      "W_J1",  "J3_E",  1000),   # main street eastbound
    ("wb",      "E_J3",  "J1_W",   900),   # main street westbound
    ("n1s1",    "N1_J1", "J1_S1",  200),
    ("s1n1",    "S1_J1", "J1_N1",  200),
    ("n2s2",    "N2_J2", "J2_S2",  300),
    ("s2n2",    "S2_J2", "J2_N2",  250),
    ("n3s3",    "N3_J3", "J3_S3",  200),
    ("s3n3",    "S3_J3", "J3_N3",  200),
    ("w_n2",    "W_J1",  "J2_N2",  100),   # turning movements
    ("s1_e",    "S1_J1", "J3_E",   100),
    ("n3_w",    "N3_J3", "J1_W",   100),
    ("e_s2",    "E_J3",  "J2_S2",  100),
]
PERIODS = [(0, 300, 0.6), (300, 1500, 1.0), (1500, 1800, 0.6)]


def write(level, scale, path):
    lines = ['<routes>',
             '  <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="5" minGap="2.5" maxSpeed="16.7"/>']
    for begin, end, share in PERIODS:
        for fid, src, dst, vph in FLOWS:
            rate = round(vph * scale * share)
            if rate <= 0:
                continue
            lines.append(f'  <flow id="{fid}_{begin}" type="car" begin="{begin}" end="{end}" '
                         f'from="{src}" to="{dst}" vehsPerHour="{rate}" departLane="best" departSpeed="max"/>')
    lines.append('</routes>')
    # SUMO wants flows sorted by begin time
    open(path, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    for name, s in LEVELS.items():
        write(name, s, f"routes_{name}.rou.xml")
        print("wrote", f"routes_{name}.rou.xml")
