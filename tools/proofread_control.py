"""Immutable five graphics writes plus adopted text and typed-pointer writes.

Preparation plans are reviewable without creating a ROM. Growth/context split
uses the existing absolute-u32 data-pointer method, never code relocation.
"""
import argparse
import json
import struct
from collections import defaultdict
from pathlib import Path

import numpy as np

from intro_graphics_stage import ROOT, plan as graphics_plan, sha
from dialogue_structure import source_records
from dialogue_tokens import controls
from text_codec import encode
from tone_inplace import cstr


def indexed_bindings(japanese, legacy, base, profile):
    result = {}
    for row in source_records(japanese, legacy):
        result[f'vm-{row["record_offset"]:08X}'] = row['record_offset'] + 4
    if profile.get('public_binding_map'):
        result.update(json.loads((ROOT / profile['public_binding_map']).read_text('utf-8')))
    else:
        work = ROOT / 'output/proofread-hanja-20261002'
        for row in map(json.loads, (work / 'typed-nondialogue-rom-readback.jsonl').read_text('utf-8').splitlines()):
            result[row['review_id']] = int(row['pointer_field_rom_offset'], 0)
            if row['source_review_id']:
                result[row['source_review_id']] = int(row['pointer_field_rom_offset'], 0)
    ui = json.loads((ROOT / 'source/review_ui_profile.json').read_text('utf-8'))
    for row in ui['fields']:
        result['review_ui:' + row['stable_id'] + ':text'] = int(row['pointer_offset'], 0)
    for row in profile['changes']:
        if result.get(row['review_id']) != int(row['pointer_field'], 0):
            raise ValueError('Adopted row does not match proven typed pointer field')
    return result


def scan_references(base, ranges, known_fields):
    """Every four-byte window, all six mirrors; unidentified words forbid in-place writes."""
    starts = np.array(sorted(ranges), dtype=np.int64)
    ends = np.array([ranges[int(at)] for at in starts], dtype=np.int64)
    result = {int(at): [] for at in starts}
    for alignment in range(4):
        count = (len(base) - alignment) // 4
        words = np.frombuffer(base, dtype='<u4', count=count, offset=alignment)
        high = words >> 24
        slots = np.flatnonzero((high >= 8) & (high <= 13))
        values = words[slots]
        physical = values & 0x01ffffff
        idx = np.searchsorted(starts, physical, side='right') - 1
        valid = idx >= 0
        valid[valid] &= physical[valid] <= ends[idx[valid]]
        for pos, value, address, index in zip(slots[valid], values[valid], physical[valid], idx[valid]):
            start, field = int(starts[index]), int(alignment + pos * 4)
            result[start].append({'field': hex(field), 'value': hex(int(value)), 'interior_bytes': int(address) - start,
                                  'kind': 'KNOWN_TYPED_STRING_FIELD' if field in known_fields and int(address) == start
                                  else 'UNCLASSIFIED_MIRROR_POINTER_LIKE'})
    return result


