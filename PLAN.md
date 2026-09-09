# health.me integration plan

Goal: fold the Blood Test Dashboard and the Genome Dashboard into the Peptide
Tracker so there is one app (`apps/peptide-tracker.html`) with one store and
four screens: **Today | programs… | Labs | Genome | Logs**. The old dashboards are
retired from the hub but their files are kept (never delete Tim's files).

Three kinds of data, one app:

| Kind         | Source today                          | After                                              |
|--------------|---------------------------------------|----------------------------------------------------|
| actions      | tracker `programs/vials/logs`         | unchanged                                          |
| measurements | tracker `labs` (45 markers, no ranges) + blood dashboard (82 tests, 16 draws 2019-02-22 → 2026-07-23, hardcoded `const DATA`) | tracker `labs` is the single source; richer catalog + ref ranges; history imported via a generated JSON |
| reference    | genome dashboard (7.3 MB; only ~48 KB is curated `FINDINGS` + `SUMMARY`) | read-only Genome screen built on the 48 KB, inlined; raw SNP table not carried over |

Ground rules for every phase:
- Single self-contained HTML file, hand-written SVG charts, no Chart.js or other libraries.
- Use the existing CSS tokens (`--good`, `--warn`, `--bad`, `--surface-2`, …) and existing
  building blocks (`.card`, `.chip`, `.tile`, `.table-wrap`, `.checks`, `.sec`, `.section-head`).
- Both storage modes must keep working: artifact `db` (cloud) and `localStorage` (opened from disk).
  Nothing may `fetch()` a sibling file — artifacts block it.
- Keep the file name `apps/peptide-tracker.html` (the artifact republish path depends on it).
  At the end of each phase copy it over `C:\Users\tsett\OneDrive\Apps\peptide-tracker.html`
  (the canonical copy) so the two stay identical.
- Don't touch `apps/blood-test-dashboard.html` or `apps/genome-dashboard.html` except to read them.
- Verify by loading the page in a browser (`python -m http.server` from the repo root, open
  `/apps/peptide-tracker.html`) with zero console errors, and by exercising the new screen.
  `node --check` on the extracted `<script>` body catches syntax slips early.
- Commit at the end of each phase with a message that says what changed and why.

---

## Phase 1 — Labs merge

### 1a. Marker catalog
Replace `LAB_MARKERS` (peptide-tracker.html ~L635, array of `[id, name, unit, group]`) with a
richer catalog. Keep the array-of-arrays shape working (three call sites: the lab form select,
`sync`, and the submit handler) or convert all three; either way each marker gains:

- `aliases`: names as they appear in the blood dashboard's `DATA.tests[].test` (e.g. `'Total Testosterone'`
  for `TT`, `'Iron Saturation'` for `TSAT`, both `'Insulin'` and `'Insulin, Fasting'` for `INS`).
- `info`: `{ high, low, related }` text copied from the dashboard's `MARKER_INFO` (~L166–384),
  keyed to the new ids. Watch the encoding: that file's em dashes read as `�` when decoded as
  UTF-8 — detect (try cp1252) and write real `—` characters into the tracker.

Add markers for every dashboard test that has no tracker id (CBC differentials — absolute and %,
MCV/MCH/MCHC/RDW/MPV, immature granulocytes, UIBC, pregnenolone, progesterone, the thyroid,
liver, metabolic and lipid tests not already present). Ids stay short uppercase (`NEUT_ABS`,
`LYMPH_PCT`, `MCV`, `UIBC`, `PREG`, …). Existing ids (`E2`, `TT`, `FT`, `SHBG`, `LH`, `FSH`, `PRL`,
`DHEAS`, `IGF1`, `CORT`, `TSH`, `FT4`, `FT3`, `HCT`, `HGB`, `RBC`, `WBC`, `PLT`, `FERR`, `IRON`,
`TIBC`, `TSAT`, `VITD`, `B12`, `FOL`, `MG`, `ZN`, `GLU`, `A1C`, `INS`, `TC`, `LDL`, `HDL`, `TG`,
`APOB`, `LPA`, `ALT`, `AST`, `GGT`, `CREA`, `EGFR`, `BUN`, `PSA`, `CRP`, `HCY`, `BP`, `WT`, `OTHER`)
must not change — they are the `marker` value on stored lab docs and the `lab:<id>` series keys
in Graphs.

