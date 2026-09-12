"""Normal-input cooking menu capture with all 22 recipes in a review save."""
import argparse,json,hashlib
from pathlib import Path
from runtime_probe import Probe
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser()
    for n in ('rom','core','save','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();g=Probe(a.core,a.rom,a.out,a.save);captures=[]
    def key(b):
        g.execute({'op':'frames','count':4,'buttons':[b]})
        g.execute({'op':'frames','count':120})
    try:
        for q in json.loads((ROOT/'qa/traces/reload-menu.json').read_text())['inputs']:g.execute(q)
        for b in ['down','a','up','a']:key(b)
        for i in range(22):
            captures.append(g.execute({'op':'screenshot','name':f'recipe-{i:02}.png'}))
            if i<21:key('down')
        key('b');captures.append(g.execute({'op':'screenshot','name':'return-category.png'}))
        r={'status':'CAPTURED_REVIEW_PENDING',**g.status(),'captures':captures,'scope':'Synthetic all-unlock save; ordinary buttons only. Recipe description/effect/ingredient display and menu return, not cooking success or natural acquisition.'}
        (a.out/'runtime.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'rom_sha256':g.rom_hash,'captures':len(captures),'ram_interventions':g.ram_interventions}))
    finally:g.lib.retro_unload_game();g.lib.retro_deinit()
if __name__=='__main__':main()
