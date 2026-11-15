"""Create a short local H264 clip for manual behavior review.

Usage, from the repo root:
 py -3.12 scripts/make_review_clip.py --clip data_local/Event20261107144004003.Avi --start 60

Output stays in data_local/review_clips, which should NOT be committed to GitHub.
"""
import argparse
import subprocess
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clip',required=True,type=Path)
    p.add_argument('--start',type=int,required=True,help='seconds from the original AVI start')
    p.add_argument('--length',type=int,default=60,help='clip length in seconds; default 60')
    p.add_argument('--outdir',type=Path,default=Path('data_local/review_clips'))
    args=p.parse_args()
    if not args.clip.is_file():p.error(f'Video not found: {args.clip}')
    if args.start<0 or not 0<args.length<=300:p.error('start>=0 and 0<length<=300 are required')
    args.outdir.mkdir(parents=True,exist_ok=True)
    out=args.outdir/f'{args.clip.stem}_{args.start:03d}_{args.start+args.length:03d}.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-c:v','hevc',
         '-ss',str(args.start),'-i',str(args.clip),'-t',str(args.length),
         '-an','-vf','scale=1280:-2','-c:v','libx264','-preset','fast','-crf','25',str(out)]
    print('Converting for local review:',args.clip.name,'at seconds',args.start,'-',args.start+args.length)
    subprocess.run(cmd,check=True)
    print('Local private clip:',out)
    print('Do NOT upload video or extracted frames to public GitHub.')

if __name__=='__main__':main()