Groups (tracker's finer split wins): Hormones, Thyroid, CBC (rename the current "Blood"),
Iron, Vitamins, Metabolic (Insulin lives here, not under Iron), Lipids, Liver & kidney,
Inflammation, Other. Group order is the order listed here.

Unit normalisation when matching aliases: `x10E3/uL` ≡ `K/µL`, `x10E6/uL` ≡ `M/µL`,
`ug/dL` ≡ `µg/dL`, `mIU/L` ≡ `µIU/mL` for insulin.

### 1b. Lab doc shape
Lab docs (`labs/{id}`) currently: `{ marker, name, unit, value, at:'YYYY-MM-DD', note, createdAt }`.
Add optional `refLow`, `refHigh`, `refText`, `flag` (`'High'|'Low'|'Normal'|null`) and `source`
(file name / lab name). The lab form gets two optional inputs, "Reference low" and "Reference high";
`flag` is derived on save (value < refLow → Low, > refHigh → High, else Normal, null if no range).
Old docs without ranges keep working everywhere.

### 1c. History import file
Write a one-off script (scratchpad, not committed) that parses `const DATA` from
`apps/blood-test-dashboard.html`, maps every test to a catalog id via the aliases (fail loudly on
an unmapped test — add the marker rather than dropping data), and writes
`data/labs-history.json` in the tracker's own export shape:

```json
{ "exportedAt": "...", "labs": { "<id>": { "id": "<id>", "marker": "TT", "name": "Total testosterone",
  "unit": "ng/dL", "value": 601, "at": "2019-02-22", "refLow": 250, "refHigh": 1100,
  "refText": "250-1100 ng/dL", "flag": "Normal", "source": "bloods1 before.pdf", "note": "", "createdAt": "..." } } }
```

Ids must be deterministic (e.g. `bt-<markerId>-<date>` lower-cased) so re-importing overwrites
instead of duplicating. Commit the JSON. The existing Import modal (Logs screen, `importData()`
~L1835) already accepts this file — do not build a second import path. Sanity check: 82 tests,
every record present, no `null` values, count printed at the end.

### 1d. Labs screen
Promote labs from a section at the bottom of Logs to its own top-level tab **Labs** (between the
program tabs and Logs; `renderTabs()` ~L1046, a new `#view-labs` container, `render()` ~L1061).
The screen, top to bottom:

1. Summary strip (`.strip/.tile`): last draw date, results in that draw, how many flagged,
   markers tracked.
2. Category filter (`.gbtn` row like Graphs' range picker): All | Hormones | Thyroid | CBC | … ;
   remember the choice in `localStorage` (`pt-labs-cat`) like `pt-graph`.
3. One card per marker in the chosen categories (`labsSection` ~L701 already does the per-marker
   card + chart + collapsible table — extend it, don't fork it):
   - reference band drawn on the chart as a `--good-soft` rect between refLow/refHigh of the latest
     record that has a range; points outside the band drawn in `--bad`;
   - latest value chip coloured by `flag` (`.chip.good/.bad`), with `refText` beside it;
   - the collapsible table gains Range, Flag and Source columns;
   - a "What it means" `<details>` under the chart with `info.high` / `info.low` (only the one that
     matches the current flag when flagged, both otherwise) and "Usually reviewed with: …" chips
     from `info.related` that jump to that marker's card.
4. "+ Lab result" stays in the top bar and section header.

The program-screen labs block (`renderProgramDetail` ~L1313, TRT compounds only) keeps working via
the same `labsSection({ only, preset })`. Extend the compound → markers map so more programs get a
labs block: Retatrutide → `GLU, A1C, INS, TC, LDL, HDL, TG, WT`; GHK-Cu / BPC-157 / TB-500 →
`CRP`; growth-hormone secretagogues (ipamorelin, CJC, tesamorelin, MK-677) → `IGF1, GLU, A1C`;
keep the existing testosterone/estradiol/hCG/enclomiphene → `E2, TT, FT, SHBG, LH, FSH, PRL,
HCT, HGB, PSA`. One small table, matched case-insensitively against `p.compound + ' ' + p.name`.

Graphs (`availableSeries` ~L756) already lists every lab marker; after import it will show 80+
series under "Labs" — group the Labs checkboxes by catalog group so the picker stays usable.

### 1e. Hub
`index.html`: Peptide Tracker card becomes the primary "health.me" card ("Programs, labs and
genome in one place"); the Blood Test card is removed (its data now lives inside), the Genome
card stays until Phase 2. `README.md` updated to match. Note in the Brain
(`OneDrive/Brain/Projects/peptide-tracker.md`, "Labs" bullets) what changed.

---

## Phase 2 — Genome screen + cross-links

### 2a. Data
Extract `FINDINGS` (213 items: `name` rsid+genotype, `risk`, `category`, `magnitude`,
`maxMagnitude`, `summary`, `chrom`, `pos`, `gene`, `publications`, `freq`) and `SUMMARY`
(genome-wide stats, `exportDate`) from `apps/genome-dashboard.html` into a second `<script>`
block in the tracker: `const GENOME = { summary: {...}, findings: [...] };` placed just before the
main script so it is trivially strippable. ~48 KB. Do not carry the raw SNP table; nothing needs it.
Also commit the same JSON as `data/genome-findings.json` for reference.

### 2b. Genome screen
New top-level tab **Genome** (after Labs). Read-only — no store writes.
1. Summary strip: SNPs called, call rate, findings count, export date.
2. Controls row: search box (matches rsid, gene, summary), category chips (`.checks`, multi-select,
   counts in the label), sort: magnitude desc (default) | category | gene. Remember in
   `localStorage` (`pt-genome`).
3. Findings list, one `.card` row each: rsid + genotype (`.num`), gene chip, category chip,
   magnitude as a small bar (0–maxMagnitude, colour `--bad` ≥ 3, `--warn` ≥ 2, else `--muted`),
   summary text, publications count, chrom:pos small/faint. 213 rows render fine without
   virtualisation.
4. Findings whose summary starts with "Possible miscall" get a `.chip.plain` "possible miscall".

### 2c. Cross-links (the point of merging)
A small static table `GENE_MARKERS = { FTO: ['WT'], GCK: ['GLU','A1C'], CDKAL1: ['GLU','A1C'],
MTNR1B: ['GLU','A1C'], CBS: ['HCY','FOL','B12'], UMOD: ['CREA','EGFR'], … }` built from the
genes actually present in `FINDINGS` (list them first; only map genes with an obvious lab
counterpart, leave the rest unmapped — do not invent associations).
- On the Genome screen, a finding whose gene is mapped shows "Markers to watch" chips with the
  latest lab value + flag for each (or "not tracked yet" → opens the lab form preset to that marker).
- On the Labs screen, a marker card whose id appears in `GENE_MARKERS` shows a one-line
  "Genetic context: <gene> — <finding summary>" under the chart, linking to the Genome screen
  filtered to that gene.
- Program screens: no genome links (weak evidence); labs links from Phase 1 are enough.

### 2d. Hub / retire
`index.html` drops the Genome card; the hub is now a single card plus a small "Archived" line
linking the two old dashboards (files stay in `apps/`). Update README and the Brain project file.

---

## Phase 3 — Local-file storage

For the disk-opened copy, upgrade the `localStorage` fallback with the File System Access API:
- `store.init()` (~L434): after the cloud check fails, look for a saved file handle in IndexedDB
  (`pt-file-handle`). If present and permission is granted (`queryPermission`/`requestPermission`
  on a user gesture), read the JSON into `store.data` and mark mode `file`; otherwise stay `local`.
- Settings gains "Data file": *Choose file…* (`showOpenFilePicker`, JSON) / *Create file…*
  (`showSaveFilePicker`, default name `health-me-data.json`) / *Disconnect*. When connected, every
  `store.put`/`store.del` writes the whole `store.data` to the file (debounced ~300 ms) after
  updating memory and `localStorage` (which stays as the crash-safe mirror).
- Storage badge: `Synced` (cloud) / `File: <name>` (file) / `This device only` (local).
- Feature-detect (`'showOpenFilePicker' in window`); browsers without it never see the buttons.
- Test in Chromium: create file, log a lab, confirm the JSON on disk updates; reload, confirm data
  comes back from the file without re-picking (permission prompt at most once per session).

---

## Order and hand-off
Phase 1 → Phase 2 → Phase 3, each as its own commit. Phase 2 depends on the Labs screen and the
catalog ids from Phase 1; Phase 3 is independent of 2 but touches `store`, so it goes last to
avoid merge noise.
