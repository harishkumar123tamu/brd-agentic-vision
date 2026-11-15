
# BRD Agentic Vision

A computer vision system that tracks individual cattle, monitors their behavior, and identifies changes that could indicate early signs of bovine respiratory disease (BRD).

Built at the Merck TAMU Animal Science Hackathon 2026.

**Team:** Srikant, Harish, Suhas

## What it does

Monitoring individual cattle in a group has remained a challenge, especially when the animals have similar physical appearances. Our dataset included ten black Angus cattle in Pen 6, recorded using three cameras over two days.

The goal of this project was to maintain an individual ID for each cow, track its behavior, and identify changes in feeding, lying, rumination, and movement.

While these behaviors can provide useful information about cattle health, they cannot independently confirm whether an animal has BRD. Our system uses a comparative risk score to identify cattle that may require closer observation.

## How it works

- **Cow Detection:** YOLO11m detects cattle in the video recordings. Duplicate detections and boxes outside the selected pen are removed before tracking.

- **Individual Tracking:** Each animal is assigned an ID from C01 to C10. Camera 03 is used as the main reference, while Cameras 01 and 02 provide additional observations near the feeding bunk.

- **Camera Zones:** Pen boundaries, feeding areas, and water areas are marked to help identify cattle behavior and exclude animals from neighboring pens.

- **Behavior Monitoring:** Tracking information and camera zones are used to estimate feeding, drinking, lying, and walking. More difficult observations, such as rumination and grooming, require further verification.

- **BRD Risk Scoring:** The scoring system compares each animal's behavior with the herd and with its own previous observations.

- **Dashboard:** A Streamlit dashboard displays cow rankings, risk scores, and the behavioral factors contributing to each score.

## Built w/

- Python 3.12
- YOLO11m for cattle detection
- OpenCV for image processing and annotations
- FFmpeg for video decoding
- Pandas and NumPy for data processing
- PyArrow for tracking data
- Streamlit for the dashboard
- SLURM for running processing jobs on the computing cluster

The team also planned to use Qwen2.5-VL-7B for reviewing difficult behavior observations. Its final deployment details need to be confirmed.

## Run it yourself

### 1. Clone the repository

```powershell
git clone https://github.com/harishkumar123tamu/brd-agentic-vision.git
cd brd-agentic-vision
```

### 2. Install dependencies

```powershell
py -3.12 -m pip install pandas numpy opencv-python pyarrow streamlit plotly
```

FFmpeg must also be installed to process the video recordings. Some recordings use HEVC encoding with a nonstandard codec tag and require the decoder to be selected explicitly.

### 3. Run the BRD scoring demonstration

```powershell
py -3.12 level2/build_risk.py
```

This generates risk scores using simulated activity data. The results are only for testing the scoring system and do not represent actual cattle health.

### 4. Open the dashboard

```powershell
py -3.12 -m streamlit run dashboard/app.py
```

Open the local URL displayed in the terminal.

The detection and tracking scripts are located in the `pipeline/` folder, with SLURM scripts for cluster execution. The exact cluster commands and final software versions still need to be documented from the completed runs.

## BRD Risk Scoring

Changes in feeding, lying, rumination, and general activity can provide useful information when evaluating cattle behavior. However, individual animals naturally have different behavior patterns.

To address this, the scoring method compares each cow with the herd and, when possible, with its behavior on the previous day.

The intended scoring weights are:

- Feeding duration: 30%
- Feeding visits: 15%
- Lying duration: 20%
- Rumination: 15%
- Isolation: 10%
- Change between days: 10%

Isolation is excluded when reliable floor-position tracking is unavailable. The actual features and weights used should be checked before interpreting the results.

The score is converted into a value between 0 and 1 and is used to rank cattle for further observation. It is not a probability of BRD.

## Results so far

According to the November 14 team update, the dataset contained 1,749 video clips totaling approximately 153 GB.

Harish's detection pipeline processed approximately 264,000 keyframes using YOLO11m. The tracking system maintained ten cow IDs on Camera 03, with a reported 99.1% continuous matching rate.

The system also assigned cow identities to approximately 92% of feeding-bunk detections on Camera 01 and 93% on Camera 02.

These percentages describe tracking continuity and identification coverage, not independently verified cow ID accuracy.

For ground truth preparation, 60 frames were manually labeled, containing 367 cow bounding boxes. Pen polygons were prepared for all three cameras.

Camera 01 and Camera 03 each contain four preliminary floor-coordinate pairs. Camera 02 has four candidate pairs that have not yet been verified.

The BRD scoring code and Streamlit dashboard have been tested with simulated activity data. Actual cattle risk rankings require the completed behavior records and supporting video evidence.

## Challenges we ran into

- **Similar-looking cattle:** All ten animals are black Angus, making individual identification difficult. We relied more on location and movement continuity instead of appearance alone.

- **Camera Visibility:** Cattle frequently obstruct one another, and some animals move outside the camera view. Nighttime infrared recordings further reduce the visible details.

- **Video Processing:** The recordings use HEVC encoding with a nonstandard codec tag, which required an explicit FFmpeg decoder setting.

- **Camera Calibration:** Not all pen boundaries are visible from every camera, making it difficult to identify matching physical landmarks.

- **Behavior Verification:** Feeding and lying can be estimated from camera observations, but rumination and other subtle behaviors require more detailed review.

## What's next

- Complete the C01 to C10 cow reference sheet using verified ID-check images.
- Validate behavior predictions using manually reviewed video recordings.
- Replace simulated activity data with actual cow behavior records.
- Verify possible cow ID changes during tracking.
- Add real behavior comparisons and video evidence to the dashboard.
- Prepare risk cards for the three highest-ranked cattle using actual observations.
- Evaluate the system using longer recordings and veterinary-confirmed health information.

## Project Files

- `pipeline/`: Cow detection, tracking, identification, and cross-camera linking.
- `pipeline/zones.json`: Pen, feeding bunk, and water zones used by Harish's pipeline.
- `ground_truth/`: Manual annotations, preliminary pen masks, and floor calibration.
- `level2/`: Behavioral feature calculations and BRD risk scoring.
- `dashboard/`: Streamlit risk monitoring dashboard.
- `docs/`: Technical brief and supporting documentation.
- `scripts/`: Supporting annotation and validation tools.
- `data_local/`: Private video recordings and temporary data excluded from GitHub.

## Data Privacy and External Tools

The original cattle videos and extracted frames are stored separately from GitHub because the event data must remain private.

ChatGPT was used for assistance with code development, debugging, and documentation preparation. Final results must be checked against the original recordings and project outputs.

The system is intended for behavior monitoring and further animal observation, not veterinary diagnosis.

