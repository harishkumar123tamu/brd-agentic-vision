# Pen 6: Cattle Behavior Tracking and BRD Risk Monitoring

Merck TAMU Animal Science Hackathon, November 2026  
Team: Harish, Suhas and Srikant

## Background and objective

Accurate monitoring of individual cattle behavior is important when evaluating cattle health, however continuously following individual animals in a group has remained a challenge. Our dataset contains ten black Angus cattle in Pen 6, recorded by three cameras over two days. Since the cattle look similar, relying only on appearance could cause incorrect identities, especially during nighttime infrared recordings or when one animal obstructs another.

To address this, we used computer vision to detect cattle, maintain individual identities and organize behavior information by cow and time. The main behaviors of interest were feeding, lying, rumination and movement. Changes in these behaviors may help identify animals that require closer observation, but they cannot independently confirm bovine respiratory disease (BRD).

## Approach

Harish processed the video recordings on the computing cluster using YOLO11m for detection. The recordings required an explicit HEVC decoder setting because of the nonstandard video tag. The detected boxes were cleaned to remove duplicates and cattle outside the target pen. The identity pipeline used Camera 03 as its main reference for C01 to C10 and linked observations from Cameras 01 and 02 when cattle approached the feeding bunk. The system relied on position and movement continuity because appearance alone was not reliable for these cattle.

Suhas's behavior pipeline was planned to use tracking information and camera zones for minute-level feeding, drinking, movement and posture estimates. Difficult cases such as rumination, grooming, nighttime visibility and uncertain identities were intended for additional vision language model review. The workflow is:

`Recorded video -> Cow detection -> Tracking and identities -> Cow-minute behavior -> Daily features -> Risk ranking -> Video review`

My work focused on manual detection labels, camera mapping, pen masks, preliminary floor landmarks, the risk scoring code and a Streamlit dashboard. I labeled 60 frames containing 367 cow boxes. The risk code was designed to accept the team activity file, while simulated activity was used initially to test the output and dashboard before real behavior data was available.

## Results available at the last update

According to the team status report dated November 14, the dataset consisted of 1,749 clips totaling approximately 153 GB. Harish processed around 264,000 keyframes using YOLO11m. His report described ten identity streams on Camera 03, a 99.1% continuous matching rate and assigned identities for around 92% and 93% of feeding-bunk detections on Cameras 01 and 02. These numbers describe tracking coverage and continuity, not independently verified identity accuracy. Review of possible ID swaps was still in progress at that time.

The pen masks have been saved for all three cameras. Four preliminary floor-point pairs were recorded for Camera 01 and four for Camera 03. Four Camera 02 candidate pairs remain unverified because several physical boundaries are not clearly visible. These points should not be considered a verified geometric calibration.

The BRD scoring script and Streamlit dashboard have been tested using simulated activity data. The resulting cow ranking is a demonstration of the software and **is not a measurement from the ten recorded cattle**. Verified behavior accuracy, real risk ranking and video evidence cannot be reported until the corresponding team outputs and original clips have been checked.

## Risk score and interpretation

The planned features include daily feeding minutes, feeding visits, lying minutes, rumination, activity and changes between the two days. The guide assigns 30% to feeding, 15% to feeding visits, 20% to lying, 15% to rumination, 10% to isolation and 10% to change between days. Reliable isolation estimates require usable floor-position tracking. When those positions are missing, the scoring implementation omits isolation and rescales the available weights.

Each cow is compared with the rest of the herd on the same day and, when possible, with its own earlier observations. The output is a relative score between 0 and 1 for prioritizing video review. It is not a probability of BRD, and a higher score alone should not be reported as a sick animal.

## Limitations and next steps

The dataset includes only ten cattle and two days without veterinary-confirmed BRD outcomes. Occlusion, infrared recordings, fisheye lenses and possible ID swaps can affect the results. The manually reviewed behavior labels and C01 to C10 identity reference need to be completed using genuine video observations. Risk cards for the highest-ranked animals also require real clips and a distinction between what was seen directly and what was estimated by the system.

With additional data, the system could be tested across more pens, longer periods and animals with confirmed clinical outcomes. Those records would make it possible to evaluate whether the monitoring results provide consistent information for actual health decisions.

*Source of reported numbers: Team Status & Remaining Tasks, November 14, 2026, 11:45 PM CST. The final report should be updated if the team's subsequent runs differ.*
