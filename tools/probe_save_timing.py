"""Controlled investigation of a three-frame cross-core save-time difference."""
import argparse,json,struct
from pathlib import Path
from runtime_probe import Probe
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    trace=json.loads((ROOT/'qa/traces/first-save.json').read_text(encoding='utf-8'))['inputs']
    if trace[208]!={'op':'frames','count':1,'buttons':['a']}:raise ValueError('Save-confirm trace identity changed')
    f=Probe(a.core,a.rom,a.out,None)
    try:
        for request in trace[:208]:f.execute(request)
        timer_address=struct.unpack_from('<I',a.rom.read_bytes(),0x8c48)[0]
        before=int.from_bytes(f.read_memory(timer_address,4),'little')
        f.execute({'op':'frames','count':3})
        after=int.from_bytes(f.read_memory(timer_address,4),'little')
        if after-before!=3:raise ValueError(f'Live game timer did not advance by inserted frames: {before} -> {after}')
        for request in trace[208:]:f.execute(request)
        save=f.execute({'op':'save_export','name':'three-frame-delay.sav'})
        same=save['sha256']=='ece2cc96ebbc2323d78c4be88bb5859592fe6c33a7b0683d4654fa80a051132f'
        report={'status':'MATCHES_MGBA_SAVE' if same else 'DIFFERENCE_REMAINS','rom_sha256':f.rom_hash,'core_sha256':f.dll_hash,'injected_input_delay_frames':3,'game_timer_address':hex(timer_address),'timer_before':before,'timer_after':after,'save':save,'ram_interventions':f.ram_interventions}
        (a.out/'timing-causality.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
        if not same:raise ValueError('Delay did not explain the cross-core save difference')
    finally:f.lib.retro_unload_game();f.lib.retro_deinit()

if __name__=='__main__':main()
