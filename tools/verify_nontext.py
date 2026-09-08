"""Require the adopted PCM sample region to remain byte-identical."""
import argparse,hashlib,json
from pathlib import Path
from nontext_contract import protected_regions
p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
r=a.rom.read_bytes()
out={'status':'PROTECTED_NON_TEXT_IDENTICAL','rom_sha256':hashlib.sha256(r).hexdigest(),'regions':protected_regions(r),'scope':'Identified PCM sample bank; does not classify all ROM data or establish translation completion'}
a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out))
