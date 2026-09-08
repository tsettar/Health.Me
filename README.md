# health.me

Personal health dashboard hub. `index.html` is a static launcher linking to
each self-contained app in `apps/`.

## Apps

- **Peptide Tracker** (`apps/peptide-tracker.html`) — the primary health.me
  app: programs, vials, dose schedules, injection logs, and a **Labs** tab
  with a full lab marker catalog (reference ranges, flags, "what it means"
  notes) merged in from the old Blood Test Dashboard. Canonical/live copy is
  published as a Claude Artifact from `OneDrive/Apps/peptide-tracker.html`;
  sync changes back to that path to keep the same artifact URL.
- **Genome Dashboard** (`apps/genome-dashboard.html`) — 23andMe raw data
  explorer (traits, health markers, Promethease results). Still linked from
  the hub until it's folded into the tracker in a later phase.
- **Blood Test Dashboard** (`apps/blood-test-dashboard.html`) — retired from
  the hub; its data now lives in the Peptide Tracker's Labs tab (imported via
  `data/labs-history.json`). The file is kept for reference and isn't linked
  from `index.html` anymore.

Each app is a single self-contained HTML file and works offline (opened
directly from disk or via GitHub Pages).

## Data

- `data/labs-history.json` — one-time import of the historical blood test
  data (82 tests, 16 draws, 2019–2026) in the Peptide Tracker's own export
  shape. Load it via the tracker's Logs → Import modal.

## Usage

Open `index.html` in a browser, or serve the folder statically:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000`.
