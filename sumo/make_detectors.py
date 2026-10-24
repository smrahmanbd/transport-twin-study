"""Place detectors on every approach lane of the three signals.

Usage:  python make_detectors.py corridor_fixed.net.xml

E2 (lane-area) detectors cover the last 80 m before each stop line. The twin
controller reads them to see queues. E1 (induction loop) detectors sit 30 m
before each stop line and count vehicles every 5 minutes, like real loops.
"""
import sys
import sumolib

net = sumolib.net.readNet(sys.argv[1] if len(sys.argv) > 1 else "corridor_fixed.net.xml")
out = ['<additional>']
for tls_id in ("J1", "J2", "J3"):
    node = net.getNode(tls_id)
    for edge in node.getIncoming():
        for lane in edge.getLanes():
            L = lane.getLength()
            lid = lane.getID()
            start = max(0.0, L - 80.0)
            out.append(f'  <laneAreaDetector id="e2_{lid}" lane="{lid}" pos="{start:.1f}" endPos="{L - 0.5:.1f}" '
                       f'period="60" file="out/e2.xml"/>')
            out.append(f'  <inductionLoop id="e1_{lid}" lane="{lid}" pos="{max(1.0, L - 30.0):.1f}" '
                       f'period="300" file="out/e1_counts.xml"/>')
out.append('</additional>')
open("detectors.add.xml", "w").write("\n".join(out) + "\n")
print("wrote detectors.add.xml with", (len(out) - 2) // 2, "lanes covered")
