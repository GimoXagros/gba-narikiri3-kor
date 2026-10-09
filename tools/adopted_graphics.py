"""Adopted graphics stage; exact algorithms and source guards from bounded control."""
import hashlib,json,struct
import numpy as np
from gba_rle import unpack
from intro_graphics_stage import optimal_rle
from town_labels import tile_half,source_canvas
BASE="8207ba4bfa6721a59cfede08e3cab17fa13b2fe2013fa7d55cf07c330749b39f"
def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def u32(raw, at):
    return struct.unpack_from('<I', raw, at)[0]


def mgba_diagnostic(raw, at):
    """Frozen e31759b input semantics, DIAGNOSTIC ONLY; strict unpack unchanged."""
    if raw[at] != 0x30:
        raise ValueError('Not a BIOS type30 stream')
    n = int.from_bytes(raw[at + 1:at + 4], 'little')
    pos, data, last = at + 4, bytearray(), None
    while len(data) < n:
        token = pos
        flag = raw[pos]
        pos += 1
        count = (flag & 127) + 3 if flag & 128 else flag + 1
        take = min(count, n - len(data))
        last = {'offset': token, 'output_at': len(data), 'flag': flag, 'encoded_count': count, 'copied_count': take}
        data.extend(raw[pos:pos + 1] * take if flag & 128 else raw[pos:pos + take])
        pos += 1 if flag & 128 else take
    return bytes(data), pos, last