def prepare_plan(base, japanese, legacy, profile):
    if sha(base) != profile['baseline_sha256'] or len(base) != profile['baseline_bytes']:
        raise ValueError('Proofread immutable baseline differs')
    for name, expected in profile.get('review_inputs', {}).items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError('Frozen review input differs: ' + name)
    graphics = json.loads((ROOT / profile['graphics_profile']).read_text('utf-8'))
    if sha((ROOT / profile['graphics_profile']).read_bytes()) != profile['graphics_profile_sha256']:
        raise ValueError('Adopted graphics source differs')
    writes, _ = graphics_plan(base, japanese, graphics)
    bindings = indexed_bindings(japanese, legacy, base, profile)
    fields = set(bindings.values())
    groups, by_start = defaultdict(list), defaultdict(set)
    for field in fields:
        pointer = struct.unpack_from('<I', base, field)[0]
        by_start[pointer - 0x08000000].add(field)
    changes = profile['changes']
    selected_fields = {int(row['pointer_field'], 0) for row in changes}
    if len(selected_fields) != len(changes):
        raise ValueError('Duplicate selected pointer field')
    targets = {}
    for row in changes:
        field, pointer = int(row['pointer_field'], 0), int(row['baseline_pointer'], 0)
        at = pointer - 0x08000000
        before, after = cstr(base, at), encode(row['after_rom'])
        if struct.unpack_from('<I', base, field)[0] != pointer or before.hex() != row['before_hex'] or sha(before) != row['before_sha256']:
            raise ValueError('Adopted pointer/string source guard differs')
        if after.hex() != row['after_hex'] or [t for _, t in controls(before)] != [t for _, t in controls(after)]:
            raise ValueError('Adopted encoding or control tokens differ')
        groups[at].append(row)
        targets[at] = at + len(before)
    references = scan_references(base, targets, fields)
    arena_start, arena_end = (int(profile['allocation'][k], 0) for k in ('start', 'end'))
    if not 0x1000000 <= arena_start < arena_end <= len(base) or base[arena_start:arena_end] != b'\xff' * (arena_end - arena_start):
        raise ValueError('Proposed generated-extension allocation is occupied or outside32MiB')
    cursor, layout = arena_start, []
    for start, rows in sorted(groups.items()):
        before = cstr(base, start)
        selected = {int(row['pointer_field'], 0) for row in rows}
        requested = {bytes.fromhex(row['after_hex']) for row in rows}
        unresolved = [r for r in references[start] if r['kind'] != 'KNOWN_TYPED_STRING_FIELD']
        known_all = by_start[start]
        can_inplace = len(requested) == 1 and selected == known_all and not unresolved and len(next(iter(requested))) <= len(before)
        # Any other indexed string start inside this payload is an interior consumer.
        if any(start < other <= start + len(before) for other in by_start):
            can_inplace = False
        if can_inplace:
            raw = next(iter(requested))
            payload = raw + b'\0' + b'\0' * (len(before) - len(raw))
            writes.append({'writer': '+'.join(row['review_id'] for row in rows), 'offset': start,
                           'allowed_end': start + len(payload), 'expected_sha256': sha(base[start:start + len(payload)]), 'payload': payload})
            for row in rows:
                layout.append({'review_id': row['review_id'], 'pointer_field': row['pointer_field'], 'old_start': hex(start),
                               'new_start': hex(start), 'stored_bytes': len(raw) + 1, 'original_payload_capacity': len(before) + 1,
                               'placement': 'EXISTING_SLOT_IN_PLACE', 'pointer_changed': False,
                               'source_hash': row['before_sha256'], 'all_known_bindings': [hex(x) for x in sorted(known_all)],
                               'whole_rom_pointer_like_refs': references[start], 'unresolved_count': 0})
        else:
            # Original payload remains untouched; selected contexts may separate safely.
            per_value = {}
            for row in rows:
                raw = bytes.fromhex(row['after_hex'])
                if raw not in per_value:
                    cursor = (cursor + 3) & ~3
                    if cursor + len(raw) + 1 > arena_end:
                        raise ValueError('Proofread arena overflow')
                    per_value[raw] = cursor
                    payload = raw + b'\0'
                    writes.append({'writer': 'proofread-resource-' + row['review_id'], 'offset': cursor,
                                   'allowed_end': arena_end, 'expected_sha256': sha(base[cursor:cursor + len(payload)]), 'payload': payload})
                    cursor += len(payload)
                target = per_value[raw]
                field = int(row['pointer_field'], 0)
                payload = struct.pack('<I', 0x08000000 + target)
                writes.append({'writer': 'proofread-pointer-' + row['review_id'], 'offset': field,
                               'allowed_end': field + 4, 'expected_sha256': sha(base[field:field + 4]), 'payload': payload})
                layout.append({'review_id': row['review_id'], 'pointer_field': row['pointer_field'], 'old_start': hex(start),
                               'new_start': hex(target), 'stored_bytes': len(raw) + 1, 'original_payload_capacity': len(before) + 1,
                               'placement': 'EXISTING32MIB_GENERATED_EXTENSION_RELOCATED', 'pointer_changed': True,
                               'source_hash': row['before_sha256'], 'old_payload_retained': True,
                               'all_known_bindings': [hex(x) for x in sorted(known_all)],
                               'whole_rom_pointer_like_refs': references[start], 'unresolved_count': len(unresolved),
                               'reason': 'Growth beyond actual payload/NUL' if len(raw) > len(before) else 'Context sharing or unclassified/interior references: preserve old object'})
    prior = 0
    for write in sorted(writes, key=lambda x: x['offset']):
        at, end = write['offset'], write['offset'] + len(write['payload'])
        if at < prior or end > write['allowed_end'] or end > len(base) or sha(base[at:end]) != write['expected_sha256']:
            raise ValueError('Expected Write collision, range or immutable guard failure')
        prior = end
    for region in json.loads((ROOT / 'source/nontext_profile.json').read_text('utf-8'))['regions']:
        start, end = int(region['start'], 0), int(region['end'], 0)
        if any(w['offset'] < end and start < w['offset'] + len(w['payload']) for w in writes):
            raise ValueError('Expected Write intersects protected nontext region: ' + region['id'])
    result = {'schema': 1, 'status': 'PLANNED_NOT_APPLIED_PENDING_TARGETED_ALLOCATION_REVIEW',
              'baseline_sha256': sha(base), 'graphics_control_sha256': 'ae241228a8268c9e31793f07f63820c408a0a1bb525209bba79f78a81111034d',
              'profile_sha256': sha(json.dumps(profile, ensure_ascii=False, indent=2).encode('utf-8') + b'\n'),
              'selected_text_fields': len(changes), 'in_place_fields': sum(not r['pointer_changed'] for r in layout),
              'relocated_fields': sum(r['pointer_changed'] for r in layout), 'arena_start': hex(arena_start),
              'arena_used_end': hex(cursor), 'arena_limit': hex(arena_end), 'arena_used_bytes_including_alignment': cursor - arena_start,
              'arena_baseline_sha256': sha(base[arena_start:arena_end]),
              'implementation': 'Existing absolute-u32 LE GBA data pointers; same original getters/renderers/formatters; no code/hook/branch changes; old source objects retained for split contexts.',
              'original16MIB_unknown_space_used': 0, 'rom_growth': 0, 'maps': layout,
              'writes': [{**{k: v for k, v in w.items() if k != 'payload'}, 'payload_hex': w['payload'].hex(),
                          'payload_sha256': sha(w['payload']), 'byte_count': len(w['payload'])} for w in writes],
              'known_binding_field_count': len(fields), 'whole_rom_pointer_scan': 'Every four-byte window, all08/09/0A/0B/0C/0D mirrors; any unexplained word forbids source-slot mutation.',
              'held': profile['held'], 'keep_ids': profile['keep_ids']}
    return result, writes, bindings


