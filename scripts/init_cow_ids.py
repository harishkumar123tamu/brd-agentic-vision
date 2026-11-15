"""Create the required cow reference CSV with empty anchor fields.

Never invent IDs, ear tags, markings, or anchor timestamps. Fill only after reviewing
Harish's ID-check frames. Existing cow_ids.csv is NEVER overwritten.
"""
from pathlib import Path
import csv

OUT=Path('ground_truth/cow_ids.csv')
FIELDS=['cow_id','ear_tag','marks','size','anchor_clip','anchor_second','notes']

if OUT.exists():
    print('Cow reference file already exists, no changes made:',OUT)
else:
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        w.writerow(FIELDS)
        for i in range(1,11):
            w.writerow([f'C{i:02d}', '', '', '', '', '', 'UNVERIFIED - review original ID-check frames'])
    print('Created 10 unverified cow rows:',OUT)
    print('No animals have been verified. Fill evidence fields from actual frames.')