def compose(atlas, index, text):
    foreground, x, sources = set(), 0, []
    for char in text:
        if char == ' ':
            x += 2
            continue
        if char not in atlas['atlas']:
            raise ValueError('Missing exact native font glyph: ' + char)
        options = atlas['atlas'][char]
        source = next((row for row in options if row['resource'] == index), options[0])
        width = source['width']
        mask = bytes.fromhex(source['foreground_mask_hex'])
        if len(mask) != width * 11 or source['height'] != 11:
            raise ValueError('Native glyph geometry differs')
        points = {(x + k % width, k // width) for k, value in enumerate(mask) if value}
        if foreground & points or any(px >= 64 for px, py in points):
            raise ValueError('Glyph ink overlaps or clips')
        foreground |= points
        sources.append({'char': char, 'source': source, 'destination_x': x, 'foreground_pixels': len(points)})
        x += width
    if x > 63:
        raise ValueError('Native text/outline exceeds declared64pixel canvas')
    pixels = [[0] * 64 for _ in range(16)]
    for px, py in foreground:
        for yy in range(max(0, py - 1), min(16, py + 2)):
            for xx in range(max(0, px - 1), min(64, px + 2)):
                pixels[yy][xx] = 1
    for px, py in foreground:
        pixels[py][px] = 6
    return pixels, sources, x


def build(base, japanese, adopted, cumulative):
    if sha(base) != BASE or sha(japanese) != 'd083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394':
        raise ValueError('Immutable base or Japanese input differs')
    atlas = json.loads((adopted / 'native_atlas.json').read_text('utf-8'))
    decisions = json.loads((adopted / 'native_decisions.json').read_text('utf-8'))
    if len(decisions) != 32:
        raise ValueError('Native32 review denominator differs')
    writes, labels = [], []
    town_labels = []
    for index, text in [(13, '인간 목장'), (14, '배신의 요새'), (18, '얼음 동굴'), (22, '부유 요새')]:
        authority = next(row for row in decisions if int(row['bank'], 0) == 0x750a00 and row['index'] == index)
        if authority['decision'] != 'REVISE' or authority['recommended_after_readable'] != text:
            raise ValueError('Selected wording differs from independent JA recommendation')
        bank, field = 0x750a00, 0x750a00 + 4 + index * 4
        at = bank + u32(base, field)
        if at != bank + u32(japanese, field):
            raise ValueError('Selected native original source pointer differs')
        old, old_end = unpack(base, at, len(base), 512)
        _, jp_end = unpack(japanese, at, len(japanese), 512)
        unchanged, _, _ = compose(atlas, index, atlas['texts'][index])
        if tile_half(unchanged, 0) + tile_half(unchanged, 1) != old:
            raise ValueError('Exact old foreground+outline source reproduction failed')
        pixels, sources, width = compose(atlas, index, text)
        payload = tile_half(pixels, 0) + tile_half(pixels, 1)
        packed = optimal_rle(payload)
        if len(packed) > jp_end - at:
            raise ValueError('Original Japanese resource allocation exceeded')
        # This is the actual original type30 object's consumed extent, not an
        # inferred blank gap. It keeps its original directory binding. Reject
        # nested directory objects and any current-stage owner intersecting it.
        bank_targets = [bank + u32(base, bank + 4 + k * 4) for k in range(u32(base, bank))]
        if any(at < other < jp_end for other in bank_targets):
            raise ValueError('Original compressed object contains another directory owner')
        if any(row['offset'] < jp_end and row['offset'] + len(bytes.fromhex(row['payload_hex'])) > at for row in cumulative):
            raise ValueError('Current managed owner overlaps original compressed object')
        check, end = unpack(packed, 0, len(packed), 512)
        if check != payload or end != len(packed):
            raise ValueError('Strict edited RLE roundtrip failed')
        writes.append({'writer': 'native-source-font-label-' + str(index), 'offset': at, 'allowed_end': jp_end,
                       'expected_sha256': sha(base[at:at + len(packed)]), 'payload_hex': packed.hex(),
                       'bank_field': field, 'bank_field_before_hex': base[field:field + 4].hex()})
        labels.append({'index': index, 'before': atlas['texts'][index], 'after': text, 'width': width,
                       'decoded_bytes': 512, 'packed_bytes': len(packed), 'current_active_bytes': old_end - at,
                       'original_JP_owned_bytes': jp_end - at, 'original_JP_owned_sha256': sha(base[at:jp_end]),
                       'ownership': 'Same original directory object; bounded by actual Japanese stream consumption; no nested bank owner or cumulative managed writer.',
                       'source_glyphs': sources, 'raster_index_hex': bytes(v for row in pixels for v in row).hex(),
                       'decoded_sha256': sha(payload), 'old_decoded_sha256': sha(old), 'original_source_roundtrip_exact': True,
                       'field': field, 'offset': at, 'old_end': old_end, 'new_end': at + len(packed)})
    contexts = json.loads((adopted / 'town_decisions.json').read_text('utf-8'))
    for number, cut, before, after in [(8, 18, '숲의집회소', '숲의 집회소'), (13, 19, '석양다리', '석양 다리')]:
        indices = [58 + number, 73 + number]
        authority = next(row for row in contexts if row['review_id'] == f'typed62-town-{number:02d}')
        if authority['bank'] != '0x75f474' or authority['resource_indices'] != indices or authority['current_transcription'] != before or authority['recommended_korean'] != after or authority['decision'] != 'REVISE':
            raise ValueError('Town zero-based ID/resource-pair/wording authority differs')
        original = source_canvas(base, 0x75f474, number)
        if any(row[cut] for row in original[:12]) or any(v for row in original[:12] for v in row[62:]):
            raise ValueError('Word-run split or empty trailing extent differs')
        width = max(x for x, value in enumerate(original[12]) if value) + 1
        if original[12] != [1] * width + [0] * (64 - width) or original[14] != original[12] or original[13] != [1] + [2] * (width - 2) + [1] + [0] * (64 - width) or any(original[15]) or width + 2 > 64:
            raise ValueError('Original embossed underline structure/extent differs')
        pixels = [row[:cut] + [0, 0] + row[cut:62] for row in original]
        for y in range(12):
            if pixels[y][:cut] + pixels[y][cut + 2:] + [0, 0] != original[y]:
                raise ValueError('Shifted town word runs lose original pixels')
        for y in (12, 14):
            pixels[y] = [1] * (width + 2) + [0] * (62 - width)
        pixels[13] = [1] + [2] * width + [1] + [0] * (62 - width)
        packed_rows = []
        for half, index in enumerate(indices):
            bank, field = 0x75f474, 0x75f474 + 4 + index * 4
            at = bank + u32(base, field)
            if at != bank + u32(japanese, field):
                raise ValueError('Selected town pair moved from its original source')
            old, old_end = unpack(base, at, len(base), 256)
            _, jp_end = unpack(japanese, at, len(japanese), 256)
            if tile_half(original, half) != old:
                raise ValueError('Town original tile roundtrip failed')
            packed = optimal_rle(tile_half(pixels, half))
            if len(packed) > jp_end - at:
                raise ValueError('Town corrected half exceeds original Japanese owned stream')
            targets = [bank + u32(base, bank + 4 + k * 4) for k in range(u32(base, bank))]
            if any(at < target < jp_end for target in targets) or any(row['offset'] < jp_end and row['offset'] + len(bytes.fromhex(row['payload_hex'])) > at for row in cumulative):
                raise ValueError('Town original source has nested/current managed owner')
            decoded, end = unpack(packed, 0, len(packed), 256)
            if decoded != tile_half(pixels, half) or end != len(packed):
                raise ValueError('Town strict edited roundtrip failed')
            writes.append({'writer': f'town-word-run-spacing-{number}-half{half}', 'offset': at, 'allowed_end': jp_end,
                           'expected_sha256': sha(base[at:at + len(packed)]), 'payload_hex': packed.hex(),
                           'bank_field': field, 'bank_field_before_hex': base[field:field + 4].hex()})
            packed_rows.append({'index': index, 'field': field, 'start': at, 'new_packed_bytes': len(packed), 'original_JP_owned_bytes': jp_end - at,
                                'original_JP_owned_sha256': sha(base[at:jp_end]), 'decoded_sha256': sha(decoded)})
        town_labels.append({'review_id': authority['review_id'], 'number_zero_based': number, 'indices': indices, 'before': before, 'after': after,
                            'word_cut': cut, 'added_gap_pixels': 2, 'old_underline_width': width, 'new_underline_width': width + 2,
                            'letter_pixels_preserved_exactly_by_inverse_shift': True, 'palette_and_two32x16_geometry_unchanged': True,
                            'raster_index_hex': bytes(v for row in pixels for v in row).hex(), 'halves': packed_rows})
    bank = 0xf1d734
    bad, repairs, valid = [], [], 0
    if u32(base, bank) != 111:
        raise ValueError('Original menu bank111 denominator differs')
    for index in range(111):
        field = bank + 4 + index * 4
        at = bank + u32(base, field)
        if base[at] != 0x30:
            continue
        n = int.from_bytes(base[at + 1:at + 4], 'little')
        try:
            unpack(base, at, len(base), n)
            valid += 1
            continue
        except ValueError as error:
            if str(error) != 'RLE run exceeds decoded extent':
                raise
        output, consumed_end, last = mgba_diagnostic(base, at)
        following = bank + u32(base, field + 4)
        row = {'index': index, 'field': field, 'start': at, 'directory_next_start': following, 'declared_bytes': n,
               'actual_mgba_input_end': consumed_end, 'display_bytes_sha256': sha(output), 'last_token': last,
               'minimal_strict_bytes': len(optimal_rle(output))}
        bad.append(row)
        if index == 52:
            row['status'] = 'HOLD_BOUNDARY_CROSSES_NEXT_HEADER; strict126bytes exceeds124byte original owner'
            continue
        if at != bank + u32(japanese, field) or consumed_end > following or not at < last['offset'] < consumed_end:
            raise ValueError('Final token repair source does not stay in original object owner')
        take = last['copied_count']
        repaired_flag = (0x80 | (take - 3)) if last['flag'] & 128 and take >= 3 else take - 1
        local = bytearray(base[at:consumed_end])
        local[last['offset'] - at] = repaired_flag
        strict, end = unpack(local, 0, len(local), n)
        if strict != output or end != len(local):
            raise ValueError('Strict last-token canonicalization changes displayed bytes or input extent')
        writes.append({'writer': 'strict-final-token-menu-' + str(index), 'offset': last['offset'], 'allowed_end': last['offset'] + 1,
                       'expected_sha256': sha(base[last['offset']:last['offset'] + 1]), 'payload_hex': bytes([repaired_flag]).hex(),
                       'bank_field': field, 'bank_field_before_hex': base[field:field + 4].hex()})
        repairs.append(row | {'status': 'STRICT_EXACT_DISPLAY_REPAIR', 'new_flag': repaired_flag,
                              'source_bytes_added': 0, 'original_pointer_unchanged': True})
    if [row['index'] for row in bad] != [52, 58, 87, 88, 89, 95] or valid != 66:
        raise ValueError('Inherited invalid-stream population differs')
    proposal = json.loads((adopted / 'rle52.json').read_text('utf-8'))
    if proposal['immutable_base_sha256'] != BASE:raise ValueError('RLE52 source applicability differs')
    source_at=int(proposal['source_old_start'],0)
    decoded,source_end,_=mgba_diagnostic(base,source_at)
    if source_end!=int(proposal['source_old_actual_read_end'],0) or sha(base[source_at:source_end])!=proposal['source_old_read_sha256'] or sha(decoded)!=proposal['decoded_sha256']:
        raise ValueError('Inherited RLE52 current consumed source differs')
    packed=optimal_rle(decoded)
    if len(packed)!=proposal['strict_stored_bytes']:raise ValueError('Regenerated strict RLE52 length differs')
    target=int(proposal['new_start'],0)
    proposal['writes'][0]['payload_hex']=(packed+b'\xff'*(proposal['allocated_aligned_bytes']-len(packed))).hex()
    proposal['writes'][1]['payload_hex']=struct.pack('<I',(target-int(proposal['source_bank'],0))&0xffffffff).hex()
    for row in proposal['writes']:
        start, end = row['offset'], row['offset'] + len(bytes.fromhex(row['payload_hex']))
        if (start, end) not in ((0x1193dd4, 0x1193e54), (0xf1d808, 0xf1d80c)):
            raise ValueError('Approved RLE52 write bounds differ')
        if any(w['offset'] < end and w['offset'] + len(bytes.fromhex(w['payload_hex'])) > start for w in cumulative + writes):
            raise ValueError('Approved RLE52 object/pointer collides with current writer')
        writes.append(row | {'bank_field': 0xf1d808, 'bank_field_before_hex': base[0xf1d808:0xf1d80c].hex()})
    expected = bytearray(base)
    permitted = np.zeros(len(base), dtype=np.bool_)
    previous = 0
    for row in sorted(writes, key=lambda r: r['offset']):
        start, payload = row['offset'], bytes.fromhex(row['payload_hex'])
        end = start + len(payload)
        if start < previous or end > row['allowed_end'] or sha(base[start:end]) != row['expected_sha256']:
            raise ValueError('Overlapping or unguarded additional graphics writer')
        field = row['bank_field']
        if base[field:field + 4].hex() != row['bank_field_before_hex']:
            raise ValueError('Before-bank source binding differs')
        expected[start:end] = payload
        permitted[start:end] = True
        previous = end
    candidate = bytes(expected)
    delta = np.frombuffer(base, np.uint8) != np.frombuffer(candidate, np.uint8)
    if np.any(delta & ~permitted) or len(candidate) != len(base) or candidate[0x1000000:0x1000400] != base[0x1000000:0x1000400]:
        raise ValueError('Unexpected diff, ROM growth or renderer change')
    for row in repairs:
        decoded, end = unpack(candidate, row['start'], row['directory_next_start'], row['declared_bytes'])
        if sha(decoded) != row['display_bytes_sha256'] or end != row['actual_mgba_input_end']:
            raise ValueError('Final strict source-bound repair differs')
    relocated, consumed = unpack(candidate, 0x1193dd4, 0x1193e54, 128)
    if sha(relocated) != proposal['decoded_sha256'] or consumed != 0x1193e52 or candidate[0xf27a40:0xf27b44] != base[0xf27a40:0xf27b44] or candidate[0xf1d808:0xf1d80c] != bytes.fromhex('a0662700'):
        raise ValueError('Approved RLE52 exact output, old source/neighbor53 or new pointer differs')
    strict_streams = 0
    for index in range(111):
        at = 0xf1d734 + u32(candidate, 0xf1d734 + 4 + index * 4)
        if candidate[at] == 0x30:
            n = int.from_bytes(candidate[at + 1:at + 4], 'little')
            decoded, end = unpack(candidate, at, 0x1193e54 if index == 52 else len(candidate), n)
            old_at = 0xf1d734 + u32(base, 0xf1d734 + 4 + index * 4)
            if decoded != mgba_diagnostic(base, old_at)[0]:
                raise ValueError('Menu strict stream alters baseline display bytes')
            strict_streams += 1
    if strict_streams != 72:
        raise ValueError('Strict menu stream denominator differs')
    report = {'status': 'BOUNDED_ADDITIONAL_GRAPHICS_STAGE_BUILT_NATIVE_CPU_REVIEW_PENDING', 'baseline_sha256': sha(base),
              'rom_sha256': sha(candidate), 'rom_bytes': len(candidate), 'changed_bytes': int(delta.sum()), 'unexpected_changed_bytes': 0,
              'writes': writes, 'native_label_changes': labels, 'town_label_changes': town_labels, 'inherited_type30_scan': {'bank_entries': 111, 'streams': 72, 'strict_valid_before': 66,
                                                                                      'invalid_before': bad, 'strict_repairs': repairs, 'invalid_after': [], 'strict_valid_after': strict_streams},
              'rle52_relocation': proposal | {'status': 'EXACT_APPROVED_DESIGN_APPLIED_FINAL_COMBINED_AUDIT_PENDING', 'production_rom_written': True},
              'pointer_changes': [{'bank': '0xf1d734', 'index': 52, 'field': '0xf1d808', 'before_hex': base[0xf1d808:0xf1d80c].hex(), 'after_hex': candidate[0xf1d808:0xf1d80c].hex()}],
              'all_text_pointer_fields_and_all_other_bank_pointer_fields_unchanged': True,
              'renderer_and_fonts_unchanged': True, 'graphics_review_denominators': {'native32': 32, 'native32_changed_here': 4, 'native25_place_labels': 25, 'native24_selector_table': 24,
                                                                                  'typed62': 62, 'original_complete_contexts': 35, 'current_exposed_contexts': 39, 'typed_complete_contexts_changed_here': 2},
              'limits': ['Development stage only; no final independent combined approval.', '52 inherited final0x40 display byte preserved explicitly.',
                         'Long floor labels and missing native glyphs remain separate.', 'Native CPU and natural path validation are separate gates.']}
    return candidate, report
