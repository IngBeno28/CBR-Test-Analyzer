# CBR Test Analyzer (Streamlit)

A Streamlit app for **BS 1377‑4:1990, Clause 7** (California Bearing Ratio)
laboratory reporting. It walks through the full CBR workflow in four stages:

1. **Compaction (Proctor)** — moisture/density trials → fitted OMC & MDD.
2. **CBR compaction** — specimens compacted at OMC using different compactive
   efforts (default 56 / 25 / 10 blows, editable) → wet/dry density, %MDD per specimen.
3. **Penetration testing** — per specimen, load-penetration data → CBR @ 2.5 mm
   and 5.0 mm; governing CBR is the **MAX** of the two, with no retest gate. An
   optional BS1377 curve-origin correction is available and off by default.
4. **Design CBR summary** — CBR vs %MDD across specimens, fitted with a smooth
   curve (quadratic for 3+ points) and read off automatically at target
   compaction levels (default 93/95/98/100%), replacing manual chart-reading
   with a computed interpolation.

Plus a downloadable PDF lab report covering all four stages.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit front end — one scrolling page covering all four stages, session state, charts |
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

It opens at `http://localhost:8501`, pre-loaded with an example dataset —
edit any field, or click **New blank test** to start your own.

## Design notes

- **Governing CBR = MAX(CBR@2.5mm, CBR@5.0mm)** — no "retest to confirm" gate.
- **BS1377 curve-origin correction is optional and off by default**, since
  applying one unconditionally would shift results for labs whose raw curves
  don't need it. Turn it on in the penetration testing section if yours does.
- **Standard loads are editable** (default 13.2 / 20.0 kN per BS1377) — enter
  whichever calibrated values your lab uses.
- **Design CBR is computed, not hand-read off a chart** — a quadratic fit through
  the specimen points (linear if only 2), evaluated at each target %MDD, flagging
  any target outside the tested compaction range as extrapolated.
- **Mould Factor is entered directly per specimen**, since each physical mould
  is individually calibrated, rather than always derived from mould dimensions.

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
