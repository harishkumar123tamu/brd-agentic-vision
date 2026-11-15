"""Read-only checks for Srikant's final submission. Never fills missing facts."""
import csv
import json
from pathlib import Path

ROOT=Path('.')
REQUIRED=['README.md','docs/technical_brief.md','ground_truth/cow_ids.csv',
          'ground_truth/behavior_labels.csv','level2/brd_risk.csv','level2/features.csv']

def read_csv(path):
    if not path.is_file():return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def main():
    for name in REQUIRED:
        print(('PRESENT' if (ROOT/name).is_file() else 'MISSING'),name)
    ids=read_csv(ROOT/'ground_truth/cow_ids.csv')
    verified=[r for r in ids if r.get('anchor_clip','').strip() and r.get('anchor_second','').strip()]
    print('Cows with anchor source:',len(verified),'/10. Check each anchor manually.')
    labels=read_csv(ROOT/'ground_truth/behavior_labels.csv')
    minutes=0
    for r in labels:
        try:minutes+=(int(r['sec_end'])-int(r['sec_start']))/60
        except (ValueError,KeyError):pass
    print(f'Manual behavior: {len(labels)} entries, {minutes:.0f} cow-minutes (target 200-300)')
    risk_meta=ROOT/'level2/risk_source.json'
    if risk_meta.is_file():
        meta=json.loads(risk_meta.read_text(encoding='utf-8'))
        print('Risk input provenance:',meta.get('source_status','unknown'))
        print('Risk input count:',meta.get('cow_count','unknown'),'cows')
        print('Minimum cow-day data coverage:',meta.get('minimum_cow_day_coverage_min','unknown'),'minutes')
    else:
        print('Risk provenance UNKNOWN: do not submit simulated risk numbers as real results.')
    print('Reminder: top-three cards need 2-3 genuine video clips each and clinician-facing limitations.')
    print('Reminder: leave private AVI, MP4, JPG, PNG and evidence clips out of GitHub.')

if __name__=='__main__':main()
