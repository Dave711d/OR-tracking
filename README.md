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
- De-identified video workflow state: patient/case in-room, out-of-room,
  room-view hold, anaesthetist/proceduralist role sightings, table-roster
  changes, and key event timeline rows
- Sample video downloader and synthetic fixture generator in `download_sample.py`
- Single-clip evaluator in `evaluate_tavr.py`
- Manifest-driven multi-clip evaluator in `evaluate_tavr_suite.py`
- Browser-only Vercel demo in `public/`, including live camera / browser
  stream mode, an opt-in static table fallback for low-motion room-view review,
  a video workflow panel for patient-room state and key events, and bundled
  evaluated TAVR replay artifacts from the real-footage suite
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
The Vercel browser surface also canonicalizes table-side detections into stable
person IDs across short raw-ID gaps, crossings, and held non-room views, so the
live "who is at the table" panels track people rather than per-frame motion
cluster labels. It can analyze uploaded videos, a local camera/capture-card
feed, or a browser-playable stream URL.
The same live/upload path now drives the video workflow layer: the browser
surface shows whether the de-identified patient/case is out of room, entering,
in room, on table, held while the room camera is unavailable, or leaving, plus
first-seen anaesthetist/proceduralist events and table-roster changes. The
patient state is a room workflow signal only; no patient identity is stored.

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
python evaluate_tavr_suite.py docs/evaluation/tavr_suite.json --output-dir outputs/tavr_suite_person_status_verify
```

To force the full canonical TAVR workflow through the same scored table,
handoff, identity, packet, and quality checks, run the committed synthetic
full-sequence fixture. Regenerate it first if you are changing the fixture
generator:

```bash
python download_sample.py --tavr-fixture --output samples/synthetic_tavr_sample.mp4
python evaluate_tavr_suite.py docs/evaluation/tavr_synthetic_suite.json --output-dir outputs/tavr_synthetic_person_status_verify
```

The suite currently covers a mixed fluoroscopy-to-room clip, a fluoroscopy-only
negative clip, and a post-deployment/closure room clip from the public Sentara
TAVR video. It fails if scored label sections fall below their configured
thresholds, including `operator_packet_pass_rate`,
`operator_snapshot_pass_rate` for timestamped "who plus stage" checks,
`table_presence_pass_rate` for exact canonical table-person intervals, and
`table_person_interval_pass_rate` for human-labelled table-person windows that
detect missed people, extra tracker people, identity fragmentation, and
no-table negative windows, and
`table_person_status_pass_rate` for human-labelled current/effective/last/peak
table rosters or explicit empty rosters at operator status snapshots or the
final procedure summary, and
`table_identity_group_pass_rate` when packet, snapshot, or canonical
table-person expectations are labelled.
Operator snapshot expectations are scored only against exported
`operator_status_snapshots` replay rows, so a passing timestamp can be selected
and audited in the public replay instead of existing only as an intermediate raw
frame.
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
The app leads with a `Current operator answer` pane: current stage, literal
current visible table, effective handoff table, stage roster, within-stage
entry/exit, and quality status are separated before the detailed audit tables.
It also shows a `Video workflow` pane for patient room-state, camera/source
status, anaesthetist and proceduralist counts, and latest workflow event, plus a
`Workflow events` timeline. The annotated MP4 labels tracked entities with
operator-facing role names such as `Anaesthetist` and `Proceduralist`.
It also shows `Operator status snapshots` so critical clip, stage, and view
transition points can be reviewed with the same current/effective table
semantics used by the public replay. The app shows a `Procedure status` summary,
`Table team summary`, the latest table roster, last observed table roster,
`Table identity groups`, and `View segments`,
`Procedure event timeline`,
`Procedure milestones`, `Stage evidence summary`, `Stage staffing summary`,
`Stage handoff summary`, `Stage roster summary`, `Stage table coverage`, `Table transition events`, and
`Table presence intervals` tables. Together these show the current observed
stage, next expected milestone, whether room tracking is available, who is at
the table now, the best available table roster source, who is active now,
recently seen, or historical table-side context, who was last observed
table-side, when the room camera is actually visible, which canonical TAVR
milestones have been observed, which
milestone is the current observed stage, which canonical table-person IDs were
table-side in each TAVR phase, how long they were present, their
operator-facing table role and raw dominant role, which raw IDs were stitched
into a canonical table person,
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
current table context, canonical within-stage entrants/exits, quality flags,
and a plain-English packet sentence.
In that packet, `stage_table_*` fields are cumulative sustained stage-history
evidence for people who were table-side long enough to count as part of the
stage roster. `brief_table_*` keeps short contacts audit-visible without
treating them as handoff staff. For the current stage, `active_table_*` is the
trusted active/effective roster at the operator status point, so it may be
narrower than the stage roster when the view is held from a recent or
last-observed room frame, or temporarily wider when recent context still
includes a brief contact.
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

## Live browser mode

The static browser app can run the same frame analyzer against live sources:

- `Live camera` uses `navigator.mediaDevices.getUserMedia()` and works on HTTPS
  or localhost. This is the easiest path for a USB webcam, HDMI capture card, or
  local OR camera feed exposed to the browser as a camera device.
- `Stream URL` attaches a browser-playable stream to the video element. Use an
  HTTPS URL that the browser can decode directly, such as an MP4/WebM stream or
  HLS on browsers with native HLS support. The stream must send CORS headers
  that allow canvas pixel reads, otherwise the video may play but the tracker
  will show `Stream pixels blocked by browser CORS`.
- `Stop live` stops camera tracks or clears the live stream source without
  disturbing uploaded-file and replay workflows.

For a real OR install, run the video conversion on an edge workstation inside
the hospital network and send the browser only a CORS-enabled, browser-readable
stream. For example, an RTSP/NDI/SDI source can be converted to low-latency HLS
or another browser-supported transport by the edge machine; the Vercel UI can
then consume that URL while all pixel processing stays local in the browser.

## Vercel static demo

Vercel hosts the browser demo from `public/`. It accepts local video uploads,
live camera/capture-card input, browser-playable stream URLs, and performs
client-side frame differencing, motion clustering, zone counts, and an activity
sparkline. The synthetic TAVR demo also shows procedure milestone
progress in canonical order, including the current observed stage, prior
observed stages, first/last seen times, peak table-side count, and unique
table-side IDs for each milestone. A `Table team status` panel keeps current
synthetic/browser-tracked IDs as active, recently observed, or historical so the
public Vercel surface mirrors the richer Python output. The browser inspector
also includes an `Operator packet` panel with the current stage, evidence,
handoff status, stage roster IDs, canonical within-stage entrants/exits,
latest/effective table IDs, next stage, and quality flags.
The `Evaluated demo` replay selector loads compact backend artifacts from the
Sentara 900s, 1800s, 2400s, and 2700s windows plus the full synthetic TAVR
workflow, including weak visual support, held non-room context, recent
room-view hold, no-table person negative checks, static-fallback review, closure
peak/last-observed labelled table people, and all-eight-stage table identity
cases. The sticky stage/table brief shows the current procedure stage,
canonical stage progress, next expected stage, stage handoff type, stage-wide
roster contacts with core-vs-supplemental dwell, audit-only brief contacts,
current visible table roster, and effective held table context so the replay can
be scanned before opening the deeper tables. A `Current operator answer` panel
now combines the current stage, procedure progress, visible table, effective
table, stage roster handoff, next stage, and quality flags into one compact
answer. The procedure-status panel also surfaces
evaluated score rows for stage status, operator snapshots, table-person
intervals/status, and no-table negative clips. When the replay scrubber moves,
the lower stage-roster and event timeline evidence panes are focused on the
selected snapshot's stage rather than showing a stale whole-case prefix. The
operator-packet card separates cumulative stage roster, active now, and
brief contacts so held-room context is not mistaken for live visibility. The
packet text uses `stage roster people` for sustained table-side people during
that stage, `brief contacts` for short audit-visible touches, and keeps
`active people` plus `latest table status` as the current/effective answer to
who is at the table now. Stage roster and operator packet cards show canonical
people for within-stage entry/exit while retaining raw IDs as audit detail.
Refresh those public replay JSON files after rerunning the local suites with:

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
