# CBR Test Analyzer (Streamlit)

A Python/Streamlit tool for **BS 1377‑4:1990, Clause 7** (California Bearing Ratio)
laboratory reporting, modelled directly on a real project lab-report template
(4 worksheets, from an actual road rehabilitation project):

1. **Compaction (Proctor)** — moisture/density trials → fitted OMC & MDD.
2. **CBR compaction** — specimens compacted at OMC using different compactive
   efforts (default 56 / 25 / 10 blows, editable) → wet/dry density, %MDD per specimen.
3. **Penetration testing** — per specimen, load-penetration data → CBR @ 2.5 mm
   and 5.0 mm; governing CBR = **MAX** of the two (the template's convention — no
   retest gate). The classic BS1377 curve-origin correction is available as an
   optional, off-by-default toggle since the source paperwork doesn't use it.
4. **Design CBR summary** — CBR vs %MDD across specimens, fitted with a smooth
   curve (quadratic for 3+ points) and read off automatically at target compaction
   levels (default 93/95/98/100%) — this replaces the template's manual
   chart-reading step with an actual computed interpolation.

Plus a downloadable PDF lab report covering all four stages.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit front end — 4 tabs (one per stage above), session state, charts |
| `cbr_engine.py` | Pure calculation engine — no Streamlit dependency, unit-testable on its own |
| `report.py` | Builds the downloadable PDF report with ReportLab |
| `requirements.txt` | Python dependencies |
| `.streamlit/config.toml` | App theme (brass/graphite palette matching the tool pool) |

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

It opens at `http://localhost:8501`, pre-loaded with an example dataset modelled on
the source project — edit any field, or click **New blank test** to start your own.

## Judgment calls made vs. the source spreadsheet template

- **Governing CBR = MAX(CBR@2.5mm, CBR@5.0mm)**, matching the template exactly —
  no "retest to confirm" gate (that was this tool's earlier, stricter convention
  before being rebuilt around the real template).
- **BS1377 curve-origin correction is optional and off by default** — the
  template's "corrected" column is proving-ring calibration, not a geotechnical
  curve-shape correction, so applying one by default would diverge from the
  template's numbers. Turn it on in tab 3 if your raw curve needs it.
- **Standard loads are editable** (default 13.2 / 20.0 kN per BS1377, but the
  source template used calibrated values of 13.344 / 20.016 kN — enter whichever
  your lab uses).
- **Design CBR is computed, not hand-read off a chart** — a quadratic fit through
  the specimen points (linear if only 2), evaluated at each target %MDD, flagging
  any target outside the tested compaction range as extrapolated.
- **Mould Factor is entered directly per specimen** (as in the template — each
  physical mould is individually calibrated), rather than always derived from
  mould dimensions.

## Verification performed in this sandbox

This sandbox has no outbound access to PyPI, so `streamlit run` itself could not
be executed here to smoke-test the UI directly. Everything that *could* be
verified without Streamlit was:

- All three files pass a Python syntax check (`python3 -m py_compile`).
- Every new `cbr_engine.py` function was run directly and cross-checked against
  the real numbers extracted from the source Excel template — exact matches,
  e.g. wet density 2092.544 kg/m³, moisture content 4.20979986197377%, dry
  density 2008.01076556291 kg/m³, relative compaction 101.055257079621% /
  94.3821029082774% / 90.0427092238339%, and CBR@2.5mm = 36.72% against the
  template's own formulas.
- The `st.data_editor` → nullable-dtype-column data path was specifically
  simulated end-to-end (blank cells producing pandas' `pd.NA`, not `None`/`NaN`)
  to catch the same class of bug that broke the single-specimen version in
  production — `cbr_engine.py` now coerces every scalar input through a small
  `_f()` helper so `pd.NA`, `None`, and `NaN` all behave identically.
- `report.py` was run end-to-end with real ReportLab/Matplotlib calls, producing
  a valid multi-page PDF that was inspected visually (including a deliberately
  long project title, to confirm long text wraps inside table cells instead of
  overflowing into the next column).

Please run it locally once before your first real test — if anything in the
Streamlit UI itself misbehaves, it's the one layer that couldn't be executed
directly here, and it'll get fixed fast.

## Deploy to Streamlit Community Cloud

1. **Push this folder to a GitHub repo** (public or private):
   ```bash
   cd cbr_streamlit_app
   git init
   git add .
   git commit -m "CBR Test Analyzer"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub.
3. Click **New app**, pick the repo/branch, and set the main file path to `app.py`.
4. Click **Deploy**. Streamlit Cloud installs `requirements.txt` automatically and
   gives you a public `https://<something>.streamlit.app` URL.
5. Whenever you push new commits to `main`, the deployed app redeploys automatically.

No secrets or API keys are needed for this app.

## Extending it

- `cbr_engine.py` has no Streamlit or UI code in it — reuse it directly in a future
  Automation Hub tool (e.g. a batch processor, or a version wired into a database)
  without touching the front end.
- Standard loads (13.2 kN / 20.0 kN) and the plunger area are constants at the top
  of `cbr_engine.py` if you ever need to support a different national standard.
