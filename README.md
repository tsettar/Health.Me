# health.me

Personal health dashboard hub. `index.html` is a static launcher linking to
each self-contained app in `apps/`.

## Apps

- **Peptide Tracker** (`apps/peptide-tracker.html`) — the one health.me app:
  programs, vials, dose schedules, injection logs, a **Labs** tab with a full
  lab marker catalog (reference ranges, flags, "what it means" notes) merged
  in from the old Blood Test Dashboard, and a **Genome** tab (read-only) with
  the 213 curated findings from the old Genome Dashboard — searchable,
  filterable by category, sortable, cross-linked to the Labs tab both ways
  (a finding with a mapped gene shows "Markers to watch"; a marker with a
  mapped gene shows a "Genetic context" line). Canonical/live copy is
  published as a Claude Artifact from `OneDrive/Apps/peptide-tracker.html`;
  sync changes back to that path to keep the same artifact URL.
- **Genome Dashboard** (`apps/genome-dashboard.html`) — archived; the 23andMe
  raw SNP explorer this was built on. Its curated findings now live in the
  Peptide Tracker's Genome tab (`data/genome-findings.json`); the raw SNP
  table (~7 MB) was not carried over since nothing else needs it. Kept for
  reference, no longer linked from `index.html`.
- **Blood Test Dashboard** (`apps/blood-test-dashboard.html`) — archived; its
  data now lives in the Peptide Tracker's Labs tab (imported via
  `data/labs-history.json`). Kept for reference, no longer linked from
  `index.html`.

Each app is a single self-contained HTML file and works offline (opened
directly from disk or via GitHub Pages).

## Data

- `data/labs-history.json` — one-time import of the historical blood test
  data (82 tests, 16 draws, 2019–2026) in the Peptide Tracker's own export
  shape. Load it via the tracker's Logs → Import modal.
- `data/genome-findings.json` — the same `{ summary, findings }` object that's
  inlined as `const GENOME = {...}` in the tracker (~213 findings, ~48 KB),
  committed for reference alongside the app.

## Usage

Open `index.html` in a browser, or serve the folder statically:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000`.

**Data file (Chromium only)**: when opened outside the artifact (i.e. not
cloud-synced), the Peptide Tracker can keep its data in a JSON file you
control instead of only browser storage — set it up from Settings →
Data file → Choose file… or Create file….
