"""Replay a hash-bound, controller-only route and capture selected milestones.

Successful replay is not a visual or whole-game compatibility assertion.
Only ordinary EEPROM input is accepted; guest memory/state edits are absent.
"""
import argparse
import hashlib
import json
from pathlib import Path

from runtime_probe import Probe


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ('core', 'rom', 'save', 'route', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    route = json.loads(args.route.read_text(encoding='utf-8'))
    if sha(args.rom) != route['rom_sha256'] or sha(args.save) != route['input_save_sha256']:
        raise ValueError('Route ROM or ordinary save differs')
    allowed = {'a', 'b', 'start', 'select', 'l', 'r', 'up', 'down', 'left', 'right'}
    frame = 0
    for row in route['steps']:
        request = row['request']
        if set(request) - {'op', 'count', 'buttons'} or request['op'] != 'frames':
            raise ValueError('Route is not controller-only')
        if not 1 <= request['count'] <= 3600 or not set(request.get('buttons', [])) <= allowed:
            raise ValueError('Invalid controller step')
        frame += request['count']
        if frame != row['frame']:
            raise ValueError('Recorded frame sequence differs')
    if frame != route['final_frame']:
        raise ValueError('Route final frame differs')
    captures = {row['frame']: row for row in route['captures']}
    if len(captures) != len(route['captures']) or not set(captures) <= {r['frame'] for r in route['steps']}:
        raise ValueError('Capture frames are ambiguous or absent')
    probe = Probe(args.core, args.rom, args.out, args.save)
    try:
        observed = []
        for row in route['steps']:
            probe.execute(row['request'])
            if probe.frame in captures:
                ref = captures[probe.frame]
                capture = probe.execute({'op': 'screenshot', 'name': ref['name']})
                observed.append({**capture, 'reference_core_sha256': route['reference_core_sha256'],
                                 'reference_png_sha256': ref['sha256'],
                                 'reference_png_bytes_equal': capture['sha256'] == ref['sha256']})
        exported = probe.execute({'op': 'save_export', 'name': 'route-final.sav'})
        if probe.ram_interventions or probe.frame != route['final_frame']:
            raise ValueError('Route intervention or frame mismatch')
        same_core = probe.dll_hash == route['reference_core_sha256']
        exact_images = all(c['reference_png_bytes_equal'] for c in observed)
        exact_save = exported['sha256'] == route['reference_final_save_sha256']
        report = {'status': 'CONTROLLER_REPLAY_COMPLETE_VISUAL_INSPECTION_PENDING',
                  'rom_sha256': probe.rom_hash, 'core_sha256': probe.dll_hash,
                  'core_version': probe.core_version, 'route_sha256': sha(args.route),
                  'input_save_sha256': probe.input_save_hash, 'final_frame': probe.frame,
                  'ram_interventions': 0, 'state_imports': 0, 'captures': observed,
                  'save': exported, 'same_core_as_reference': same_core,
                  'reference_images_byte_identical': exact_images,
                  'reference_save_byte_identical': exact_save,
                  'scope': route['scope']}
        if same_core and not (exact_images and exact_save):
            report['status'] = 'SAME_CORE_REPLAY_MISMATCH'
        (args.out / 'route-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: report[k] for k in ('status', 'core_version', 'final_frame',
              'reference_images_byte_identical', 'reference_save_byte_identical')}))
        if report['status'] == 'SAME_CORE_REPLAY_MISMATCH':
            raise ValueError('Same-core recorded route did not reproduce')
    finally:
        probe.lib.retro_unload_game()
        probe.lib.retro_deinit()


if __name__ == '__main__':
    main()
