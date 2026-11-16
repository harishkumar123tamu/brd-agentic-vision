# K1 manual behavior review and K2 identity checkpoint

Checkpoint: 2026-11-15. Reviewer: Suhas. Status: completed 11 video annotations, resume at K1_067.

## Completed review

11 cow-minutes have human annotations: 5 standing, 5 lying, and 1 social_interaction. All 11 were reported to play clearly. Nine targets were reported consistently identifiable; K1_115 and K1_133 were only partly identifiable and remain flagged. All C01-C10 identities are tracker hypotheses, not independently verified cross-day identities. No accuracy claim is made.

| Sample | Tracker ID | Dataset minute | Human label | Confidence | Target visibility |
|---|---|---|---|---|---|
| K1_001 | C01 | 2026-11-07 06:25:00 | standing | medium | consistently identifiable |
| K1_031 | C02 | 2026-11-07 02:59:00 | lying | high | consistently identifiable |
| K1_085 | C04 | 2026-11-08 08:48:00 | lying | high | consistently identifiable |
| K1_097 | C05 | 2026-11-07 07:53:00 | social_interaction | medium | consistently identifiable |
| K1_115 | C05 | 2026-11-08 00:28:00 | lying | medium | partly identifiable |
| K1_133 | C06 | 2026-11-08 06:18:00 | lying | high | partly identifiable |
| K1_145 | C07 | 2026-11-07 06:23:00 | standing | high | consistently identifiable |
| K1_175 | C08 | 2026-11-07 00:52:00 | standing | high | consistently identifiable |
| K1_181 | C08 | 2026-11-08 08:45:00 | standing | medium | consistently identifiable |
| K1_193 | C09 | 2026-11-07 06:58:00 | standing | high | consistently identifiable |
| K1_223 | C10 | 2026-11-07 00:46:00 | lying | high | consistently identifiable |

Suhas watched the clips and supplied observations in chat. The assistant recorded the responses and asked clarifying questions; these are human observations with AI-assisted transcription, not a second independent annotator. Predictions were not shown during this review, although the reviewer had prior project context. A second independent review has not been performed.

## Annotation decisions

- K1_031 and K1_085: user wording "sitting" mapped to lying (resting on the ground); original wording retained.
- K1_115: "sitting and sleeping" mapped to lying. Sleeping is an impression, not a confirmed project class; partial visibility flagged.
- K1_133: lying, high confidence, but partial target visibility remains flagged separately.
- K1_175: standing predominates with approximately 5 seconds taking steps/walking. Exact interval timestamps were not supplied; none were invented.
- K1_193: standing with tail movement only.
- K1_097: visible physical tussling for more than half the minute, confirmed by the reviewer; social_interaction is the majority label. Exact intervals unspecified.
- K1_145: target remained idle/standing while neighboring cows tussled. Neighbor activity was not assigned to the target.

## Sampling and extraction

The 240-minute queue is balanced: six samples per cow, day, and clock-defined day/night stratum (seed 20261115). Day/night is a clock proxy (<06:00 or >=19:00 for night), not independently verified illumination. This is not a time-proportional prevalence sample. The first pilot selected one minute per cow/day, alternating periods: 10 daytime and 10 nighttime samples. All pilot footage is Cam03; other cameras are not validated by this batch.

Grace job 20544047 yielded 18 clips and two failed source-coverage checks: K1_079 at 2026-11-07 02:34:15.533333 and K1_127 at 2026-11-07 01:19:10.433333. Whether these are real video gaps or metadata errors remains unresolved. Failed samples remain in the denominator/accounting; no substitutions were made.

Each successful extraction reports 600 frames at 10 fps, 1280x960. HEVC warnings occurred; these counts alone do not prove source fidelity. The human reviewer reported clear playback for the 11 annotated clips. Reduced resolution/frame rate may limit fine behavior assessment. Approximate boxes use nearest tracked detections within 1.05 seconds; a missing box does not establish the cow's absence.

Box coverage among 18 clips: seven full, seven partial, four zero. Review began with full-box clips, then easier partial-box clips, so the completed subset is visibility-biased and must not be presented as representative accuracy. Seven extracted clips remain unreviewed. K1_067 was presented but has no response yet. Two extraction failures remain unresolved.

## Records and integration

`../ground_truth/k1_pilot/annotations.json` records all 20 pilot samples, including pending cases, source clip segments, observations, confidence and identity limitations. `sampling_queue.json` preserves the original 240-sample plan with empty observation fields; it is not the annotation file. Predictions are deliberately not included in this review folder.

Calendar-minute samples may cross AVI boundaries, so source segments are retained rather than falsely representing every observation as a single source clip. This checkpoint does not overwrite ground_truth/behavior_labels.csv or feed the repository's legacy single-clip agreement checker. A later evaluator must align absolute cow-minute keys and handle multi-segment provenance, uncertain identities and exclusions explicitly.

## K2 status

253 of 288 scheduled ID-check images were found: Cam01 Day1 48/48, Day2 47/48; Cam02 Day1 34/48, Day2 28/48; Cam03 both days 48/48. Coverage is not identity accuracy. An AI-assisted look at the Cam03 12:30 images noted a distinctive white facial marking on Day2 tracker C06, but did not establish a Day1 match. No cross-day cow identity has been independently confirmed in this session.

## Remaining work

1. Resume K1_067, then review remaining pilot clips without revealing predictions.
2. Resolve partial/zero-box cases and extraction failures using source and alternate-camera evidence; retain unresolved status when necessary.
3. Complete the planned review sample and obtain a second independent reviewer for overlapping intervals.
4. Build verified day-1/day-2 and cross-camera identity anchors for each cow; investigate possible ID swaps.
5. Only then calculate appropriately qualified agreement/accuracy and confusion matrices. No new metrics or completed K1/K2 claim is warranted at this checkpoint.

Review videos and raw data are excluded from this commit. The existing pipeline outputs and cow-ID reference sheet are unchanged.
