"""Compare two independent behavior-label CSVs using exactly matching cow-minute keys.

First labels: ground_truth/behavior_labels.csv
Second labels: ground_truth/behavior_labels_second.csv

The two people must label independently. An empty file is not evidence.
"""
import argparse
import csv
from collections import Counter
from pathlib import Path

KEY=['clip_file','camera','sec_start','sec_end','cow_id']

def read(path):
    if not path.is_file():raise FileNotFoundError(path)
    with path.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    d={}
    for r in rows:
        k=tuple(r.get(c,'').strip() for c in KEY)
        if not all(k):raise ValueError(f'Missing key fields in {path}: {r}')
        if k in d:raise ValueError(f'Duplicate cow-minute key in {path}: {k}')
        d[k]=r.get('behavior','').strip()
    return d

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--first',type=Path,default=Path('ground_truth/behavior_labels.csv'))
    p.add_argument('--second',type=Path,default=Path('ground_truth/behavior_labels_second.csv'))
    a=p.parse_args()
    if not a.second.is_file():
        print('No second-label CSV yet. Independent validation remains pending.')
        return
    x,y=read(a.first),read(a.second)
    common=sorted(x.keys()&y.keys())
    if not common:
        print('No identical cow-minute keys between the two files. Agreement cannot be calculated.')
        return
    agree=sum(x[k]==y[k] for k in common)
    print('Double-labeled minutes:',len(common))
    print(f'Exact agreement: {agree}/{len(common)} = {100*agree/len(common):.1f}%')
    print('Disagreements:')
    for k in common:
        if x[k]!=y[k]:print('  ',k,'first:',x[k],'second:',y[k])
    if len(common)<30:print('The guide target is around 30 independently labeled minutes.')

if __name__=='__main__':main()
