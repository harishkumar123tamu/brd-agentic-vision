"""Read-only local audit of Srikant's deliverables (does not invent missing data)."""
import csv
import json
from pathlib import Path
from collections import Counter

ROOT=Path('.')
CAMERAS=['cam01','cam02','cam03']
BEHAVIORS={'lying','standing','walking','feeding','drinking','ruminating_lying','ruminating_standing','grooming','social_interaction','other_not_visible'}

def rows(path):
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    print('== Ground truth ==')
    for file in ['ground_truth/zones.json','pipeline/zones.json','ground_truth/floor_points.json','ground_truth/cam02_candidate_points.json']:
        p=ROOT/file
        if not p.exists():print('MISSING',file);continue
        try:data=json.loads(p.read_text(encoding='utf-8'))
        except Exception as exc:print('BAD JSON',file,exc);continue
        print('EXISTS',file)
        for cam in CAMERAS:
            val=data.get(cam,[])
            if file.endswith('zones.json'):
                print(' ',cam,'pen vertices:',len(val.get('pen',[])),'zones:',list(val.keys()))
            elif file.endswith('floor_points.json'):
                print(' ',cam,'saved pairs:',len(val),'(requires visual verification)')
    labels=sorted((ROOT/'ground_truth/det_labels').glob('*.txt'))
    invalid=0; boxes=0
    for path in labels:
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            try:
                parts=line.split();cls=int(parts[0]);nums=[float(v) for v in parts[1:]]
                assert len(parts)==5 and cls==0 and all(0<=v<=1 for v in nums) and all(v>0 for v in nums[2:])
                boxes+=1
            except Exception:invalid+=1
    print(f'Detection labels: {len(labels)} frame TXT files, {boxes} YOLO boxes, {invalid} bad lines; target 150-200 frames')
    cows=rows(ROOT/'ground_truth/cow_ids.csv')
    print('Cow-ID rows:',len(cows),'verified anchor clips:',sum(bool(r.get('anchor_clip')) and bool(r.get('anchor_second')) for r in cows),'/10')
    obs=rows(ROOT/'ground_truth/behavior_labels.csv')
    total=0; classes=Counter(); invalid_obs=0; nights=0
    for row in obs:
        try:
            start,end=int(row['sec_start']),int(row['sec_end']); assert 0<=start<end<=300
            assert row['behavior'] in BEHAVIORS
            assert row['cow_id'] in [f'C{i:02d}' for i in range(1,11)]
            assert row['camera'] in CAMERAS
            total+=(end-start)/60
            nights+=(str(row.get('is_night','')).strip()=='1')
            classes[row['behavior']]+=1
        except Exception:invalid_obs+=1
    print(f'Behavior labels: {len(obs)} entries, {total:.1f} cow-minutes; {nights} nighttime entries, {invalid_obs} invalid entries; target 200-300 cow-minutes')
    print('Behavior class counts:',dict(classes))
    for path in ['data_local/activity.csv','data_local/tracks.parquet','level2/brd_risk.csv','level2/features.csv','level2/risk_source.json','dashboard/app.py','dashboard/app_srikant.py','docs/technical_brief.md','docs/technical_brief.pdf']:
        p=ROOT/path;print(('FOUND' if p.exists() else 'MISSING'),path)
    meta=ROOT/'level2/risk_source.json'
    if meta.exists():
        try:
            s=json.loads(meta.read_text(encoding='utf-8'))
            print('Risk provenance:', 'SIMULATED' if s.get('is_simulated') else 'REAL-INPUT claimed; verify file and coverage',s.get('activity_file'))
        except Exception as exc:print('Risk metadata unreadable:',exc)
    elif (ROOT/'level2/brd_risk.csv').exists():
        print('Risk provenance UNKNOWN: existing brd_risk.csv may be simulated; do NOT submit as real.')

if __name__=='__main__':main()
