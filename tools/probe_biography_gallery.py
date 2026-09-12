"""Capture all 37 library entries through ordinary buttons using an explicit review save.

This records observations for subsequent source/portrait/visual review, not an
automatic claim that correct screens or natural unlock progression occurred.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from runtime_probe import Probe

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'rom', 'save', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    probe = Probe(a.core, a.rom, a.out, a.save)
    def frames(n, key=None):
        return probe.execute({'op': 'frames', 'count': n, 'buttons': [key] if key else []})
    def key(k, wait=240):
        frames(4, k)
        frames(wait)
    def capture(name):
        return probe.execute({'op': 'screenshot', 'name': name + '.png'})
    try:
        trace = ROOT / 'qa/traces/reload-menu.json'
        steps = json.loads(trace.read_text(encoding='utf-8'))['inputs']
        probe.execute(steps[0])
        boot = capture('boot')
        for step in steps[1:]:
            probe.execute(step)
        for button in ('down', 'a', 'down', 'down', 'a'):
            key(button, 120)
        rows = []
        for i in range(37):
            row = {'index': i, 'selection': capture(f'{i+1:02d}-selection'), 'fields': []}
            for field in range(1, 5):
                key('a')
                row['fields'].append(capture(f'{i+1:02d}-field-{field}'))
            key('a', 120)
            row['return'] = capture(f'{i+1:02d}-return')
            rows.append(row)
            if i != 36:
                key('down', 120)
        key('b', 120)
        exit_capture = capture('exit-info-menu')
        # Contact sheets retain every rendered field, without retyping text.
        sheets = []
        for start in range(0, 37, 6):
            sheet = Image.new('RGB', (720, 640), 'white')
            for local, row in enumerate(rows[start:start+6]):
                tile = Image.new('RGB', (240, 320), 'white')
                ImageDraw.Draw(tile).text((3, 2), str(row['index']+1), fill='black')
                tile.paste(Image.open(row['selection']['path']).crop((0, 0, 240, 112)), (0, 16))
                for field, cap in enumerate(row['fields']):
                    tile.paste(Image.open(cap['path']).crop((0, 112, 240, 160)), (0, 128+48*field))
                sheet.paste(tile, ((local % 3)*240, (local // 3)*320))
            path = a.out / f'sheet-{start+1:02d}-{min(start+6,37):02d}.png'
            sheet.resize((1440,1280), Image.Resampling.NEAREST).save(path)
            sheets.append({'path':str(path.resolve()), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        result = {'status':'CAPTURED_REVIEW_PENDING', **probe.status(), 'boot':boot,
                  'records':rows, 'exit':exit_capture, 'sheets':sheets,
                  'entry_trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),
                  'scope':'Synthetic unlocked EEPROM; ordinary controller inputs only. No live memory/state edits. Natural unlock acquisition and other gameplay are outside this review.'}
        (a.out/'gallery.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'gallery':str(a.out), 'records':len(rows), 'ram_interventions':probe.ram_interventions}))
    finally:
        probe.lib.retro_unload_game()
        probe.lib.retro_deinit()


if __name__ == '__main__':
    main()
