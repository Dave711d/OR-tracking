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
- Per-track TAVR role dwell, current/effective table team status, and
  evaluation summaries
- Sample video downloader and synthetic fixture generator in `download_sample.py`
- Single-clip evaluator in `evaluate_tavr.py`
- Manifest-driven multi-clip evaluator in `evaluate_tavr_suite.py`
- Browser-only Vercel demo in `public/`, including an opt-in static table
  fallback for low-motion room-view review and bundled evaluated TAVR replay
  artifacts from the real-footage suite
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

The evaluator prints JSON with a one-row procedure status summary, the stage
timeline, view segments, current and peak table rosters, per-track role dwell,
table-team status rows, table-presence intervals, table entry/exit events,
stage-by-stage table coverage, stage handoff summaries, stage roster summaries,
stage evidence summaries, procedure milestones, stage staffing summaries,
operator stage packets, a unified procedure event timeline, and low-confidence
segments to inspect before changing heuristics.
The status row includes an `effective_table_source` so fluoro/non-room frames
can distinguish live room rosters from the last trustworthy room-view table
observation, a current-stage recent room-window roster, or from no usable table
evidence. Current table fields remain current-frame truth; effective table
fields are the operator-facing continuity layer for brief same-stage detection
dropouts and held/non-room views.
The table-team rows classify each meaningful table-side track as
`active_current`, `recent_last_observed`, or `historical_seen`, with explicit
current/effective/last/peak roster membership flags. They keep both the raw
`dominant_role` and an operator-facing `table_team_role`, so a table-side track
with enough access/table evidence can read as a table operator even if its
dominant zone history was imaging or another support area. Stage coverage,
handoff, roster snapshot, and event timeline rows carry the same pair of roles,
so the stage-by-stage review is consistent with the operator-facing table-team
summary while preserving the raw audit trail. The evaluator also derives
`table_identity_groups`, which stitch compatible sequential raw track IDs into
canonical table-person groups using timing, role, position, area, and recent
motion continuity, then expose `merged_track_ids` for review.
It also writes those derived TAVR tables as CSV files alongside the frame-level
metrics CSV.
For low-motion room-view review, pass `--static-table-fallback` to opt into the
same conservative table-zone silhouette fallback exposed in the apps. This stays
off by default so default footage regressions do not silently count static
equipment as staff.
The Vercel browser uploader also canonicalizes table-side detections into stable
person IDs across short raw-ID gaps, crossings, and held non-room views, so the
live "who is at the table" panels track people rather than per-frame motion
cluster labels.

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

To force the full canonical TAVR workflow through the same scored table,
handoff, identity, packet, and quality checks, run the committed synthetic
full-sequence fixture. Regenerate it first if you are changing the fixture
generator:

```bash
python download_sample.py --tavr-fixture --output samples/synthetic_tavr_sample.mp4
python evaluate_tavr_suite.py docs/evaluation/tavr_synthetic_suite.json --output-dir outputs/tavr_synthetic_suite
```

