# SUMO corridor digital twin

A 1.4 km main street with three signalised junctions (J1, J2, J3), built for Eclipse SUMO 1.28.
It compares four ways of running the signals:

| Controller    | What it uses                                                         |
|---------------|----------------------------------------------------------------------|
| `fixed`       | 90 s fixed cycle, equal split                                        |
| `actuated`    | SUMO's built-in gap-based actuated control (local)                   |
| `twin`        | `twin_controller.py` through TraCI, perfect detectors + vehicle data |
| `twin_camera` | the same twin, fed only by the virtual cameras in `camera_sensor.py` |

## Quick start

```bash
pip install eclipse-sumo traci sumolib rtree
python make_routes.py                               # demand: low / medium / high
python make_detectors.py corridor_fixed.net.xml     # E1 loops and E2 queue detectors
python camera_sensor.py                             # camera icons for sumo-gui
python run_scenario.py --controller twin_camera --demand medium --gui
```

Other scripts:

- `calibrate_geh.py` – compares model counts with hidden "field" counts using GEH, rescales demand, checks again.
- `export_web.py` – runs all 12 combinations and writes the JSON used by the SUMO Lab web page.
- `corridor.sumocfg` – open the scenario directly in `sumo-gui`.

To rebuild the networks from the plain XML:

```bash
netconvert -n corridor.nod.xml -e corridor.edg.xml -o corridor_fixed.net.xml \
  --tls.default-type static --tls.cycle.time 90 --no-turnarounds true --tls.left-green.time 0
netconvert -n corridor.nod.xml -e corridor.edg.xml -o corridor_actuated.net.xml \
  --tls.default-type actuated --tls.cycle.time 90 --no-turnarounds true --tls.left-green.time 0
```

The scenario is a teaching example, not a model of a real street.
