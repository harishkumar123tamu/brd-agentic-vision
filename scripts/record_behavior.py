"""Append only genuinely observed 1-minute cow behavior labels.

From repo root, use:
  py -3.12 scripts/record_behavior.py --clip Event20261107144004003.Avi --camera cam03 --cow C01 --night 0

Watch the actual video for each minute. This script does NOT label automatically.
"""
import argparse
import csv
from pathlib import Path

FIELDS = ['clip_file','camera','sec_start','sec_end','cow_id','behavior','is_night','confidence','notes']
CLASSES = ['lying','standing','walking','feeding','drinking','ruminating_lying',
           'ruminating_standing','grooming','social_interaction','other_not_visible']

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clip', required=True, help='Actual original clip filename')
    p.add_argument('--camera', required=True, choices=('cam01','cam02','cam03'))
    p.add_argument('--cow', required=True, choices=[f'C{i:02d}' for i in range(1,11)])
    p.add_argument('--night', type=int, required=True, choices=(0,1))
    p.add_argument('--out', type=Path, default=Path('ground_truth/behavior_labels.csv'))
    a = p.parse_args()
    if not a.clip.lower().endswith('.avi'):
        p.error('clip must be the original .Avi filename to preserve its time reference')
    if a.out.exists():
        with a.out.open(encoding='utf-8-sig',newline='') as f:
            r=csv.reader(f); actual=next(r,None)
        if actual!=FIELDS:
            raise SystemExit(f'Stop: {a.out} has columns {actual}, expected {FIELDS}')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    print('Watch each actual one-minute interval before recording it. Press Enter on start to quit.')
    print('Behavior options:',', '.join(CLASSES))
    while True:
        raw=input('Start second in source clip [0, 60, 120, 180, 240]: ').strip()
        if not raw:break
        try: start=int(raw)
        except ValueError:
            print('Enter an integer.');continue
        if start not in (0,60,120,180,240):
            print('Use one of 0,60,120,180,240; clips generally run for five minutes.');continue
        behavior=input('Observed behavior (exact spelling): ').strip().lower()
        if behavior not in CLASSES:
            print('Not a recognized label; nothing saved.');continue
        confidence=input('Confidence [high, medium, low]: ').strip().lower()
        if confidence not in ('high','medium','low'):
            print('Invalid confidence; nothing saved.');continue
        notes=input('Observed detail / ambiguity (optional): ').strip()
        row=[a.clip,a.camera,start,start+60,a.cow,behavior,a.night,confidence,notes]
        with a.out.open('a',encoding='utf-8',newline='') as f:
            w=csv.writer(f)
            if f.tell()==0:w.writerow(FIELDS)
            w.writerow(row)
        print('Saved one genuinely reviewed cow-minute:',a.cow, start,behavior)

if __name__=='__main__':main()
