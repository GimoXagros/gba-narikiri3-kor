"""Replay the preserved controller-only first-battle route on a candidate.

Screens must be inspected separately. No successful replay implies visual or
whole-game success; the input EEPROM is read without modifying its source.
"""
import argparse
import hashlib
import json
from pathlib import Path
from runtime_probe import Probe

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser()
    for name in ('core', 'rom', 'save', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--trace', type=Path, default=ROOT/'qa/traces/book-review-first-battle-20260920.jsonl')
    a = p.parse_args()
    trace = a.trace
    steps = [json.loads(line) for line in trace.read_text('utf-8').splitlines()]
    g = Probe(a.core, a.rom, a.out, a.save)
    captures = []
    try:
        for step in steps:
            q = step.get('request',{})
            if not q:
                continue
            if q.get('op') not in ('frames','screenshot'):
                raise ValueError('Trace is not controller/capture only')
            result = g.execute(q)
            if q['op'] == 'screenshot':
                captures.append(result)
        if g.frame != steps[0]['reference_final_frame'] or g.ram_interventions:
            raise ValueError('Recorded route or RAM intervention differs')
        report = {'status':'CONTROLLER_REPLAY_COMPLETE_VISUAL_REVIEW_PENDING',
                  'rom_sha256':g.rom_hash, 'core_sha256':g.dll_hash,
                  'core_version':g.core_version, 'input_save_sha256':g.input_save_hash,
                  'trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),
                  'ram_interventions':g.ram_interventions, 'captures':captures,
                  'scope':'Attempt to reproduce the observed opening-save route to first battle and Select menu. Reachability must be visually confirmed on each core; no later battles, endings, hardware, or audio-quality claim.'}
        (a.out/'runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='captures'}))
    finally:
        g.lib.retro_unload_game();g.lib.retro_deinit()

if __name__ == '__main__':
    main()
