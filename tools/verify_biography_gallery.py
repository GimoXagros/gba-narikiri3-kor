"""Compare recorded Japanese portraits and two PC cores' complete biography text areas.

Captures require separate visual review. RGB channels are reduced to the GBA's
five meaningful bits to ignore the cores' different 5-to-8-bit expansion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('japanese', 'mgba', 'vba', 'rom', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    paths = [a.japanese/'gallery.json', a.mgba/'gallery.json', a.vba/'gallery.json']
    reports = [json.loads(x.read_text(encoding='utf-8')) for x in paths]
    target = hashlib.sha256(a.rom.read_bytes()).hexdigest()
    if reports[0]['rom_sha256'] != 'd083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394':
        raise ValueError('Wrong Japanese source')
    if any(r['rom_sha256'] != target for r in reports[1:]):
        raise ValueError('Wrong localized artifact')
    if len({r['input_save_sha256'] for r in reports}) != 1:
        raise ValueError('Different review saves')
    for r in reports:
        if r['ram_interventions'] or [x['index'] for x in r['records']] != list(range(37)):
            raise ValueError('Incomplete or intervened capture')
    def pixels(cap, box):
        path = Path(cap['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != cap['sha256']:
            raise ValueError('Capture changed')
        return np.array(Image.open(path).convert('RGB').crop(box)) >> 3
    def equal(caps, box):
        images = [pixels(c, box) for c in caps]
        if any(not np.array_equal(images[0], x) for x in images[1:]):
            raise ValueError(f'Pixel mismatch: {[c["path"] for c in caps]}, {box}')
        return hashlib.sha256(images[0].tobytes()).hexdigest()
    rows = []
    for i in range(37):
        items = [r['records'][i] for r in reports]
        portrait = equal([r['selection'] for r in items], (136, 16, 224, 96))
        # The four complete 18-column text areas exclude only the next arrow.
        fields = [equal([r['fields'][f] for r in items[1:]], (0, 112, 224, 160)) for f in range(4)]
        # Return text must equal each run's initial selection prompt.
        for r, item in zip(reports, items):
            equal([r['records'][0]['selection'], item['return']], (0, 112, 224, 160))
        rows.append({'index':i, 'portrait_rgb555_sha256':portrait, 'large_field_rgb555_sha256':fields})
    if len({r['portrait_rgb555_sha256'] for r in rows}) != 37:
        raise ValueError('Duplicate portrait suggests stalled navigation')
    equal([r['boot'] for r in reports[1:]], (0, 0, 240, 160))
    out = {'status':'SCOPED_PIXEL_COMPARISON_PASS_VISUAL_REVIEW_SEPARATE', 'rom_sha256':target,
           'gallery_reports':[{'path':str(x), 'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in paths],
           'japanese_portraits_matching_both_cores':37, 'large_fields_matching_between_cores':148,
           'return_to_selection_checks':111, 'boot_bitmaps_equal':True, 'ram_interventions':0,
           'records':rows, 'scope':'Explicit synthetic review save. Portrait crop 136,16..224,96; complete text crop 0,112..224,160 excluding next arrow. RGB555 comparison; source-language semantic review and natural unlock progression remain separate.'}
    a.out.parent.mkdir(exist_ok=True, parents=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('records','gallery_reports')}))


if __name__ == '__main__':
    main()
