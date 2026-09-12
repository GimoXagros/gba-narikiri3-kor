"""Read-only end-of-frame glyph-cache measurements during controller replays.

This observes a bounded route, not every draw inside a frame or every screen.
No core or guest code, RAM, or persistent save is modified by the sampler.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from runtime_probe import Probe


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--save', type=Path)
    p.add_argument('--trace', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    lines = [json.loads(line) for line in a.trace.read_text(encoding='utf-8').splitlines()]
    controller_requests = [row['request'] for row in lines if row.get('request', {}).get('op') == 'frames']
    controller_hash = hashlib.sha256(json.dumps(controller_requests, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if any(row.get('request', {}).get('op') in ('state_load', 'ram_compare_set') for row in lines):
        raise ValueError('Only traces without guest-state intervention are accepted')
    source = next((row for row in lines if row.get('op') == 'initialize'), None)
    input_hash = hashlib.sha256(a.save.read_bytes()).hexdigest() if a.save else None
    if source and source['input_save_sha256'] != input_hash:
        raise ValueError('Replay does not use its recorded ordinary EEPROM input')
    probe = Probe(a.core, a.rom, a.out, a.save)
    capacity = set(range(0x70, 0xae)) | set(range(0xb0, 0xee))
    maximum = -1
    valid = 0
    skipped = 0
    high_water = []
    original_run = probe.lib.retro_run
    def run_and_sample():
        nonlocal maximum, valid, skipped
        original_run()
        try:
            font, tile_base = struct.unpack('<II', probe.read_memory(0x03000054, 8))
        except ValueError:
            skipped += 1
            return
        if not (0x06000000 <= font <= 0x06016000 and font % 32 == 0 and tile_base <= 0x300):
            skipped += 1
            return
        shadow = probe.read_memory(0x03000060, 2048)
        refs = {((v & 1023) - tile_base) for (v,) in struct.iter_unpack('<H', shadow)}
        pinned = sorted(refs & capacity)
        valid += 1
        if len(pinned) > maximum:
            maximum = len(pinned)
            frame = probe.frame + 1
            entry = {'end_of_guest_frame': frame, 'pinned_cache_slots': maximum,
                     'font_base': hex(font), 'absolute_tile_base': tile_base,
                     'shadow_sha256': hashlib.sha256(shadow).hexdigest(),
                     'relative_slots': pinned}
            high_water.append(entry)
            (probe.root / f'high-water-{frame}-shadow.bin').write_bytes(shadow)
            (probe.root / f'high-water-{frame}-font.bin').write_bytes(probe.read_memory(font, 8192))
            # Video already belongs to the completed guest frame. The host's
            # frame counter increments after this wrapper returns.
            if probe.video is not None:
                shot = probe.execute({'op': 'screenshot', 'name': f'high-water-{frame}.png'})
                entry['image_sha256'] = shot['sha256']
                entry['image_file'] = Path(shot['path']).name
    probe.lib.retro_run = run_and_sample
    try:
        for row in lines:
            request = row.get('request', {})
            if request.get('op') == 'frames':
                probe.execute(request)
        final_image = probe.execute({'op': 'screenshot', 'name': 'final.png'})
        final_save = probe.execute({'op': 'save_export', 'name': 'final.sav'})
        report = {'status': 'SCOPED_END_OF_FRAME_MEASUREMENT_COMPLETE',
                  'rom_sha256': probe.rom_hash, 'core_sha256': probe.dll_hash,
                  'small_and_simple_hook_region_0x400_sha256': hashlib.sha256(probe.rom[0x1000000:0x1000400]).hexdigest(),
                  'trace_sha256': hashlib.sha256(a.trace.read_bytes()).hexdigest(),
                  'controller_sequence_sha256': controller_hash,
                  'input_save_sha256': input_hash, 'ram_interventions': probe.ram_interventions,
                  'frames': probe.frame, 'valid_font_context_frames': valid,
                  'uninitialized_or_outside_context_frames': skipped,
                  'maximum_referenced_cache_slots': maximum, 'cache_capacity': 124,
                  'final_image_sha256': final_image['sha256'],
                  'final_save_sha256': final_save['sha256'],
                  'high_water': high_water,
                  'limits': ['End-of-frame samples do not cover transient per-draw occupancy.',
                             'Shadow-map references include offscreen/stale cells, as the current allocator does.',
                             'A bounded controller route is not a bound for every game screen or loader.',
                             'Counts alone do not prove every visible glyph has the intended pixels.']}
        if valid + skipped != probe.frame:
            raise ValueError('Not every completed guest frame was accounted for')
        (probe.root / 'font-working-set.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k != 'high_water'}, ensure_ascii=False))
    finally:
        probe.lib.retro_run = original_run
        probe.lib.retro_unload_game()
        probe.lib.retro_deinit()


if __name__ == '__main__':
    main()
