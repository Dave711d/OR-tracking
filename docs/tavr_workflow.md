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
The static Vercel demo mirrors the operator-facing shape with a browser-only
synthetic TAVR run that shows the current procedure milestone, observed prior
milestones, first/last seen timing, peak table-side count, and unique
table-side IDs. It also keeps a `Table team status` panel for active, recently
observed, and historical table-side IDs in the current browser session, plus an
`Operator packet` panel for the current stage, evidence, handoff status, active
table IDs, next stage, and quality flags.

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
- A short recent-table hold that keeps a separate `recent_who_at_table` audit
  field when a table-side person briefly disappears behind an occlusion or a
  motion-tracking dropout. The fresh `who_at_table` / `table_count` fields stay
  current-frame only; the recent field is explicitly stale evidence and is
  cleared as soon as that track reappears away from the table or ages out.
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

Add `--static-table-fallback` when reviewing low-motion room-view footage where
table-side staff are visually present but too still for motion-only tracking.
The fallback is opt-in so the default evaluator and regression suite keep
static equipment from being counted as people. Static fallback detections update
the table roster and role history, but they are deliberately treated as
roster-only evidence; by themselves they do not advance the TAVR procedure
stage.

The JSON output includes:

- `procedure_status_summary`: a one-row operator status that combines current
  stage, current stage evidence status (`strong_visual_support`,
  `moderate_visual_support`, `weak_visual_support`, or
  `held_non_room_context`), next expected milestone, evidence level,
  observable rate, mean confidence, latest room/non-room view state, tracking
  availability, current table roster, effective table roster source, last
  observed table roster, peak table roster, quality flag codes, and a concise
  `operator_summary` sentence. `effective_table_source` is
  `current_room_view`, `current_room_view_empty`,
  `current_stage_recent_room_window`, `recent_room_view_hold`,
  `last_observed_room_view`, or `no_room_table_evidence`.
  `current_table_*` stays literal current-frame truth; the current-stage recent
  room window is used only for effective table status when a same-stage roster
  member briefly drops out of the latest frame. This keeps fluoroscopy frames
  from implying a false empty table when the room is not visible, and keeps a
  recently observed table roster visible when the latest room-view frame is
  motion-quiet rather than confidently empty.
- `operator_status_snapshots`: timestamped procedure-status rows at critical
  replay points, including clip start/end, stage boundaries, view switches,
  peak table, and last-observed table. These rows reuse
  `procedure_status_summary` semantics so the public replay can answer "what
  stage are we at, and who is effectively at the table?" throughout the clip,
  not only at the final frame. Streamlit renders the same snapshots for uploaded
  footage so the public replay and upload path share the same operator answer
  contract.
- `operator_stage_packet`: one row per observed stage segment designed as a
  compact handover packet. Each row combines current/prior stage status,
  stage evidence status, timing, evidence level, observable rate, mean
  confidence, handoff type, peak table count, active/canonical table-person
  counts, lead role, active/new/dropped table IDs, canonical within-stage
  entry/exit table-person IDs, the effective current table source for the
  current stage, quality flag codes, and a plain-English `operator_packet`
  sentence.
- `stage_timeline`: contiguous stage segments with timestamps, peak table
  counts, and end-of-stage table roster snapshots.
- `view_segments`: contiguous room/non-room stretches with duration,
  colorfulness, dominant stage, and whether table tracking is available.
- `track_role_report`: latest role dwell for every track ID seen in the clip.
- `current_table_roster`: the most recent table-side roster.
- `last_observed_table_roster`: a stable roster from the latest recent
  room-view window with table-side presence, useful when the clip ends in
  fluoroscopy or after the table-side staff have stepped away without letting a
  single sparse terminal frame undercount the table team.
- `peak_table_roster`: roster from the frame with the highest table-side count.
- `table_roster_snapshots`: row-oriented current, last-observed, and peak roster
  snapshots for CSV export.
- `table_team_summary`: one row per meaningful table-side track across the clip.
  Rows include a representative raw `track_id`, `canonical_table_id`,
  `merged_track_ids`, `team_status` (`active_current`,
  `recent_last_observed`, or `historical_seen`), raw `dominant_role`,
  operator-facing `table_team_role`, table-role confidence,
  current/effective/last/peak roster membership flags, first/last table-side
  timestamps, age from clip end, table frames, table-presence ratio, dominant
  stage, role/stage counts, and a compact label. This is the operator-facing
  "who is/was at the table" table when the latest frame is non-room or the
  current room view is empty.
