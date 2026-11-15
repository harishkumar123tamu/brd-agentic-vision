"""Create honest draft markdown cards for top 3 cows from features + risk.

EXAMPLES (from the team repo root):
 py -3.12 scripts/generate_risk_cards.py --mode demo
 py -3.12 scripts/generate_risk_cards.py --mode real

For real mode, first regenerate brd_risk.csv/features.csv from REAL activity.
Cards always require human review and video evidence placeholders.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd

METRICS = [
    ('feed_min', 'Feeding time (min)'),
    ('feed_visits', 'Feeding visits'),
    ('lying_min', 'Lying time (min)'),
    ('rumination_min', 'Rumination time (min)'),
    ('isolation_map_units', 'Isolation (pen-map units)'),
]

def number(df, cow, day, metric):
    r = df[(df.cow_id == cow) & (df.day == day)]
    if r.empty or metric not in r.columns or pd.isna(r.iloc[0][metric]):
        return 'N/A'
    return f'{r.iloc[0][metric]:.1f}'

def median(df, day, metric):
    r = df[df.day == day]
    if r.empty or metric not in r.columns:
        return 'N/A'
    values = pd.to_numeric(r[metric], errors='coerce')
    if not values.notna().any():
        return 'N/A'
    v = values.median()
    return f'{v:.1f}' if pd.notna(v) else 'N/A'

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=['demo','real'], required=True)
    ap.add_argument('--features', type=Path, default=Path('level2/features.csv'))
    ap.add_argument('--risk', type=Path, default=Path('level2/brd_risk.csv'))
    args = ap.parse_args()
    if args.mode == 'real' and not Path('data_local/activity.csv').exists():
        raise SystemExit('Real activity.csv is missing. Obtain actual team activity data first.')
    provenance = args.risk.parent / 'risk_source.json'
    if not provenance.exists():
        raise SystemExit('Missing risk_source.json. First rerun build_risk.py with this completion kit.')
    meta = json.loads(provenance.read_text(encoding='utf-8'))
    if args.mode == 'demo' and meta.get('source_status') != 'demo':
        raise SystemExit('Demo risk cards require --source demo scoring data.')
    if args.mode == 'real' and meta.get('source_status') != 'real':
        raise SystemExit('Real risk cards require a verified real activity file scored with --source real.')
    f, r = pd.read_csv(args.features), pd.read_csv(args.risk)
    required = {'cow_id','day'} | {m for m, _ in METRICS if m != 'isolation_map_units'}
    if not required.issubset(f.columns):
        raise SystemExit('features.csv missing columns: ' + str(sorted(required - set(f.columns))))
    days = sorted(f.day.unique())
    if len(days) < 2:
        raise SystemExit('Two dataset days are required for cards.')
    d1, d2 = days[-2], days[-1]
    outdir = Path('docs/demo_only' if args.mode == 'demo' else 'docs/risk_cards_drafts')
    outdir.mkdir(parents=True, exist_ok=True)
    for _, row in r.sort_values('rank').head(3).iterrows():
        cow = row.cow_id
        table = ['| Feature | Cow day 1 | Herd median day 1 | Cow day 2 | Herd median day 2 |', '|---|---:|---:|---:|---:|']
        for metric, label in METRICS:
            table.append(f'| {label} | {number(f,cow,d1,metric)} | {median(f,d1,metric)} | {number(f,cow,d2,metric)} | {median(f,d2,metric)} |')
        banner = '**SIMULATED DATA — DEMO ONLY, NOT A REAL ANIMAL RISK CARD**\n\n' if args.mode=='demo' else '**REAL-ACTIVITY DRAFT — VERIFY ALL EVIDENCE BEFORE SUBMISSION**\n\n'
        content = (f'# BRD watch card — {cow}\n\n{banner}'
                   f'- Rank: {int(row["rank"])}\n- Relative heuristic risk score: {float(row["risk_score"]):.4f} (NOT a probability or diagnosis)\n'
                   f'- Computed reasons: {row["top_reasons"]}\n'
                   f'- Cow identification verified by Harish: [YES / NO / UNKNOWN]\n'
                   f'- Day 1/2 coverage and observed-vs-estimated status: [fill from features.csv]\n\n'
                   '## Cow vs herd\n\n' + '\n'.join(table) + '\n\n'
                   '## Video evidence — fill from Suhas, NEVER invent clips\n'
                   '1. [clip filename, camera, offset seconds, observed behavior]\n'
                   '2. [clip filename, camera, offset seconds, observed behavior]\n'
                   '3. [optional third clip]\n\n'
                   '## Clinical signs (mark seen / not seen / could not tell)\n'
                   '- Drooping ears: could not tell (not reviewed)\n'
                   '- Nasal discharge: could not tell (not reviewed)\n'
                   '- Head low: could not tell (not reviewed)\n'
                   '- Cough posture: could not tell (not reviewed)\n\n'
                   '## Observed versus estimated\n'
                   '- Observed: [actual clip or manually verified activity]\n'
                   '- Estimated: [algorithmic decisions, occlusion or inferred ID]\n\n'
                   '## Recommended follow-up\n'
                   'Closer visual observation and veterinarian-directed assessment only if warranted; not a diagnosis.\n\n'
                   '> Two days and 10 cows are not sufficient to establish clinical BRD. Some or all cows may be healthy.\n')
        outfile = outdir / f'risk_card_{cow}.md'
        outfile.write_text(content, encoding='utf-8')
        print('Wrote', outfile)

if __name__ == '__main__':
    main()
