# OR Tracking

Deployable prototype for operating room staff motion tracking and activity
analysis. The current implementation uses CPU-friendly OpenCV motion tracking so
it can run today on Streamlit Cloud, Hugging Face Spaces, and a static Vercel
demo without model downloads or GPU access.

The code is structured so YOLO, pose estimation, and multi-camera fusion can be
added behind the same metrics surface later.

## What is included

- Streamlit uploader and tracking dashboard in `app.py`
- Deterministic video tracker in `or_tracking/`
- TAVR table-presence and procedure-stage inference
- Per-track TAVR role dwell, current table roster, and evaluation summaries
- Sample video downloader and synthetic fixture generator in `download_sample.py`
- Test-clip evaluator in `evaluate_tavr.py`
- Browser-only Vercel demo in `public/`
- Tests and GitHub Actions CI
- Deployment notes for Streamlit Cloud, Hugging Face Spaces, and Vercel

## Local test checklist

```bash
git clone https://github.com/Dave711d/OR-tracking.git
cd OR-tracking
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python download_sample.py --url 'https://www.youtube.com/watch?v=W7aRQGYhuk0'
pytest
streamlit run app.py --server.headless true
```

If the YouTube download is blocked by network or platform policy, the downloader
automatically creates a local deterministic fixture at the same output path. To
force an offline fixture directly:

```bash
python download_sample.py --fixture
```

For deterministic TAVR-stage test footage:

```bash
python download_sample.py --tavr-fixture --output samples/tavr_sample.mp4
```

To run a repeatable TAVR evaluation pass on any local clip:

```bash
python evaluate_tavr.py samples/tavr_sample.mp4 --max-frames 360
```

The evaluator prints JSON with the stage timeline, current table roster,
per-track role dwell, and low-confidence segments to inspect before changing
heuristics.

For long cases, evaluate targeted slices while preserving source timestamps:

```bash
python evaluate_tavr.py samples/live_tavr.mp4 --start-s 900 --max-frames 600
```

## Streamlit app

Run the Python prototype locally:

```bash
streamlit run app.py --server.headless true
```

Open the local URL Streamlit prints, upload a video, or click `Use synthetic
sample` / `Use TAVR sample`. The app writes:

- `outputs/*_metrics.csv`
- `outputs/*_tracked.mp4` when annotated video is enabled

For TAVR runs, CSV rows include `tavr_stage`, `tavr_stage_label`,
`tavr_confidence`, `table_count`, `table_track_ids`, `role_counts`, and
`tavr_signals`. The role/roster layer also emits `who_at_table`,
`role_track_ids`, and `track_role_summary` so a test run can be audited by track
ID rather than only by frame-level counts.

## Vercel static demo

Vercel hosts the browser demo from `public/`. It accepts local video uploads and
performs client-side frame differencing, motion clustering, zone counts, and an
activity sparkline.

```bash
npm install
npm run build
vercel deploy --prod
```

## Hugging Face Spaces

Create a Streamlit Space, import this repo, and keep `app.py` as the entrypoint.
`requirements.txt` and `runtime.txt` are already in the expected root locations.

## Streamlit Cloud

Import `Dave711d/OR-tracking`, set the main file to `app.py`, and deploy.

## Notes on scope

This prototype is for workflow demonstration and engineering validation. It is
not a clinical device, not a staff performance scoring system, and not suitable
for patient-identifiable deployment without privacy, governance, and security
review.

See [docs/tavr_workflow.md](docs/tavr_workflow.md) for the TAVR stage taxonomy,
source references, and inference caveats.
