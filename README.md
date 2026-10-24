# Transport Twin Study Path

An interactive self-study website on digital twins for transportation.
Live site: https://smrahmanbd.github.io/transport-twin-study/

| Page | What it has |
|------|-------------|
| `index.html` – Study path | Three layers (foundations, build and implement, research frontier), each with intuition, a study guide, a mind map, an exercise, flashcards and a quiz |
| `workshop.html` – Workshop | A full 3-day workshop: timed agenda, facilitator plans, engineer and manager tracks, capstone briefs and rubric, setup, assessment |
| `software.html` – Software guide | Required software for eight types of transport twin, layer by layer, open-source and commercial |
| `sumo.html` – SUMO Lab | Replays of real Eclipse SUMO runs on a three-signal corridor: fixed-time, actuated, a TraCI digital twin, and a twin fed only by virtual cameras; results over five held-out seeds; calibration with GEH; implementation steps from SUMO to a real camera twin |
| `slides.html` – Slides | Four presentation decks with speaker notes (print to PDF) |
| `guides.html` – Study guides | Workbooks, a SUMO lab manual, a camera-twin implementation guide, a cheat sheet and a glossary (print to PDF) |

## SUMO scenario

Everything needed to rerun the simulations is in [`sumo/`](sumo/) (see its README), or download
`sumo/sumo_corridor_twin.zip`. The web page reads the exported results from `data/`.

Static site, no build step, served by GitHub Pages.