def certificate_constructor_path(name):
    """Certificate schema uses constructor basenames, exclusively under tools."""
    if not isinstance(name, str) or not name or '/' in name or '\\' in name or ':' in name or name in ('.', '..'):
        raise ValueError('Invalid arena constructor basename')
    path = (ROOT / 'tools' / name).resolve()
    if path.parent != (ROOT / 'tools').resolve():
        raise ValueError('Arena constructor escapes tools directory')
    return path


def validate_application(base, report, writes, approval):
    """Read-only application gate; never constructs or writes a candidate ROM."""
    if approval.get('decision') != 'APPROVE_BOUNDED_32MIB_LANGUAGE_PLAN' or approval.get('plan_sha256') != sha(json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8') + b'\n'):
        raise ValueError('Exact-plan targeted review approval missing or different')
    if approval.get('implementation_sha256') != sha(Path(__file__).read_bytes()):
        raise ValueError('Reviewed application implementation differs')
    profile_paths = [ROOT / 'source/proofread_hanja_profile.json', ROOT / 'source/proofread_hanja_profile_skill195.json']
    profile_bytes = next((path.read_bytes() for path in profile_paths if path.exists() and sha(path.read_bytes()) == report['profile_sha256']), None)
    if profile_bytes is None:
        raise ValueError('Reviewed source profile differs')
    profile = json.loads(profile_bytes)
    if sha(profile_bytes) != report['profile_sha256'] or approval.get('profile_sha256') != report['profile_sha256']:
        raise ValueError('Reviewed source profile differs')
    if len(base) != profile['baseline_bytes'] or len(base) != 0x2000000 or sha(base) != report['baseline_sha256'] or sha(base) != profile['baseline_sha256']:
        raise ValueError('Application immutable baseline hash or size differs')
    # Bind every actual write, including its payload, to the approved ordered list.
    actual = []
    for write in writes:
        if set(write) != {'writer', 'offset', 'allowed_end', 'expected_sha256', 'payload'} or not isinstance(write['payload'], bytes):
            raise ValueError('Unexpected application write schema')
        if type(write['offset']) is not int or type(write['allowed_end']) is not int:
            raise ValueError('Expected Write address type differs')
        actual.append({**{k: v for k, v in write.items() if k != 'payload'}, 'payload_hex': write['payload'].hex(),
                       'payload_sha256': sha(write['payload']), 'byte_count': len(write['payload'])})
    if actual != report['writes']:
        raise ValueError('Actual writes differ from approved report')
    # Reconstruct the sole application input from the approved report itself.
    approved = [{k: row[k] for k in ('writer', 'offset', 'allowed_end', 'expected_sha256')} |
                {'payload': bytes.fromhex(row['payload_hex'])} for row in report['writes']]
    prior_end = 0
    for write in sorted(approved, key=lambda row: row['offset']):
        at, end = write['offset'], write['offset'] + len(write['payload'])
        if not write['payload'] or at < prior_end or at < 0 or end > write['allowed_end'] or write['allowed_end'] > len(base):
            raise ValueError('Application Expected Write overlap or bounds failure')
        if sha(base[at:end]) != write['expected_sha256']:
            raise ValueError('Application immutable before guard differs')
        prior_end = end
    graphics_path = ROOT / profile['graphics_profile']
    if sha(graphics_path.read_bytes()) != profile['graphics_profile_sha256']:
        raise ValueError('Reviewed graphics profile differs')
    graphics = json.loads(graphics_path.read_text('utf-8'))
    protected = list(graphics['protected_ranges']) + json.loads((ROOT / 'source/nontext_profile.json').read_text('utf-8'))['regions']
    protected.append({'start': graphics['large_font_offset'], 'end': graphics['large_font_end'], 'sha256': graphics['large_font_sha256']})
    for region in protected:
        at, end = int(region['start'], 0), int(region['end'], 0)
        if sha(base[at:end]) != region['sha256']:
            raise ValueError('Application protected baseline guard differs')
        if any(row['offset'] < end and at < row['offset'] + len(row['payload']) for row in approved):
            raise ValueError('Application write intersects protected region')
    if not isinstance(approval.get('ownership_certificate'), dict) or not approval.get('reviewer'):
        raise ValueError('Allocator ownership evidence/reviewer missing')
    proof = approval['ownership_certificate']
    proof_path = ROOT / proof['path']
    if sha(proof_path.read_bytes()) != proof['sha256']:
        raise ValueError('Reviewed ownership certificate changed')
    certificate = json.loads(proof_path.read_text('utf-8'))
    if (certificate['status'] != 'BUILDER_OWNED32MIB_UNUSED_ARENA_TYPED_GRAPH_CLEAR' or
            certificate['baseline_sha256'] != report['graphics_control_sha256'] or
            certificate['start'] != report['arena_start'] or certificate['end'] != report['arena_limit'] or
            certificate['expected_before_sha256'] != report['arena_baseline_sha256'] or
            certificate['known_objects_overlapping'] or certificate['typed_references_into_arena'] or
            certificate['original_directory_entries_into_arena']):
        raise ValueError('Reviewed arena ownership or applicability differs')
    for name, digest in certificate['source_hashes'].items():
        if sha(certificate_constructor_path(name).read_bytes()) != digest:
            raise ValueError('Arena constructor source differs: ' + name)
    if sha(base[int(report['arena_start'], 0):int(report['arena_limit'], 0)]) != certificate['expected_before_sha256']:
        raise ValueError('Application arena immutable before differs')
    return approved


def apply_plan(base, report, writes, approval):
    approved = validate_application(base, report, writes, approval)
    result = bytearray(base)
    allowed = np.zeros(len(base), dtype=np.bool_)
    for w in approved:
        at, payload = w['offset'], w['payload']
        result[at:at + len(payload)] = payload
        allowed[at:at + len(payload)] = True
    output = bytes(result)
    diff = np.frombuffer(base, np.uint8) != np.frombuffer(output, np.uint8)
    if len(output) != len(base) or np.any(diff & ~allowed):
        raise ValueError('Unexplained final diff or growth')
    return output, {'changed_bytes': int(diff.sum()), 'unexplained_changed_bytes': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path, default=ROOT / 'source/proofread_hanja_profile.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Fresh plan path required')
    base = (ROOT / 'output/tone-inplace-final-20260930/ND3_B3TJ_K_v1.2_tone-inplace.gba').read_bytes()
    japanese = next(ROOT.glob('*[[]B3TJ[]][[]J[]].gba')).read_bytes()
    legacy = next(ROOT.glob('*[[]B3TJ[]][[]K[]]_1.1.gba')).read_bytes()
    result, _, _ = prepare_plan(base, japanese, legacy, json.loads(args.profile.read_text('utf-8')))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf-8', newline='\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('maps', 'writes', 'held', 'keep_ids')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
