# TAVR Workflow Tracking

The prototype now includes a TAVR-focused workflow layer for transcatheter
aortic valve replacement / implantation room footage.

## Stage Taxonomy

The first-pass taxonomy follows the public ACC transfemoral TAVR handbook's
procedural sequence of access, valve crossing, optional balloon aortic
valvuloplasty, valve implantation, and access closure, with room-prep and
post-deployment assessment added as video-facing states:

1. `room_prep_drape`
2. `access_sheathing`
3. `angio_alignment_crossing`
4. `bav_optional`
5. `valve_delivery_positioning`
6. `valve_deployment`
7. `post_deploy_assessment`
8. `closure_finish`

Supporting public references:

- ACC TAVR Handbook, transfemoral procedural steps:
  <https://www.acc.org/~/media/Non-Clinical/Files-PDFs-Excel-MS-Word-etc/Membership/TAVR-Handbook/Chapter-11-Step-by-step-guide-transfemoral-corevalve-evolut-TAVR-March-2-2018.pdf>
- CMS TAVR decision memo describing heart-team and cath-lab / hybrid-OR setting:
  <https://www.cms.gov/medicare-coverage-database/view/ncacal-decision-memo.aspx?NCAId=257&proposed=N>
- Edwards SAPIEN 3 public IFU for delivery, positioning, deployment, assessment,
  removal, and access closure concepts:
  <https://eifu.edwards.com/eifu/5970f1a946e0fb00015e5f4c/DOC-0161577B.pdf>

## What the Current Prototype Infers

For each processed frame, the tracker emits:

- TAVR stage key and label
- Stage confidence
- Table-side count
- Table-side track IDs
- Current `who_at_table` roster with track IDs and dominant role estimates
- Coarse role-zone counts, such as `table_operator`, `access_operator`,
  `imaging`, `device_prep`, and `anesthesia`
- Per-track role dwell summaries in `track_role_summary`
- Zone and motion signals used by the heuristic

These values are written to the metrics CSV and shown in Streamlit.

## Visual Signals

The current model uses deterministic room-video heuristics:

- Normalized room zones for table, access site, anesthesia, imaging/C-arm, device
  table, and entry.
- Track IDs from OpenCV motion/contour tracking.
- Table-side membership based on whether tracked centroids are inside table or
  access zones.
- Persistent role history per track, so "who is at the table" is reported as
  stable track IDs with dominant role and table-presence ratio rather than only
  a transient frame count.
- A colorfulness guardrail for broadcast ROIs that switch to fluoroscopy or
  other non-room views. Those frames are flagged as `non_room_view`, and
  staff/table detections are suppressed so imaging motion does not become a
  fabricated table roster. Procedure-stage advancement is also held on those
  frames and emitted with low confidence, so seeded or last-known stage context
  is not mistaken for fresh room-video evidence.
- A sequential stage model with minimum dwell time so the estimate progresses
  like a procedure timeline rather than flickering frame by frame.

## Test-Footage Evaluation Loop

Use the evaluator for every new clip before changing heuristics:

```bash
python evaluate_tavr.py samples/tavr_sample.mp4 --max-frames 360
```

For a long live case, use `--start-s` or `--start-frame` to inspect targeted
access, deployment, and closure windows without losing source timestamps:

```bash
python evaluate_tavr.py samples/live_tavr.mp4 --start-s 900 --max-frames 600
```

For targeted windows, add `--initial-stage` when the starting phase is already
known from the video title, transcript, narration, or manual review:

```bash
python evaluate_tavr.py samples/live_tavr.mp4 \
  --start-s 900 \
  --max-frames 600 \
  --initial-stage valve_deployment \
  --roi 0,0.46,0.31,0.89 \
  --min-area 900
```

Valid seed stages are the stage keys in the taxonomy above. This keeps slice
evaluation useful for table-roster and local-stage behavior instead of forcing
every clip to replay the whole procedure sequence from room prep.

Use `--roi x0,y0,x1,y1` for broadcast videos where the actual room camera is a
small picture-in-picture inset and fluoroscopy or hemodynamic monitors dominate
the full frame. The same initial-stage and ROI controls are available in the
Streamlit sidebar for uploaded clips.

The JSON output includes:

- `stage_timeline`: contiguous stage segments with timestamps, peak table
  counts, and end-of-stage table roster snapshots.
- `view_segments`: contiguous room/non-room stretches with duration,
  colorfulness, dominant stage, and whether table tracking is available.
