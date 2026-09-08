"""Controller-only settings/strategy regression, usable on all three ROMs.

Captures must be viewed; config comparisons do not prove translation quality.
Read-only snapshots use the actual settings handlers' EWRAM locations.
"""
import argparse,hashlib,json
from pathlib import Path
from runtime_probe import Probe
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--save',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    f=Probe(a.core,a.rom,a.out,a.save);captures=[];checks=[]
    def key(button,wait=60):
        f.execute({'op':'frames','count':1,'buttons':[button]});f.execute({'op':'frames','count':wait})
    def capture(name):captures.append({'name':name,**f.execute({'op':'screenshot','name':name+'.png'})})
    def config():return f.read_memory(0x02002990,16)
    def expect(label,settings):
        actual=config()
        if actual[:3]!=bytes(settings):raise ValueError(f'{label}: settings state differs {actual.hex()}')
        checks.append({'label':label,'frame':f.frame,'settings_hex':actual.hex()})
    try:
        for req in json.loads((ROOT/'qa/traces/reload-menu.json').read_text(encoding='utf-8'))['inputs']:f.execute(req)
        f.execute({'op':'frames','count':660})
        for _ in range(7):key('down',10)
        key('a',120);capture('settings-initial');initial=config();expect('initial',[1,1,2])
        for name,value in [('auto',2),('manual',0),('semi-auto',1)]:
            key('right');capture('control-'+name);expect(name,[value,1,2])
        key('down')
        for name,value in [('slow',2),('fast',0),('normal',1)]:
            key('right');capture('speed-'+name);expect(name,[1,value,2])
        key('down')
        for value in [0,1,2]:
            key('right');capture(f'display-mode-{value+1}');expect(f'mode-{value+1}',[1,1,value])
        key('down');key('a');capture('button-editor')
        key('b');capture('target-button-b')
        for _ in range(4):key('down')
        key('a');capture('buttons-reset')
        key('down');key('a');key('b')
        if config()!=initial:raise ValueError('Settings/bindings did not return to their initial bytes')
        checks.append({'label':'settings-and-bindings-restored','frame':f.frame,'settings_hex':config().hex()})
        for _ in range(3):key('up')
        key('a');capture('strategy-character');key('a',120);capture('strategy-list')
        for _ in range(4):key('down')
        capture('strategy-last-choice');key('a');key('a');capture('strategy-reopened')
        for _ in range(4):key('up')
        key('a');key('b');key('b')
        if f.ram_interventions:raise ValueError('Unexpected RAM intervention')
        report={'status':'SETTINGS_STATE_CHECKS_PASS_VISUAL_INSPECTION_PENDING','rom_sha256':f.rom_hash,'core_sha256':f.dll_hash,'input_save_sha256':f.input_save_hash,'ram_interventions':0,'checks':checks,'captures':captures,'scope':'Existing first-save reload, settings alternatives, button assignment/default reset and strategy popup. No whole-game or battle mechanics claim.'}
        (a.out/'settings-route.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'status':report['status'],'rom_sha256':f.rom_hash,'captures':len(captures),'out':str(a.out)}))
    finally:f.lib.retro_unload_game();f.lib.retro_deinit()
if __name__=='__main__':main()
