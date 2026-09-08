"""Observe the original timer at every recorded opening input boundary."""
import argparse,hashlib,json,struct
from pathlib import Path
from runtime_probe import Probe
from verify_default_save_change import decode

def main():
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    trace=Path('qa/traces/first-save.json');requests=json.loads(trace.read_text())['inputs']
    f=Probe(a.core,a.rom,a.out,None);samples=[];rom=a.rom.read_bytes()
    try:
        address=struct.unpack_from('<I',rom,0x8c48)[0]
        if address!=0x03002bc8:raise ValueError('Original saved timer literal differs')
        for index,request in enumerate(requests):
            f.execute(request)
            samples.append({'input_index':index,'frame':f.frame,'timer':int.from_bytes(f.read_memory(address,4),'little')})
            if index==207:f.execute({'op':'screenshot','name':'first-save-confirmation.png'})
        saved=f.execute({'op':'save_export','name':'first-save.sav'});b=decode((a.out/'first-save.sav').read_bytes());timer=struct.unpack_from('<I',b,0x9dc)[0]
        b[12:16]=bytes(4);b[0x9dc:0x9e0]=bytes(4);state=hashlib.sha256(b).hexdigest()
        if state!='439a1bf22c6323169984dc9eb24d393a3dcbf5ba16b32aa9524209c699898e56':raise ValueError('Non-timing opening save state differs')
        f.execute({'op':'screenshot','name':'first-save-finished.png'})
        report={'status':'OBSERVED_OPENING_TIMER_COMPLETE_STATE_IDENTICAL','rom_sha256':f.rom_hash,'core_sha256':f.dll_hash,'trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),'save':saved,'saved_timer':timer,'normalized_state_sha256':state,'samples':samples,'scope':'Read-only timer observation; identical normal input; complete saved state excluding checksum/time is checked. Not an audio or gameplay performance equivalence claim.'}
        (a.out/'timing.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='samples'}))
    finally:f.lib.retro_unload_game();f.lib.retro_deinit()

if __name__=='__main__':main()