- `table_identity_groups`: canonical table-person groups stitched from
  compatible sequential raw track IDs using table-side timing, role, centroid,
  area, and recent motion continuity. Brief table-side crossings or occlusions
  can therefore keep the moving person identity instead of blindly following
  the next raw track ID. These rows keep the representative raw track ID plus
  `merged_track_ids` so identity stitching remains auditable.
- `table_presence_roster`: canonical table people that spent meaningful time
  table-side anywhere in the clip, useful when the final frames are still or
  empty.
- `table_presence_intervals`: entry/exit-style table-side intervals with start
  and end timestamps, observed table frames, canonical table ID, merged raw
  track IDs, raw dominant role, operator-facing table role, and dominant stage.
- `table_transition_events`: table entry, table exit, stage-start presence, and
  stage-end presence events derived from the stage coverage rows.
- `stage_table_coverage`: one row per table-side track per contiguous stage
  segment, including stage start/end, first/last seen timestamps, coverage
  ratio, room-view coverage ratio, canonical table ID, merged raw track IDs, raw
  dominant role, operator-facing table role, and whether the track entered or
  exited during the stage.
- `stage_handoff_summary`: one row per contiguous stage segment showing the
  lead table-side track, operator-facing lead role plus raw lead dominant role,
  active roster, table IDs that continued from the prior stage, new IDs, dropped
  IDs, within-stage entry/exit IDs, and a handoff type such as
  `table_roster_started`, `roster_added`, `roster_removed`, `roster_changed`,
  `roster_continued`, or `table_cleared`.
- `stage_roster_summary`: one concise operator-facing row per contiguous stage
  segment combining evidence, peak table count, active/canonical table-person
  count, lead table-side role, continued/new/dropped IDs, within-stage
  entry/exit IDs, handoff type, and readable roster labels.
- `stage_evidence_summary`: one row per contiguous stage segment showing
  room-view availability, observable rate, mean/min/max stage confidence,
  dominant visual signal, and an evidence level: `strong_visual_support`,
  `moderate_visual_support`, `weak_visual_support`, or `held_non_room`.
- `timebase_summary`: one row describing the clock contract for the run:
  clip-local start/end, original source/case start/end, frame offsets, FPS, and
  the source offset. Pre-cut public case slices can therefore show `clip 0-30s`
  while retaining the original procedure clock such as `source 1800-1830s`.
- `procedure_milestones`: one row per canonical TAVR stage showing whether that
  milestone was observed in the clip, whether it is the current observed stage,
  the first/last observed timestamps, duration, evidence level, observable rate,
  mean confidence, peak table-side count, raw unique table-side track count, and
  canonical table-person count after identity stitching.
  Unobserved stages remain explicit rows so a partial clip does not imply prior
  or later procedural progress that was not visible.
- `procedure_event_timeline`: one chronological review table combining stage
  starts, room/non-room view starts, stage handoffs, and table-count peaks. Each
  event keeps the relevant stage, view, table count, lead track, table-facing
  role, raw dominant role, table track IDs, roster labels, source table, and a
  human-readable label.
- `stage_staffing_summary`: one compact row per observed stage with duration,
  room-view frame counts, tracking-available rate, mean/peak table count,
  total-stage and room-view table occupancy, raw unique track count, canonical
  table-person count, role mix, and the meaningful table-side roster for that
  stage.
- `low_confidence_segments`: frame ranges where stage confidence fell below the
  review threshold.
- `quality_flags`: warnings for rapid stage progression, early closure,
  fragmented tracks, non-room/fluoroscopy view, low-motion room views that may
  undercount staff, low stage-confidence spans, or unusually noisy motion
  detections.
- `label_score`: when `--labels` is provided, stage accuracy/confusion, table
  count range pass rates, table-presence expectation pass rates, and
  stage-staffing, stage-table-coverage, table-transition, stage-handoff,
  stage-roster, stage-evidence, procedure-milestone, procedure-status,
  operator-packet, table-team, procedure-event-timeline, roster-snapshot, and
  quality-flag expectation pass rates.

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
  --source-start-s 2700 \
  --no-annotated-video \
  --labels docs/evaluation/sentara_live_2700_room_post.labels.json
