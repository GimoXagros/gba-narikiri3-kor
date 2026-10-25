"""Replay observed normal input, then reload its EEPROM in a fresh process.

Only this opening/menu/save regression is covered. Images require inspection;
successful replay alone is not a claim that a screen was reached or localized.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from runtime_probe import Probe
from save_contract import opening_save

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def timing_reference(rom_hash,core_hash,trace_hash,required=False):
    profile_path=ROOT/'source/opening_timing_profile.json'
    profiles=json.loads(profile_path.read_text(encoding='utf-8'))['records'] if profile_path.exists() else []
    matched=[r for r in profiles if r['rom_sha256']==rom_hash and r['core_sha256']==core_hash and r['trace_sha256']==trace_hash]
    if len(matched)>1:raise ValueError('Ambiguous opening timing reference')
    if required and not matched:raise ValueError('v13a requires an observed exact ROM/core/trace timing reference')
    return matched[0] if matched else None

def phase(a):
    save=a.out.parent/'first-save'/'first-save.sav' if a.phase=='reload' else None
    probe=Probe(a.core,a.rom,a.out,save)
    try:
        prefix='v13a-' if a.trace_set=='v13a' else ''
        trace=ROOT/'qa/traces'/(prefix+('first-save.json' if a.phase=='first-save' else 'reload-menu.json'))
        inputs=json.loads(trace.read_text(encoding='utf-8'))
        reference=None
        if a.trace_set=='v13a':
            if inputs.get('candidate_sha256')!=probe.rom_hash:raise ValueError('v13a trace candidate identity differs')
            reference=timing_reference(probe.rom_hash,probe.dll_hash,sha(ROOT/'qa/traces/v13a-first-save.json'),required=True)
            if a.phase=='reload' and reference.get('reload_trace_sha256')!=sha(trace):raise ValueError('v13a reload trace identity differs')
        for request in inputs['inputs']:probe.execute(request)
        if probe.frame!=inputs['reference_final_frame'] or probe.ram_interventions:raise ValueError('Trace frame or intervention mismatch')
        captures=[probe.execute({'op':'screenshot','name':a.phase+'.png'})]
        exported=None
        save_validation=None
        if a.phase=='first-save':
            exported=probe.execute({'op':'save_export','name':'first-save.sav'})
            if reference is None:reference=timing_reference(probe.rom_hash,probe.dll_hash,sha(trace))
            timing={'reference_timer':reference['saved_timer'],'timer_tolerance':0} if reference else {}
            save_validation=opening_save((a.out/'first-save.sav').read_bytes(),**timing)
            if reference:save_validation['timing_evidence_sha256']=reference['evidence_sha256']
        elif a.trace_set=='legacy':
            def key(button,count=60):
                probe.execute({'op':'frames','count':1,'buttons':[button]})
                probe.execute({'op':'frames','count':count})
            for _ in range(5):key('down',10)
            key('a');captures.append(probe.execute({'op':'screenshot','name':'items.png'}))
            key('a');captures.append(probe.execute({'op':'screenshot','name':'item-description.png'}))
        result={'status':'REPLAY_AND_SAVE_CHECKS_PASS_VISUAL_INSPECTION_PENDING','phase':a.phase,
                'rom_sha256':probe.rom_hash,'core_sha256':probe.dll_hash,'core_version':probe.core_version,
                'trace_set':a.trace_set,'trace_sha256':sha(trace),'ram_interventions':probe.ram_interventions,
                'input_save_sha256':probe.input_save_hash,'save':exported,'save_validation':save_validation,'captures':captures}
        (a.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        probe.lib.retro_unload_game();probe.lib.retro_deinit()

def main():
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['first-save','reload']);p.add_argument('--trace-set',choices=['legacy','v13a'],default='legacy');a=p.parse_args()
    if a.phase:phase(a);return
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('first-save','reload'):
        subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--phase',name,'--trace-set',a.trace_set,'--core',str(a.core.resolve()),'--rom',str(a.rom.resolve()),'--out',str((a.out/name).resolve())],cwd=ROOT,check=True)
    report={'status':'REPLAY_AND_SAVE_CHECKS_PASS_VISUAL_INSPECTION_PENDING','rom_sha256':sha(a.rom),'core_sha256':sha(a.core),'trace_set':a.trace_set,'separate_process_reload':True,'ram_interventions':0,
            'phases':{name:json.loads((a.out/name/'result.json').read_text(encoding='utf-8')) for name in ('first-save','reload')},
            'scope':('Normal opening to first save; fresh-process reload, main menu, three starting items, description, exit and reentry. Final reload capture is the item description after reentry. ' if a.trace_set=='v13a' else 'Normal opening inputs to first save, fresh-process reload, main menu and three starting items. ')+'No battle, branches, endings, all names, user saves or hardware claim.'}
    (a.out/'runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'rom_sha256':report['rom_sha256'],'report':str(a.out/'runtime.json')}))

if __name__=='__main__':main()
