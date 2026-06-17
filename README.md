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
- Single-clip evaluator in `evaluate_tavr.py`
- Manifest-driven multi-clip evaluator in `evaluate_tavr_suite.py`
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

The evaluator prints JSON with the stage timeline, view segments, current and
peak table rosters, per-track role dwell, table-presence intervals, table
entry/exit events, stage-by-stage table coverage, stage staffing summaries, and
low-confidence segments to inspect before changing heuristics.
It also writes those derived TAVR tables as CSV files alongside the frame-level
metrics CSV.

To compare output against expected stage/table labels:

```bash
python evaluate_tavr.py samples/live_tavr_slices/live_tavr_2700_30s.mp4 \
  --roi 0,0.46,0.31,0.89 \
  --initial-stage post_deploy_assessment \
  --min-area 300 \
  --max-frames 900 \
  --no-annotated-video \
  --labels docs/evaluation/sentara_live_2700_room_post.labels.json
```

To run the current multi-clip real-footage regression suite:

```bash
python evaluate_tavr_suite.py docs/evaluation/tavr_suite.json --output-dir outputs/tavr_suite
```

The suite currently covers a mixed fluoroscopy-to-room clip, a fluoroscopy-only
negative clip, and a post-deployment/closure room clip from the public Sentara
TAVR video. It fails if scored label sections fall below their configured
thresholds.

For long cases, evaluate targeted slices while preserving source timestamps:

```bash
python evaluate_tavr.py samples/live_tavr.mp4 --start-s 900 --max-frames 600
```

If you know the slice begins around a specific procedure phase, seed the stage
estimator so the clip does not restart from room prep:

```bash
python evaluate_tavr.py samples/live_tavr.mp4 \
  --start-s 900 \
  --max-frames 600 \
  --initial-stage valve_deployment \
  --roi 0,0.46,0.31,0.89 \
  --min-area 900
```

`--roi` is useful for broadcast cases where the room camera is a picture-in-
picture inset and fluoroscopy fills the main frame.

## Streamlit app

Run the Python prototype locally:

```bash
streamlit run app.py --server.headless true
```

Open the local URL Streamlit prints, upload a video, or click `Use synthetic
sample` / `Use TAVR sample`. Use the sidebar `Initial TAVR stage` selector for
targeted clips and `Crop to ROI` for broadcast videos with a room-camera inset.
The app shows the latest table roster plus `View segments`,
`Stage staffing summary`, `Stage table coverage`, `Table transition events`,
and `Table presence intervals` tables. Together these show when the room camera
is actually visible, which track IDs were table-side in each TAVR phase, how
long they were present, their dominant role, and whether they entered or exited
during a stage. Mixed room/fluoroscopy runs also include room-view frame counts,
tracking-available rates, and room-view table occupancy so staff/table coverage
is not understated by frames where the room was not visible.
It also writes:

- `outputs/*_metrics.csv`
- `outputs/*_stage_table_coverage.csv`, `*_table_transition_events.csv`, and
  related derived TAVR table CSVs
- `outputs/*_tracked.mp4` when annotated video is enabled

The Streamlit app includes a `Download TAVR tables` ZIP containing the derived
stage, view, roster, event, and quality CSVs for the current run.

For TAVR runs, CSV rows include `tavr_stage`, `tavr_stage_label`,
`tavr_confidence`, `table_count`, `table_track_ids`, `role_counts`,
`view_colorfulness`, and `tavr_signals`. The role/roster layer also emits
`who_at_table`,
`role_track_ids`, and `track_role_summary` so a test run can be audited by track
ID rather than only by frame-level counts.

Broadcast footage can switch the ROI from room camera to fluoroscopy. Frames
that look like non-room / fluoroscopy views are flagged as `non_room_view`, and
staff/table detections are suppressed for those frames to avoid inventing
table-side rosters from imaging motion. Stage staffing and coverage tables keep
both total-stage rates and room-view-only rates for those mixed-view clips.

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
