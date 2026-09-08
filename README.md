# health.me

Personal health dashboard hub. `index.html` is a static launcher linking to
each self-contained app in `apps/`.

## Apps

- **Peptide Tracker** (`apps/peptide-tracker.html`) — programs, vials, dose
  schedules, injection logs, and lab markers. Canonical/live copy is
  published as a Claude Artifact from `OneDrive/Apps/peptide-tracker.html`;
  sync changes back to that path to keep the same artifact URL.
- **Blood Test Dashboard** (`apps/blood-test-dashboard.html`) — lab panels
  over time with flagged values, reference ranges, and trend charts.
- **Genome Dashboard** (`apps/genome-dashboard.html`) — 23andMe raw data
  explorer (traits, health markers, Promethease results).

Each app is a single self-contained HTML file and works offline (opened
directly from disk or via GitHub Pages).

## Usage

Open `index.html` in a browser, or serve the folder statically:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000`.
