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
- Coarse role-zone counts, such as `table_operator`, `access_operator`,
  `imaging`, `device_prep`, and `anesthesia`
- Zone and motion signals used by the heuristic

These values are written to the metrics CSV and shown in Streamlit.

## Visual Signals

The current model uses deterministic room-video heuristics:

- Normalized room zones for table, access site, anesthesia, imaging/C-arm, device
  table, and entry.
- Track IDs from OpenCV motion/contour tracking.
- Table-side membership based on whether tracked centroids are inside table or
  access zones.
- A sequential stage model with minimum dwell time so the estimate progresses
  like a procedure timeline rather than flickering frame by frame.

## Caveats

This is not a clinical decision system. It is a workflow prototype.

Video alone usually cannot identify named staff, distinguish surgeon from
interventional cardiologist, confirm internal catheter position, prove rapid
pacing, or separate balloon valvuloplasty from post-dilation. Those require
extra context such as fluoroscopy feed, hemodynamics, device logs, audio, case
metadata, or supervised labels.

Use the current output as annotation scaffolding and QA instrumentation for test
footage. Treat low-confidence or visually ambiguous stages as review candidates.
