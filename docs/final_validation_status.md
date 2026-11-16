# Final Results and Validation Status

## Pen 6 BRD Monitoring

The pipeline processed real video-derived activity records for 10 Angus cattle across two days. The real-data scoring run used 6,007 activity records from outputs/activity.csv.

## Final Risk Ranking

| Rank | Cow | Risk Score |
|---|---|---|
| 1 | C02 | 0.6619 |
| 2 | C03 | 0.6410 |
| 3 | C08 | 0.6101 |

The scores are relative behavioral risk estimates, not BRD diagnoses or disease probabilities.

## Completed Work

- Cow detection labels and camera-zone mapping
- Level 2 feature extraction and real-data risk scoring
- Streamlit dashboard with real activity data
- Three risk cards with activity comparisons and nine indexed evidence clips
- README and technical brief
- Preliminary cow reference sheet

## Validation Limitations

Manual behavior validation remains incomplete: 0 of the target 200-300 cow-minutes were independently labeled.

The cow reference sheet contains preliminary observations for C01-C10, but cross-day identities have not been independently verified.

Rumination labels and isolation measurements are unavailable in the current activity data. Clinical signs in the evidence clips have not been independently assessed.

Therefore, no manual behavior accuracy, verified identity accuracy or clinical BRD prediction accuracy is claimed.

## Conclusion

The project demonstrates an explainable cattle behavior monitoring and relative risk-ranking system. Flagged cattle should receive closer observation and, when appropriate, veterinary examination.