The suite currently covers a mixed fluoroscopy-to-room clip, a fluoroscopy-only
negative clip, and a post-deployment/closure room clip from the public Sentara
TAVR video. It fails if scored label sections fall below their configured
thresholds, including `operator_packet_pass_rate`,
`operator_snapshot_pass_rate` for timestamped "who plus stage" checks, and
`table_identity_group_pass_rate` when packet, snapshot, or canonical
table-person expectations are labelled.
Each public suite case also declares `required_score_checks`; a required section
that is missing labels now fails the suite instead of being treated as an
unscored optional gap.

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
`Static table fallback` is an opt-in low-motion review mode for room-view clips:
it adds conservative table-zone silhouette candidates when table motion is
otherwise absent, leaves fluoroscopy/non-room suppression in place, and treats
those silhouettes as roster evidence rather than procedure-stage evidence.
The browser uploader also holds the seeded stage and suppresses table boxes on
low-colorfulness fluoroscopy/non-room frames.
When uploaded footage drops from room view into fluoroscopy, the browser packet
keeps a separate effective table roster from the last trustworthy room frame so
operators can distinguish current visible detections from held table context.
The app shows a `Procedure status` summary, `Table team summary`, the latest
table roster, last observed table roster, `Table identity groups`, and `View segments`,
`Procedure event timeline`,
`Procedure milestones`, `Stage evidence summary`, `Stage staffing summary`,
`Stage handoff summary`, `Stage roster summary`, `Stage table coverage`, `Table transition events`, and
`Table presence intervals` tables. Together these show the current observed
stage, next expected milestone, whether room tracking is available, who is at
the table now, the best available table roster source, who is active now,
recently seen, or historical table-side context, who was last observed
table-side, when the room camera is actually visible, which canonical TAVR
milestones have been observed, which
milestone is the current observed stage, which track IDs were table-side in each
TAVR phase, how long they were present, their operator-facing table role and raw
dominant role, which raw IDs were stitched into a canonical table person,
how many canonical table people were present in each stage or milestone,
which stable table-person IDs are current/effective/last-observed/peak at the
operator status point, whether they entered or exited during a stage, which
table-side IDs continued, appeared, or dropped at each stage boundary, and whether each
stage estimate is strong, weak, or held because the room view was unavailable. Mixed
room/fluoroscopy runs also include room-view frame counts, tracking-available
rates, and room-view table occupancy so staff/table coverage is not understated
by frames where the room was not visible. The `Operator stage packet` table is
the compact handover surface: one row per observed stage segment with current
stage status, evidence, handoff type, active/new/dropped table IDs, effective
current table context, quality flags, and a plain-English packet sentence.
It also writes:

- `outputs/*_metrics.csv`
- `outputs/*_procedure_status_summary.csv`,
  `*_operator_stage_packet.csv`,
  `*_table_team_summary.csv`,
  `*_stage_table_coverage.csv`, `*_stage_handoff_summary.csv`,
  `*_stage_evidence_summary.csv`, `*_procedure_milestones.csv`,
  `*_procedure_event_timeline.csv`, `*_table_transition_events.csv`, and
  related derived TAVR table CSVs
- `outputs/*_tracked.mp4` when annotated video is enabled

The Streamlit app includes a `Download TAVR tables` ZIP containing the derived
status, operator packet, table-team, stage, view, milestone, roster snapshot,
event, and quality CSVs for the current run.

For TAVR runs, CSV rows include `tavr_stage`, `tavr_stage_label`,
`tavr_confidence`, `table_count`, `table_track_ids`, `role_counts`,
`view_colorfulness`, and `tavr_signals`. The role/roster layer also emits
`who_at_table`,
`recent_table_track_ids`, `recent_who_at_table`, `role_track_ids`, and
`track_role_summary` so a test run can be audited by track ID rather than only
by frame-level counts. `who_at_table` is the fresh current-frame sighting;
`recent_who_at_table` is a short visual hold for people who were just seen at
the table and have not yet reappeared elsewhere, which makes brief occlusions
and motion-tracker dropouts easier to audit without inflating the current table
count.

Broadcast footage can switch the ROI from room camera to fluoroscopy. Frames
that look like non-room / fluoroscopy views are flagged as `non_room_view`, and
staff/table detections are suppressed for those frames to avoid inventing
table-side rosters from imaging motion. Stage staffing and coverage tables keep
both total-stage rates and room-view-only rates for those mixed-view clips.
Procedure-stage advancement is held on non-room frames and reported with low
confidence until room-video evidence returns.

## Vercel static demo

Vercel hosts the browser demo from `public/`. It accepts local video uploads and
performs client-side frame differencing, motion clustering, zone counts, and an
activity sparkline. The synthetic TAVR demo also shows procedure milestone
progress in canonical order, including the current observed stage, prior
observed stages, first/last seen times, peak table-side count, and unique
table-side IDs for each milestone. A `Table team status` panel keeps current
synthetic/browser-tracked IDs as active, recently observed, or historical so the
public Vercel surface mirrors the richer Python output. The browser inspector
also includes an `Operator packet` panel with the current stage, evidence,
handoff status, active table IDs, next stage, and quality flags.
The `Evaluated demo` replay selector loads compact backend artifacts from the
Sentara 900s, 1800s, 2400s, and 2700s windows plus the full synthetic TAVR
workflow, including weak visual support, held non-room context, recent
room-view hold, static-fallback review, and all-eight-stage table identity
cases. Refresh those public replay JSON files after rerunning the local suites
with:

```bash
python3 export_public_demo_data.py
```

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
