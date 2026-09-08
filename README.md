# CBR Test Analyzer (Streamlit)

A Python/Streamlit port of the CBR Test Analyzer, following **BS 1377‑4:1990, Clause 7**
(California Bearing Ratio). Same calculation engine as the browser version in the
Automation Hub pool — curve correction, CBR at 2.5/5.0 mm, compaction-curve fitting,
swell, and field-compaction check — plus a downloadable PDF lab report.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit front end (UI, session state, charts) |
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

It opens at `http://localhost:8501`, pre-loaded with an example dataset — edit any
field, or click **New blank test** to start your own.

> **Note on this build:** the sandbox this was built in has no outbound access to
> PyPI, so `streamlit run` itself could not be executed here to smoke-test the UI.
> Everything that *could* be verified without Streamlit was: all three files pass
> a Python syntax check, `cbr_engine.py`'s math was run directly and cross-checked
> against the browser-based tool (identical results — correction 0.867 mm,
> CBR₂.₅=10.44 %, CBR₅.₀=10.95 %, OMC=14.04 %, MDD=1.849 g/cm³), and `report.py`
> was run end-to-end with real ReportLab/Matplotlib calls, producing a valid
> 2‑page PDF that was inspected visually. Please run it locally once before your
> first real test — if anything in the Streamlit UI itself misbehaves, it's the
> one layer I couldn't execute directly, and I'll fix it fast.

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
