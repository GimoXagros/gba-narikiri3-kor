"""Freeze identified upstream 8x8 Wansung assets as product font sources.

The generated upstream bitmap corpus is required, with a clean checkout at
the pinned commit. The resulting assets are fixed inputs, not runtime guesses.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
from text_codec import hangul_map

COMMIT='897f0e71224d9964a84b888f2596b2bfd7f98def'
def main():
    p=argparse.ArgumentParser();p.add_argument('--checkout',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    head=subprocess.check_output(['git','-C',str(a.checkout),'rev-parse','HEAD'],text=True).strip()
    status=subprocess.check_output(['git','-C',str(a.checkout),'status','--porcelain','--untracked-files=no'],text=True).strip()
    if head!=COMMIT or status:raise ValueError('Wrong or modified upstream checkout')
    glyphs={}
    for c in hangul_map().values():
        h=f'{ord(c):04X}';path=a.checkout/'generator/build/ascii-font'/h[:2]/(h+'.txt')
        rows=[''.join(x for x in row if x in '.#') for row in path.read_text(encoding='utf-8').splitlines()]
        if len(rows)!=8 or any(len(row)!=8 for row in rows) or not any('#' in row for row in rows):raise ValueError(f'Missing/invalid 8x8: {c}')
        glyphs[c]=rows
    a.out.write_text(json.dumps(glyphs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest=dict(source='https://github.com/RanolP/dalmoori-font',commit=COMMIT,license='Apache-2.0',
        glyphs=len(glyphs),asset_sha256=hashlib.sha256(a.out.read_bytes()).hexdigest(),
        transformation='Whitespace removed from upstream generated 8x8 ASCII bitmaps; pixels unchanged.',
        upstream_generation='generator build:debug -> build/ascii-font. Imported pre-existing generated corpus from clean pinned checkout; regenerate via upstream generator to independently reproduce.')
    a.out.with_suffix('.source.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print(json.dumps(manifest))
if __name__=='__main__':main()
