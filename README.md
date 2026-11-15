
# BRD Agentic Vision

## Project Overview

This project was developed for the Merck TAMU Animal Science Hackathon 2026. The objective was to monitor individual cattle behavior using video recordings and identify changes that could be associated with bovine respiratory disease (BRD).

The dataset consists of ten black Angus cattle in Pen 6, recorded using three cameras over two days. While computer vision provides an opportunity to monitor cattle continuously, maintaining individual identities becomes difficult when animals have similar physical appearances or when camera visibility is limited.

To address this challenge, our system combines cattle detection, tracking, individual identification and behavior analysis. The behavior information is then used to calculate a comparative BRD risk score for each animal. The score is intended to support further observation and does not provide a veterinary diagnosis.

## Team Contributions

Harish: Video processing, cattle detection, tracking, cow identification and cross-camera linking.

Suhas: Behavior classification, vision language model analysis, agent verification and video evidence.

Srikant: Ground truth annotations, camera mapping, pen boundaries, floor calibration, BRD risk scoring, Streamlit dashboard and documentation.

## System Approach

The pipeline begins with cow detection using YOLO11m. The detected bounding boxes are processed to remove duplicate detections and animals outside the selected pen.

The tracking system maintains ten identities, C01 to C10, primarily using Camera 03. Observations from Cameras 01 and 02 are linked to existing identities when cattle approach the feeding bunk.

Since black Angus cattle have similar physical appearances, the tracking system uses location and movement continuity to maintain identities. This is especially important in nighttime infrared recordings.

The behavior classification component uses tracking information and camera zones to estimate feeding, drinking, walking, lying and other behaviors. Difficult observations are intended for additional review using a vision language model.

The resulting activity information is used to calculate daily behavioral features and compare individual cattle with the herd.

## Repository Structure

- pipeline/: Cow detection, tracking, identification and camera linking.
- ground_truth/: Manual annotations, camera mapping, pen zones and floor calibration.
- level2/: Behavioral features and BRD risk scoring.
- dashboard/: Streamlit visualization.
- docs/: Technical brief and risk-card documentation.
- scripts/: Supporting scripts and validation utilities.
- data_local/: Private video files and temporary data excluded from GitHub.

## Setup

The local environment uses Python 3.12 and FFmpeg.

Install the main dependencies:

```powershell
py -3.12 -m pip install pandas numpy opencv-python pyarrow streamlit plotly
```

The video recordings use HEVC encoding. Some files require FFmpeg to use the HEVC decoder explicitly.

Harish's detection and tracking scripts are designed to run on the computing cluster using SLURM jobs. Cluster paths and job settings must be configured for the available environment.

## Running the Project

The main pipeline includes:

1. pipeline/detect.py for cattle detection.
2. pipeline/clean_track.py for cleaning detections and tracking.
3. pipeline/cow_ids.py for individual cow identification.
4. pipeline/link_bunk.py for linking front-camera observations.
5. pipeline/id_check_frames.py for producing identity verification frames.

Harish's tracking pipeline uses pipeline/zones.json for the pen, feeding bunk and waterer zones. The ground_truth/zones.json file contains the preliminary pen masks.


Corresponding SLURM scripts are available in the pipeline folder. The complete cluster execution commands and final model environment should be verified against Harish's actual runs.

To test the BRD scoring implementation using simulated data:

```powershell
py -3.12 level2/build_risk.py
```

This demonstration produces simulated activity data and should not be interpreted as actual cattle behavior.

A separate script has been prepared for running the risk score with actual activity data. This still needs to be tested using Suhas's final activity.csv before it is included in the reproducible pipeline.

```powershell
py -3.12 level2/build_risk_real.py --activity data_local/activity.csv
```

To open the existing Streamlit dashboard:

```powershell
py -3.12 -m streamlit run dashboard/app.py
```

An additional dashboard implementation is available at dashboard/app_srikant.py.

## BRD Risk Scoring

Changes in feeding duration, feeding visits, lying time, rumination and general activity can provide information about individual cattle behavior.

However, cattle naturally have different behavior patterns. For this reason, the scoring approach compares each animal with the rest of the herd and, where possible, with its own behavior on the previous day.

The intended risk scoring weights are:

- Feeding duration: 30%
- Feeding visits: 15%
- Lying duration: 20%
- Rumination: 15%
- Isolation: 10%
- Change between days: 10%

Isolation cannot be included when reliable floor-position tracking is unavailable. The implemented score must therefore be reviewed to confirm which features and weights were used.

The weighted score is converted to a value between 0 and 1 and used to rank cattle for further observation. It does not represent the probability of an animal having BRD.

## Current Progress

According to the team status update from November 14, 2026, the dataset contained 1,749 video clips totaling approximately 153 GB.

Harish's detection pipeline processed approximately 264,000 keyframes using YOLO11m. The reported tracking results included ten individual cow identities on Camera 03 and identity coverage of approximately 92% and 93% for feeding-bunk detections on Cameras 01 and 02.

These values describe pipeline performance and tracking coverage, not independently verified cow identification accuracy.

For ground truth preparation, 60 frames were manually annotated, containing 367 cow bounding boxes. Pen polygons were saved for all three cameras.

Camera 01 and Camera 03 each contain four preliminary floor-coordinate pairs. Camera 02 has four candidate pairs that remain unverified.

The BRD risk scoring code and Streamlit dashboard were tested using simulated behavioral data. Actual rankings require the completed activity records and supporting video evidence.

## Limitations

The dataset includes only ten cattle over two days. Camera obstruction, nighttime infrared recordings, fisheye distortion and similarities between cattle can affect detection and identification accuracy.

The behavior validation dataset and cow reference sheet require additional manual observations. The final risk cards also require original video evidence.

No veterinary-confirmed BRD outcomes were available to evaluate disease prediction. Therefore, the current system should be considered a behavior monitoring and risk-ranking prototype rather than a diagnostic tool.

## Models and External Tools

The project uses YOLO11m for cattle detection, Python libraries for data processing, FFmpeg for video decoding and Streamlit for visualization.

The team planned to use Qwen2.5-VL-7B for reviewing difficult behavior observations. Its final deployment status, model versions and additional dependencies should be confirmed against the completed pipeline.

ChatGPT was used for assistance with code development, debugging and documentation preparation. Final implementation details and results should be checked against the original project files.

## Data Privacy

The original cattle recordings and extracted video frames are stored separately from the GitHub repository.

Raw videos and images should not be committed to the repository. Only project code, configuration files, annotations and appropriate derived outputs should be included.

## Project Documentation

A draft technical brief has been prepared and is being reviewed before final submission.

The repository includes preliminary ground truth, cow detection labels, tracking code, risk scoring scripts and dashboard implementations.

Final behavioral validation results, actual risk rankings and evidence-backed risk cards should be added when the required observations become available.
