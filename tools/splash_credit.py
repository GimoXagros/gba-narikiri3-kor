"""Preserve the consent prompt and clear its lower credits as requested."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def install(legacy):
    p=json.loads((ROOT/'source/splash_credit.json').read_text(encoding='utf8'))
    base=int(p['bitmap_offset'],0)
    if hashlib.sha256(legacy[base:base+240*160*2]).hexdigest()!=p['bitmap_sha256']:raise ValueError('Splash source bitmap differs')
    if hashlib.sha256(legacy[0xfce200:0xfce284]).hexdigest()!=p['boot_sha256']:raise ValueError('Splash DMA/input code differs')
    # User superseded the previous credit addition: clear everything below
    # the consent prompt. Its final ink row is 89; y90..109 was already blank.
    cut=100
    return [(base+cut*480,bytes((160-cut)*480),'splash-remove-lower-credits')],{
        'text':'','rectangle':[0,cut,240,160-cut],
        'original_credits_preserved':False,'consent_prompt_preserved':True,
        'boot_code_unchanged':True}
