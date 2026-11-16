# BRD Agentic Vision

A computer vision prototype that tracks individual cattle, monitors their behavior, and identifies changes that may warrant closer observation for bovine respiratory disease (BRD).

Built for the **Merck–TAMU Animal Science Hackathon 2026**.

**Team:** Harish, Suhas, Srikant

## What it does

Monitoring individual cattle in a group is challenging, especially when animals look similar. Our dataset includes ten black Angus cattle in Pen 6, recorded using three cameras over two days.

The system aims to maintain cow identities (C01–C10), estimate activities such as feeding, drinking, lying, and walking, and compare behavior across cows and days. It then ranks cattle for further observation using a relative behavioral risk score.

**The score is not a BRD diagnosis or a calibrated probability of disease.** No veterinary-confirmed disease outcomes were available to validate BRD prediction.

## How it works

- **Cow detection:** YOLO11m identifies cattle in video frames. Processing removes duplicate detections and detections outside the selected pen.
- **Individual tracking:** Camera 03 is the primary source for maintaining cow IDs C01–C10. Cameras 01 and 02 provide additional feeding-bunk observations linked to those identities.
- **Camera zones:** Pen boundaries, feeding-bunk areas, and water areas support behavior estimation and help exclude cattle in neighboring pens.
- **Behavior monitoring:** The pipeline produces video-derived activity intervals, including feeding, drinking, lying, walking, and other observed behavior. Subtle behaviors such as rumination still require reliable labeling and verification.
- **Risk scoring:** Daily behavioral features are compared with herd patterns and, where supported by the data, each cow's previous-day activity.
- **Dashboard and evidence:** A Streamlit dashboard displays the results. Separate risk cards summarize the three highest-ranked cows and reference supporting video clips.

For the detection, tracking, and cluster execution workflow, see [PIPELINE.md](PIPELINE.md).

## Final real-data results

The current scoring run uses **6,007 video-derived activity intervals** in `outputs/activity.csv`, covering **10 cattle across two days**. The provenance file `level2/risk_source.json` identifies this input as **real**, not simulated. These are model/pipeline-derived observations, not independently verified manual behavior labels.

| Rank | Cow ID | Relative risk score |
| --- | --- | ---: |
| 1 | C02 | 0.6619 |
| 2 | C03 | 0.6410 |
| 3 | C08 | 0.6101 |

The scores are **relative watch-list heuristics**, not disease probabilities. A higher score suggests that a cow may merit closer observation; it does not establish that the animal has BRD.

**Output files:**

- `level2/brd_risk.csv`: per-cow ranking and scores.
- `level2/features.csv`: derived behavioral features.
- `level2/risk_source.json`: data source and coverage information.
- `docs/risk_card_C02.md`, `docs/risk_card_C03.md`, `docs/risk_card_C08.md`: the three risk cards.
- `docs/clips/index.csv`: index of nine referenced evidence clips. Access to underlying footage depends on the team's private video storage; clip references are not independent clinical confirmation.

**Rumination and isolation could not be assessed from the available final scoring inputs.** In particular, isolation was unavailable without suitable location tracks. Do not interpret the original proposed feature weights as the exact formula used for this real-data run; the implemented logic is in `level2/build_risk_real.py`.

## Run it yourself

### 1. Clone the repository

```powershell
git clone https://github.com/harishkumar123tamu/brd-agentic-vision.git
cd brd-agentic-vision
```

### 2. Install the local dependencies

The local dashboard and scoring workflow uses Python 3.12:

```powershell
py -3.12 -m pip install pandas numpy opencv-python pyarrow streamlit plotly
```

FFmpeg is also needed for video processing. Some source recordings have a nonstandard video-stream layout and may require explicit stream selection. Detection and tracking are intended for the team's cluster/SLURM environment; see `PIPELINE.md` for the available pipeline instructions and confirm cluster-specific paths with the team.

### 3. Build scores from the real activity data

With `outputs/activity.csv` available, run:

```powershell
py -3.12 level2/build_risk_real.py --activity outputs/activity.csv --source real
```

