"""Record ordinary costume-menu selection and changing Julio to swordsman."""
import argparse
import hashlib
import json
from pathlib import Path
from runtime_probe import Probe

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    for n in ('rom','core','save','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--dump-memory',action='store_true')
    a=p.parse_args();f=Probe(a.core,a.rom,a.out,a.save);captures=[]
    def key(k,wait=240):
        f.execute({'op':'frames','count':4,'buttons':[k]})
        f.execute({'op':'frames','count':wait})
    def capture(name):
        c=f.execute({'op':'screenshot','name':name+'.png'})
        ram=f.read_memory(0x02000000,0x20000)+f.read_memory(0x02020000,0x20000)
        c['ewram_sha256']=hashlib.sha256(ram).hexdigest()
        if a.dump_memory:(a.out/(name+'.ewram')).write_bytes(ram)
        captures.append(c)
    try:
        trace=ROOT/'qa/traces/reload-menu.json'
        for req in json.loads(trace.read_text(encoding='utf-8'))['inputs']:f.execute(req)
        capture('main-menu')
        for k in ['down']*6+['a']:key(k,120)
        capture('change-selected')
        for k,name in [('down','confirm-selected'),('up','change-reselected'),('a','character-selection'),
                       ('a','costume-list'),('down','swordsman-selection'),('a','change-confirmation'),
                       ('a','change-applied'),('b','back-from-costumes'),('b','back-to-menu')]:
            key(k);capture(name)
        r={'status':'CAPTURED_REVIEW_PENDING',**f.status(),'captures':captures,
           'trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),
           'scope':'Explicit synthetic review save; ordinary controller inputs, no live RAM/state edits. Selection highlighting and one swordsman costume change; not all costumes or natural acquisition.'}
        (a.out/'runtime.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'rom_sha256':f.rom_hash,'captures':len(captures),'ram_interventions':f.ram_interventions}))
    finally:f.lib.retro_unload_game();f.lib.retro_deinit()


if __name__=='__main__':main()