```

The label file can include:

- `timebase`: `clip` or `source`. `clip` is the default and means
  `start_s`/`end_s` windows are local to the exported clip. `source` means the
  windows use the original procedure/source clock. Use `--source-start-s` for
  pre-cut clips when you want JSON/CSV artifacts to show source time without
  seeking into a longer file.
- `stage_segments`: expected stage over timestamp windows.
- `table_count_segments`: expected minimum/maximum table-side count windows, or
  `min_peak_count` when the requirement is that the table count reaches a peak
  during the window.
- `table_presence_expectations`: expected role-specific table-side intervals,
  including exact or required canonical table-person IDs via
  `expected_canonical_table_ids` / `required_canonical_table_ids`, plus exact or
  required raw track IDs when a fixture should guard the raw tracker surface.
- `table_person_interval_expectations`: human-labelled table-person windows.
  Each window can contain a `persons` list with stable `person_id` values and
  optional tracker mappings such as `expected_canonical_table_ids`,
  `accepted_canonical_table_ids`, `max_canonical_table_ids`, and
  `max_merged_track_ids`. The score checks each labelled person and also fails
  unmatched extra canonical table people in the same window when
  `max_extra_canonical_table_ids` is set. Use `person_id` as the ground-truth
  handle; tracker IDs are regression mappings that should be updated after
  visual review.
- `table_person_status_expectations`: human-labelled table-person roster
  checks at an operator snapshot or the procedure status summary. Use stable
  `person_id` values with tracker mappings, then require or forbid those people
  in the `current`, `effective`, `last_observed`, and `peak` table rosters. Exact
  roster fields such as `expected_effective_person_ids` fail both missed people
  and extra tracked people.
- `stage_staffing_expectations`: expected table-side staffing within a stage,
  such as minimum table-operator tracks, minimum observed table frames, minimum
  stage peak count, mean table count, table-occupancy rate, room-view mean table
  count, room-view table-occupancy rate, canonical table-person count bounds, or
  tracking-available rate. `role`
  matches the operator-facing table role; use `dominant_role` when you need to
  constrain the raw zone-history role.
- `stage_table_coverage_expectations`: expected per-track coverage rows within a
  stage, such as requiring a minimum number of table-operator coverage rows,
  requiring zero coverage rows in fluoroscopy-only clips, or constraining
  observed table frames, coverage ratio, room-view coverage ratio, tracking
  availability, table-role confidence, merged raw track IDs, entry/exit flags,
  and label text. Use `required_merged_track_ids` for subset checks and
  `expected_merged_track_ids` when a curated fixture must match the raw-ID
  stitching exactly.
- `table_transition_expectations`: expected table entry, exit, stage-start
  presence, or stage-end presence events. Labels can require minimum/maximum
  matching events, zero events in non-room clips, stage/segment/time windows,
  operator-facing role, raw dominant role, track/canonical IDs, merged raw track
  IDs, observed table frames, coverage ratios, tracking availability, table-role
  confidence, and label text. `expected_merged_track_ids` is available here too
  for exact entry/exit identity stitching checks.
- `stage_handoff_expectations`: expected stage-boundary roster behavior, such as
  requiring a deployment-stage `table_roster_started` event, a closure-stage
  `roster_added` event, a lead role, minimum active/new/continued/dropped track
  counts, exact active/continued/new/dropped canonical table-person sets,
  minimum lead table frames, or minimum tracking-available rate. `role` and
  `lead_role` match operator-facing table roles; `dominant_role` and
  `lead_dominant_role` constrain the raw role when needed. Use
  `required_*_canonical_table_ids` for subset checks and
  `expected_*_canonical_table_ids` for exact checks; a present empty expected
  list means the stage boundary must have no canonical people in that delta.
- `stage_roster_expectations`: expected concise per-stage roster summaries,
  combining stage, handoff type, evidence level, active table-facing role
  counts, peak table count, canonical table-person count, exact
  active/continued/new/dropped canonical table-person sets, within-stage
  entry/exit IDs, lead role, observable rate, tracking rate, and mean
  confidence. Use this when the question is "who was at the table during this
  procedure stage?" rather than only "what happened at the boundary?"
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
  table-side track count or canonical table-person count for the milestone.
- `procedure_status_expectations`: expected one-row operator status, including
  current stage, current milestone status, current stage evidence status, next
  stage, current view, tracking availability, effective table
  source/count/freshness, evidence level, observable rate, mean confidence,
  current table count, last-observed table count/freshness, peak table count,
  required current/effective/last-observed/peak canonical table-person IDs, and
  exact current/effective/last-observed/peak canonical table-person ID sets via
  `expected_*_canonical_table_ids`, plus required or forbidden quality flags.
- `operator_snapshot_expectations`: expected timestamped operator status
  snapshots for the combined question "what stage is underway, and who is at the
  table?" Labels can use `timestamp_s` / `at_s` with `tolerance_s`, or a
  `start_s` / `end_s` window. They support the same stage, view, evidence,
  table-count, canonical table-person ID, and quality-flag checks as
  `procedure_status_expectations`, with `stage` and `stage_evidence_status`
  accepted as shorthand for current status fields.
- `operator_packet_expectations`: expected operator handover packet rows,
  including stage/current-vs-prior status, stage evidence status, next stage,
  handoff type, evidence level, lead role, active/canonical/effective table
  counts, continued/new/dropped table identities, tracking and observable
  rates, mean confidence, effective table source, required active/effective
  canonical table IDs, exact active/effective canonical table ID sets via
  `expected_active_canonical_table_ids` and
  `expected_effective_canonical_table_ids`, required or forbidden quality flags,
  and required or forbidden packet text fragments.
- `event_timeline_expectations`: expected operator timeline events for stage
  starts, view changes, table handoffs, and table peaks. Expectations can
  constrain event type, stage, view, handoff type, timing, tracking
  availability, table count, matching role, and required canonical table-person
  IDs via `required_table_canonical_ids`.
- `table_team_expectations`: expected table-team rows, such as requiring no
  tracks in fluoroscopy-only clips, requiring a `recent_last_observed` row from
  the last room-view roster, requiring an `active_current` row in a live room
  view, or requiring historical peak-table operators. Expectations can constrain
  status, raw dominant role, operator-facing `table_team_role`, dominant stage,
  minimum/maximum matching tracks, observed table frames, table-presence ratio,
  last-seen age from clip end, interval count, and current/effective/last/peak
  roster membership.
- `table_identity_group_expectations`: expected canonical table-person groups
  after raw track stitching, such as requiring zero groups in fluoroscopy-only
  clips, requiring a fixed number of canonical table people in a room-visible
  stage, or requiring fragmented raw IDs to merge into one auditable group.
  Expectations can constrain operator-facing role, raw dominant role, canonical
  group ID, representative raw track ID, merged raw track IDs, observed table
  frames, stage-specific frames, first/last seen timing, and minimum/maximum
  group counts. Use `required_merged_track_ids` to require a subset of raw
  fragments, and `expected_merged_track_ids` when an over-merge should fail the
  curated fixture.
- `event_timeline_expectations`: expected chronological review events, such as
  requiring a room-view return at deployment, a closure-stage roster-added event,
  a table peak, or a non-room event with zero table count. Expectations can
  constrain event type, stage, view, handoff type, timestamp window,
  tracking-available flag, minimum/maximum table count, operator-facing role,
  raw dominant role, and minimum matching roster tracks.
- `roster_snapshot_expectations`: expected current, last-observed, or peak
  roster snapshots, such as requiring at least one table-operator track in the
  last-observed room-view table roster. Use `expected_canonical_table_ids` when
  the label should fail on extra invented table people rather than only proving
  that required people were present.
- `quality_flag_expectations`: expected quality flags, such as requiring
  `non_room_view` and `low_stage_confidence` to cover a fluoroscopy-only ROI.

Labels are deliberately lightweight JSON so they can be hand-authored from
public clips, broadcast timestamps, or future labelled theatre footage.

## Multi-Clip Suite

Use the manifest runner to score several clips with one command:

```bash
python evaluate_tavr_suite.py docs/evaluation/tavr_suite.json --output-dir outputs/tavr_suite_person_status_verify
```

The default suite is manifest-driven rather than shell-string-driven. Each case
declares a clip path, label path, ROI, starting stage, frame limit, optional
`source_start_s` for pre-cut case-clock metadata, and tracking configuration.
Cases can set `"static_table_fallback": true` in their `config` object for
opt-in low-motion room-view review. The runner writes per-case JSON plus
`outputs/tavr_suite_person_status_verify/suite_summary.json`. It also exports the derived TAVR
summary tables as per-case CSV files, including view segments, procedure
status summaries, table-team summaries, procedure milestones, stage staffing,
operator status snapshots, operator stage packets, stage table coverage, stage
handoff summaries, stage roster summaries, stage evidence summaries,
procedure event timelines, table roster snapshots, table transition events,
table identity groups, table presence intervals, quality flags, and
low-confidence segments. The
command exits non-zero if any scored label section falls below its configured
threshold, including `operator_packet_pass_rate`,
`table_person_interval_pass_rate`, `table_person_status_pass_rate`,
`table_identity_group_pass_rate`, and `table_transition_pass_rate` when those
expectations are labelled.

The default suite keeps static fallback off as a conservative baseline. Run the
opt-in fallback fixture separately when refining low-motion room-view tracking:

```bash
python evaluate_tavr_suite.py docs/evaluation/tavr_static_table_fallback_suite.json --output-dir outputs/tavr_static_person_status_verify
```

Run the deterministic full-workflow suite when you need a compact regression
that covers every canonical stage, table handoff, canonical table-presence
interval, canonical table identity, operator packet, roster snapshot, and
rapid-progression quality flag:

```bash
# Optional when changing the fixture generator; the MP4 is committed.
python download_sample.py --tavr-fixture --output samples/synthetic_tavr_sample.mp4
python evaluate_tavr_suite.py docs/evaluation/tavr_synthetic_suite.json --output-dir outputs/tavr_synthetic_person_status_verify
```

## Public Replay Artifacts

The Vercel static demo can replay compact backend artifacts without shipping the
full source videos. After refreshing `outputs/tavr_suite_person_status_verify`,
`outputs/tavr_static_person_status_verify`, and
`outputs/tavr_synthetic_person_status_verify`, export the public JSON bundle
with:

```bash
python3 export_public_demo_data.py
python3 export_public_demo_data.py --check
```

The selector in `public/app.js` currently covers the 900s weak-support access
window, the 1800s deployment/table-hold window, the 2400s fluoroscopy-held
context window, the 2700s closure weak-support window, the opt-in 900s
static-fallback review artifact, and the synthetic full TAVR workflow with all
eight canonical stages. This lets the online prototype show both positive
table-roster evidence and honest weak/held/non-room cases.

The current local Sentara suite covers:

- `sentara_900_room_to_fluoro_low_motion`: short room-view stretch with sparse
  motion evidence followed by fluoroscopy, proving the system flags likely
  undercount instead of inventing table staff, and event-timeline labels the
  room-to-non-room view transition. Stage-evidence labels keep the whole slice
  weak because most frames are non-room and low-confidence. The app's opt-in
  static table fallback can be used for manual low-motion review, but the
  default suite keeps this case conservative unless static staff are visually
  proven.
- `sentara_900_static_table_fallback`: the opt-in version of the same slice,
  proving static fallback can recover the three-person table roster before the
  fluoroscopy switch while keeping the procedure stage held at
  `access_sheathing`. Static table silhouettes are roster evidence, not
  procedure-stage evidence.
- `sentara_1800_mixed_room`: fluoroscopy-to-room transition with table-side
  roster expectations once the room view returns, plus room-view denominator
  checks for the deployment-stage staffing summary, a deployment-stage
  `table_roster_started` handoff expectation, and a stage-roster expectation
  that proves the deployment stage has a table-operator lead, strong visual
  support, peak table count of 3, and at least eight canonical table identities.
  Table-transition labels verify repeated table-operator entries and exits
  during deployment. Event-timeline labels also verify the room-view return,
  table roster start, and deployment table peak. Stage evidence labels
  distinguish held non-room delivery-positioning context from strong
  room-visible deployment evidence. Identity-group labels verify ten canonical
  table people in deployment, seven table-operator groups, and a fragmented
  lead table-operator group whose raw IDs merge into one auditable identity.
- `sentara_2400_fluoro_negative`: fluoroscopy-only ROI that should produce no
  table staff, should be flagged `non_room_view`, and should emit non-room
  timeline events with zero table count, zero table-transition events, and zero
  canonical table-person groups. Stage evidence and stage-roster labels should
  remain `held_non_room` / no-table-evidence.
- `sentara_2700_room_post`: post-deployment / closure room-view segment with
  stage, table count, presence, staffing, room-view occupancy, quality, and
  post-deploy-to-closure handoff expectations. Event-timeline labels verify the
  closure stage start, closure roster addition, table peak, and later non-room
  transition. Table-transition labels verify post-deploy presence-at-end plus
  closure table entries and exits. Stage-roster labels verify the closure roster
  addition with continued and new table-side tracks. Identity-group labels
  verify nine canonical table people in the closure segment and preserve the
  long-running post-deploy table operator as one auditable table-person group.
  Human-labelled table-person windows verify the crowded closure peak and the
  late room-view table hold, and status-roster labels verify both the peak
  current/effective/last/peak roster and the final non-room last-observed table
  answer. Stage-evidence labels keep both post-deploy and closure stages weak
  because the visual confidence is low and closure is partly non-room.

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
