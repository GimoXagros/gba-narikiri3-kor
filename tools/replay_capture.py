"""Replay only recorded controller/frame operations on an exact ROM."""
import argparse,json
from pathlib import Path
from runtime_probe import Probe

def main():
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--trace',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    probe=Probe(a.core,a.rom,a.out,None)
    try:
        for line in a.trace.read_text(encoding='utf-8').splitlines():
            request=json.loads(line).get('request',{})
            if request.get('op')=='frames':probe.execute(request)
        result=probe.execute({'op':'screenshot','name':'result.png'})
        probe.execute({'op':'dump','address':'0x06000000','length':98304,'name':'vram.bin'})
        print(json.dumps(result,ensure_ascii=False))
    finally:
        probe.lib.retro_unload_game();probe.lib.retro_deinit()
if __name__=='__main__':main()
