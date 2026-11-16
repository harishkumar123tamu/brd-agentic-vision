# Pen 6: Agentic Vision for Angus Behavior and BRD Risk
*Technical brief · Merck–TAMU Animal Science Hackathon 2026 · Team: Harish Kumar Veeraperuma, Suhas, Srikant*

## Objective
Watch a pen of 10 Angus cows around the clock from three cameras, know each cow, label what she does every minute, and rank the cows by early behavioral signs of bovine respiratory disease (BRD): eating less, fewer bunk visits, more lying, less activity and standing apart from the herd.

## Data
1,749 five-minute clips (153 GB): 3 cameras × 2 full days (Nov 7–8), day and infrared night. Matched to the pen map: **Cam 03 = back camera** (whole pen), **Cam 01 = front camera** (from the feed bunk down the pen), **Cam 02 = feed-bunk close-up**. Lenses are fisheye. The video is HEVC with a non-standard codec tag, so every decode forces the HEVC decoder. Keyframes arrive every 2 s; we analyse only keyframes (about 264,000 frames, 30 samples per cow-minute), which is about 15× cheaper than decoding every frame.

## Approach: two layers
**Layer 1 (every frame, fast).** YOLO11m (COCO weights, not fine-tuned) detects cows on every keyframe on the TAMU HPRC cluster (18 parallel GPU jobs, about 1 hour). Hand-drawn pen outlines remove cows in neighbouring pens. Black Angus cows look almost identical, and appearance-based tracking had fragmented in our pilot (22 IDs for 10 cows), so identity is solved as a **closed set**: every frame, Cam 03 boxes are matched to exactly 10 persistent cow "slots" (C01–C10) with the Hungarian algorithm. A hidden cow keeps her last position, and a cow missing for over 30 s can be re-acquired. The recording is continuous through midnight, so IDs carry over from Day 1 to Day 2. Cows at the feed bunk are given the same IDs in Cam 01 and Cam 02 by matching their order along the bunk at the same moment. Rules then label every cow-minute: **feeding** (at the bunk zone, or identified at the bunk by a front camera), **drinking** (at the waterer zone), **walking** (foot-point movement), **lying vs standing** (box height relative to the typical standing height at that image position), and **not visible** when no camera sees her.

**Layer 2 (agentic, only where needed).** A vision-language model (Qwen2.5-VL-7B on one A100) handles uncertain minutes and possible ID swaps. It **plans** which tools it needs (view, zoom, look ±20 s in time, the other camera, zone and neighbour check), **calls** them, **answers** with a behavior and confidence, **checks itself** against the zone geometry and the rule label, and **re-answers** with a new tool, up to 3 rounds. Every run is saved as a trace (`outputs/traces/`).

## Results: Level 1
- **10 IDs, both days:** 561,455 Cam 03 boxes over 84,099 frames; 50–61k boxes per cow (balanced); 99.1% of assignments are smooth continuations; median 7 cows identified per frame. Bunk cows on Cam 01 / Cam 02 receive a Cam 03 ID in 92% / 93% of cases.
- **Behavior for all 28,800 cow-minutes** (`outputs/activity.csv`, 6,007 bouts). **67% of cow-minutes are "observed"** (clear view, continuous ID, consistent label); the rest are marked "estimated". 18% are "not visible".
- **ID risk:** 735 moments where two cows were within one body-height were logged as possible swaps; a sample was checked by the agent.
- **ID-check frames** every 30 min per camera (`outputs/id_check/`). Missing slots, mostly on the bunk close-up at night, are times when no cow was in that view.

**The agent, honestly (the 3 required traces).** In v1, on a cow seen from behind at the bunk, the model claimed "rhythmic jaw movement" (the jaw wasn't visible), ignored the zone check, and overrode a correct *feeding* label with *ruminating*. Across 6 behavior cases, v1 overrode the rules 4 times, always towards rumination: a 7B model on still frames cannot see chewing. We added guard-rails: for feeding minutes it opens the bunk close-up first; its self-check flags "zone says at bunk but answer isn't feeding" and "claims jaw movement without a close-up"; and an unresolved conflict **keeps the rule label and flags it** for review. On the same 8 cases, v2 made 0 unsafe overrides, verified 2, flagged 4, and on the failure case opened the close-up and kept *feeding*. In this setup the agent is most valuable as a **verifier and flagger**, not the primary labeler. Traces: `1_failure` (v1), `2_success` 
(v2 self-check), `3_night`.

## Results: Level 2 (BRD risk)
Per cow and day we compute feeding time and bunk visits, lying time and activity, all **per visible hour** so a cow that is often hidden is not penalised, plus distance to the nearest cow (isolation) and the Day 1 → Day 2 change. Each feature is compared with the herd on the same day; weights were fixed before seeing results, and the weighted sum is squashed to 0–1.

**The same three cows rank highest in both scoring versions:**

| Cow | Main reasons | Score (`level2/`, used on risk cards) | Score (`outputs/`, adds isolation) |
|---|---|---|---|
| **C02** | lowest feeding (≈27% below herd), fewest bunk visits (21 vs ≈27), more lying, low activity | 0.66 (#1) | 0.85 (#1) |
| **C03** | most lying (367 vs 318 min) and rising Day 1 → Day 2 while feeding drops (≈23% below herd) | 0.64 (#2) | 0.77 (#3) |
| **C08** | low feeding (≈16% below herd), low activity, worsening vs her own Day 1 | 0.61 (#3) | 0.81 (#2) |

The `level2/` version uses feeding, visits, lying and activity change. The `outputs/` version also adds isolation and normalises by visible time. Agreement on the top three cows makes the ranking more credible than either score alone. Each top-3 cow has a risk card (`docs/risk_card_C0x.md`) with 3 clips: her longest lying bout, a moment when the herd feeds and she doesn't, and her own bunk visit on the close-up camera. The dashboard (`dashboard/`) shows the ranking, time budgets against the herd, hourly rhythm, ID-check frames and the agent traces.

## What 10 cows × 2 days can and cannot support
It supports a **within-herd comparison** and a picture of the daily rhythm. It does **not** support a diagnosis: there are no clinical records, differences between cows are modest, and some or all cows may be healthy. The score says *look at these cows first*; the suggested action is a pen-rider check and rectal temperature.

## Limitations
No veterinary ground truth. **Behavior accuracy and ID accuracy are not measured** against hand labels: 60 frames (367 cow boxes) were labeled for detection, but the minute-level behavior labels were not completed. Identity is position-based, so two cows lying together can swap unnoticed. "Drinking" means "near the waterer" (over-counted), and lying is under-counted (6–9 h vs typical 10–14 h) because posture comes from box shape. Rumination, grooming and social interaction are not labeled by rules. Feeding and visibility drop for the whole herd on Day 2, which same-day herd comparison controls for. A full pen-floor map failed for the back camera's shallow fisheye view, so cross-camera IDs are limited to the bunk. Level 3 (live alert) was not built.

## With more data and time
Clinical records to validate the score; weeks of video for per-cow baselines; a detector fine-tuned on our day and night labels; ear-tag or RFID anchors for identity; calibrated fisheye cameras for one shared floor map; a 30 fps video model for jaw motion (rumination); and the same pipeline run every 5 minutes on new clips to push alerts with evidence clips to a pen rider.

*Reproduce: `PIPELINE.md` (exact commands, models, versions, run times). AI assistance (Claude) was used for planning, code and drafting; all results were run and checked by the team.*