This generates the relative risk outputs in `level2/`. The repository also contains `level2/build_risk.py` for a **separate simulated-data demonstration**; simulated results must not be presented as real cattle observations.

### 4. Open the dashboard

```powershell
py -3.12 -m streamlit run dashboard/app_srikant.py
```

Open the local URL shown in the terminal. Use the real-data outputs above to display the final rankings.

## Progress and validation status

The team status report from **November 14, 2026** described approximately 1,749 video clips (153 GB), roughly 264,000 processed keyframes, and tracking of ten identities on Camera 03. It reported 99.1% tracking continuity and identity assignment for approximately 92% and 93% of feeding-bunk detections on Cameras 01 and 02. **Those are team-reported tracking/coverage measures, not independently measured cow-ID accuracy.**

Ground-truth preparation included **60 manually annotated detection frames with 367 cattle bounding boxes**, pen zone definitions for all three cameras, and preliminary floor-reference points. The C01–C10 reference sheet contains tentative observations rather than fully verified cross-day identities.

The current prototype has real activity-derived risk rankings and three evidence-linked risk cards, but the following validation work remains incomplete:

- **Manual behavior validation:** 0 of the targeted 200–300 independently labeled cow-minutes were completed at the last recorded status.
- **Cow identification validation:** The ten cow IDs have not been independently verified end-to-end across days and cameras.
- **Clinical validation:** No veterinary-confirmed BRD labels were available for measuring disease prediction accuracy. Clinical signs in referenced clips have not been independently verified.

Consequently, **no manually verified behavior accuracy, cow-ID accuracy, or clinical BRD prediction accuracy is claimed**. See [docs/final_validation_status.md](docs/final_validation_status.md) for the latest documented status. If the team completes validation, that document and this section should be updated.

## Challenges

- **Similar-looking cattle:** Individual recognition is difficult because the animals are all black Angus; tracking relies heavily on movement and position continuity.
- **Camera visibility:** Occlusion, animals leaving the field of view, and nighttime infrared footage affect tracking and behavior estimation.
- **Video processing:** The source recordings require care when decoding their video streams.
- **Calibration:** Some shared physical landmarks and floor-coordinate references remain preliminary.
- **Behavior verification:** Visible activities can be estimated from video, but subtle behavior and clinical signs require additional manual review.

## Project files

- [`pipeline/`](pipeline/): cattle detection, tracking, cow identification, and cross-camera linking.
- [`pipeline/zones.json`](pipeline/zones.json): pen, feeding-bunk, and water zones used by the detection pipeline.
- [`outputs/activity.csv`](outputs/activity.csv): video-derived behavior intervals used for final scoring.
- [`ground_truth/`](ground_truth/): detection annotations, zone references, calibration, and preliminary cow ID information.
- [`level2/`](level2/): feature extraction, risk scoring, and real-data outputs.
- [`dashboard/app_srikant.py`](dashboard/app_srikant.py): Streamlit dashboard used for the final real-data view.
- [`docs/`](docs/): technical brief, risk cards, clip index, and validation status.
- [`scripts/`](scripts/): supporting annotation and validation utilities.
- [`PIPELINE.md`](PIPELINE.md): agent/pipeline documentation supplied by the team.
- `data_local/`: private source recordings and local files excluded from GitHub.

## Built with

Python 3.12, YOLO11m, OpenCV, FFmpeg, Pandas, NumPy, PyArrow, Streamlit, and SLURM for cluster execution.

The team also considered Qwen2.5-VL-7B for difficult behavior observations; its final deployment status is not verified here. ChatGPT and Claude were used to assist with development, debugging, and documentation. Results should be checked against project outputs and original recordings.

## Data privacy

Original video footage and extracted private frames are kept outside the public code repository. Do not upload source videos, sensitive images, or private local files to GitHub. Derived outputs and annotations should be shared only according to the team's data permissions.

This project is a **behavior-monitoring and relative risk-ranking prototype**, not a substitute for animal-health assessment or veterinary diagnosis.