- `track_role_report`: latest role dwell for every track ID seen in the clip.
- `current_table_roster`: the most recent table-side roster.
- `last_observed_table_roster`: the latest room-view frame with table-side
  presence, useful when the clip ends in fluoroscopy or after the table-side
  staff have stepped away.
- `peak_table_roster`: roster from the frame with the highest table-side count.
- `table_roster_snapshots`: row-oriented current, last-observed, and peak roster
  snapshots for CSV export.
- `table_presence_roster`: tracks that spent meaningful time table-side anywhere
  in the clip, useful when the final frames are still or empty.
- `table_presence_intervals`: entry/exit-style table-side intervals with start
  and end timestamps, observed table frames, dominant role, and dominant stage.
- `table_transition_events`: table entry, table exit, stage-start presence, and
  stage-end presence events derived from the stage coverage rows.
- `stage_table_coverage`: one row per table-side track per contiguous stage
  segment, including stage start/end, first/last seen timestamps, coverage
  ratio, room-view coverage ratio, dominant role, and whether the track entered
  or exited during the stage.
- `stage_handoff_summary`: one row per contiguous stage segment showing the
  lead table-side track, active roster, table IDs that continued from the prior
  stage, new IDs, dropped IDs, within-stage entry/exit IDs, and a handoff type
  such as `table_roster_started`, `roster_added`, `roster_removed`,
  `roster_changed`, `roster_continued`, or `table_cleared`.
- `stage_evidence_summary`: one row per contiguous stage segment showing
  room-view availability, observable rate, mean/min/max stage confidence,
  dominant visual signal, and an evidence level: `strong_visual_support`,
  `moderate_visual_support`, `weak_visual_support`, or `held_non_room`.
- `procedure_milestones`: one row per canonical TAVR stage showing whether that
  milestone was observed in the clip, whether it is the current observed stage,
  the first/last observed timestamps, duration, evidence level, observable rate,
  mean confidence, peak table-side count, and unique table-side track count.
  Unobserved stages remain explicit rows so a partial clip does not imply prior
  or later procedural progress that was not visible.
- `procedure_event_timeline`: one chronological review table combining stage
  starts, room/non-room view starts, stage handoffs, and table-count peaks. Each
  event keeps the relevant stage, view, table count, lead track, table track
  IDs, roster labels, source table, and a human-readable label.
- `stage_staffing_summary`: one compact row per observed stage with duration,
  room-view frame counts, tracking-available rate, mean/peak table count,
  total-stage and room-view table occupancy, role mix, and the meaningful
  table-side roster for that stage.
- `low_confidence_segments`: frame ranges where stage confidence fell below the
  review threshold.
- `quality_flags`: warnings for rapid stage progression, early closure,
  fragmented tracks, non-room/fluoroscopy view, low-motion room views that may
  undercount staff, low stage-confidence spans, or unusually noisy motion
  detections.
- `label_score`: when `--labels` is provided, stage accuracy/confusion, table
  count range pass rates, table-presence expectation pass rates, and
  stage-staffing, stage-handoff, stage-evidence, procedure-milestone,
  procedure-event-timeline, roster-snapshot, and quality-flag expectation pass
  rates.

This is the preferred refinement surface for comparing synthetic fixtures,
downloaded public footage, and future labelled clips.

## Label Scoring

Use `--labels path/to/labels.json` to score a clip against expected stage and
table-presence labels:

```bash
python evaluate_tavr.py samples/live_tavr_slices/live_tavr_2700_30s.mp4 \
  --roi 0,0.46,0.31,0.89 \
  --initial-stage post_deploy_assessment \
  --min-area 300 \
  --max-frames 900 \
  --no-annotated-video \
  --labels docs/evaluation/sentara_live_2700_room_post.labels.json
```

The label file can include:

- `stage_segments`: expected stage over timestamp windows.
- `table_count_segments`: expected minimum/maximum table-side count windows, or
  `min_peak_count` when the requirement is that the table count reaches a peak
  during the window.
- `table_presence_expectations`: expected role-specific table-side intervals.
- `stage_staffing_expectations`: expected table-side staffing within a stage,
  such as minimum table-operator tracks, minimum observed table frames, minimum
  stage peak count, mean table count, table-occupancy rate, room-view mean table
  count, room-view table-occupancy rate, or tracking-available rate.
- `stage_handoff_expectations`: expected stage-boundary roster behavior, such as
  requiring a deployment-stage `table_roster_started` event, a closure-stage
  `roster_added` event, a lead role, minimum active/new/continued/dropped track
  counts, minimum lead table frames, or minimum tracking-available rate.
- `stage_evidence_expectations`: expected evidence support for a stage segment,
  such as requiring fluoroscopy-only stages to be `held_non_room`, requiring a
  room-visible deployment stage to have strong support, or requiring a visually
  ambiguous post-deploy / closure segment to remain labelled weak rather than
  overconfident. Expectations can constrain evidence level, dominant signal,
  observable rate, mean confidence, and room/non-room frame counts.
- `procedure_milestone_expectations`: expected canonical milestone progress,
  such as requiring a deployment milestone to be observed and current, requiring
  a prior milestone to remain `observed_prior`, requiring an unseen closure
  milestone to stay `not_observed_in_clip`, or constraining the evidence level,
  observable rate, mean confidence, peak table-side count, and unique
  table-side track count for the milestone.
- `event_timeline_expectations`: expected chronological review events, such as
  requiring a room-view return at deployment, a closure-stage roster-added event,
  a table peak, or a non-room event with zero table count. Expectations can
  constrain event type, stage, view, handoff type, timestamp window,
  tracking-available flag, minimum/maximum table count, role, and minimum
  matching roster tracks.
- `roster_snapshot_expectations`: expected current, last-observed, or peak
  roster snapshots, such as requiring at least one table-operator track in the
  last-observed room-view table roster.
- `quality_flag_expectations`: expected quality flags, such as requiring
  `non_room_view` and `low_stage_confidence` to cover a fluoroscopy-only ROI.

Labels are deliberately lightweight JSON so they can be hand-authored from
public clips, broadcast timestamps, or future labelled theatre footage.

## Multi-Clip Suite

Use the manifest runner to score several clips with one command:

```bash
python evaluate_tavr_suite.py docs/evaluation/tavr_suite.json --output-dir outputs/tavr_suite
```

The default suite is manifest-driven rather than shell-string-driven. Each case
declares a clip path, label path, ROI, starting stage, frame limit, and tracking
configuration. The runner writes per-case JSON plus
`outputs/tavr_suite/suite_summary.json`. It also exports the derived TAVR
summary tables as per-case CSV files, including view segments, procedure
milestones, stage staffing, stage table coverage, stage handoff summaries, stage
evidence summaries, procedure event timelines, table roster snapshots, table
transition events, table presence intervals, quality flags, and low-confidence
segments. The command exits non-zero if any scored label section falls below its
configured threshold.

The current local Sentara suite covers:

- `sentara_900_room_to_fluoro_low_motion`: short room-view stretch with sparse
  motion evidence followed by fluoroscopy, proving the system flags likely
  undercount instead of inventing table staff, and event-timeline labels the
  room-to-non-room view transition. Stage-evidence labels keep the whole slice
  weak because most frames are non-room and low-confidence.
- `sentara_1800_mixed_room`: fluoroscopy-to-room transition with table-side
  roster expectations once the room view returns, plus room-view denominator
  checks for the deployment-stage staffing summary and a deployment-stage
  `table_roster_started` handoff expectation. Event-timeline labels also verify
  the room-view return, table roster start, and deployment table peak. Stage
  evidence labels distinguish held non-room delivery-positioning context from
  strong room-visible deployment evidence.
- `sentara_2400_fluoro_negative`: fluoroscopy-only ROI that should produce no
  table staff, should be flagged `non_room_view`, and should emit non-room
  timeline events with zero table count. Stage evidence should remain
  `held_non_room`.
- `sentara_2700_room_post`: post-deployment / closure room-view segment with
  stage, table count, presence, staffing, room-view occupancy, quality, and
  post-deploy-to-closure handoff expectations. Event-timeline labels verify the
  closure stage start, closure roster addition, table peak, and later non-room
  transition. Stage-evidence labels keep both post-deploy and closure stages
  weak because the visual confidence is low and closure is partly non-room.

## Caveats

This is not a clinical decision system. It is a workflow prototype.

Video alone usually cannot identify named staff, distinguish surgeon from
interventional cardiologist, confirm internal catheter position, prove rapid
pacing, or separate balloon valvuloplasty from post-dilation. Current "who"
output means track IDs plus role/zone estimates, not biometric or badge-based
identity. Stronger identity and stage certainty require extra context such as
fluoroscopy feed, hemodynamics, device logs, audio, case metadata, or supervised
labels.

Use the current output as annotation scaffolding and QA instrumentation for test
footage. Treat low-confidence or visually ambiguous stages as review candidates.
