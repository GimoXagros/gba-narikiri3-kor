"""Fixed-length, identity-guarded overlays for the published v1.3a image."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = '0008712948a3dd570d817bdcb15ec2c3ae3a12bf06d56047882569f091e66968'


def apply_profiles(base, profiles):
    changes = {}
    for profile in profiles:
        for row in profile['writes']:
            at = row['offset']
            before = bytes.fromhex(row['expected_hex'])
            after = bytes.fromhex(row['payload_hex'])
            if not before or len(before) != len(after) or at < 0 or at + len(before) > len(base):
                raise ValueError('Invalid fixed-length overlay bounds')
            if base[at:at + len(before)] != before:
                raise ValueError(f'Overlay source mismatch at {at:#x}')
            for i, value in enumerate(after):
                if at + i in changes and changes[at + i] != value:
                    raise ValueError(f'Conflicting overlay at {at+i:#x}')
                changes[at + i] = value
    result = bytearray(base)
    for at, value in changes.items():
        result[at] = value
    return bytes(result)


def build_text(base):
    if len(base) != 16777216 or hashlib.sha256(base).hexdigest() != BASE_SHA256:
        raise ValueError('Exact published v1.3a baseline required')
    source = ROOT / 'source/v13b'
    profiles = [json.loads((source / name).read_text('utf8')) for name in
                ('dialogue.json', 'descriptions.json', 'large_ui.json')]
    from dialogue_tokens import units
    for profile in profiles:
        if profile['source_sha256'] != BASE_SHA256:
            raise ValueError('Profile baseline identity mismatch')
        for row in profile['writes']:
            before, after = bytes.fromhex(row['expected_hex']), bytes.fromhex(row['payload_hex'])
            if row['offset'] == 0xca588:
                if (before, after) != (bytes.fromhex('02d8'), bytes.fromhex('c046')):
                    raise ValueError('Unexpected skill TP separator patch')
                continue
            for offset, token in units(before):
                replacement = after[offset:offset+len(token)]
                allowed = {token}
                if token == b'\x81\x40':
                    allowed.add(b'\x16\x01')
                elif token == b' ':
                    allowed.add(b'\x17')
                elif token == b'\n':
                    allowed.update((b'\x17', b'\x18'))
                if replacement not in allowed:
                    raise ValueError(f'Non-layout text mutation at {row["offset"]+offset:#x}')
    result = apply_profiles(base, profiles)
    for row in json.loads((ROOT / 'source/v13a/bindings.json').read_text('utf8')):
        field = int(row['pointer_offset'], 0)
        end = int(row['current_pointer'], 0) - 0x08000000 + row['bytes']
        if result[field:field+4] != base[field:field+4] or result[end] != base[end]:
            raise ValueError('Pointer/terminator changed: ' + row['binding_id'])
    return result


def build(base, toolchain, out):
    from v13b_boot import apply_boot
    from v13b_performance import apply_performance
    from v13b_consumers import apply as apply_consumers
    from v13b_preservation import verify
    from v13b_small_ui import build as apply_small_ui
    from v13b_native_detail import apply as apply_native_detail
    from v13b_small_runtime import apply as apply_small_runtime
    from v13b_numeric_prefix import apply as apply_numeric_prefix
    out.mkdir(parents=True, exist_ok=False)
    result = build_text(base)
    result, boot = apply_boot(result, toolchain, out/'boot')
    result, performance = apply_performance(result, toolchain, out/'performance')
    result, consumers = apply_consumers(result, toolchain, out/'consumers')
    symbols = performance['small_symbols']
    result, small_ui = apply_small_ui(result, toolchain, out/'small-ui', symbols['small_label_print'],
                                     row_cached_tile=symbols['row_cached_tile'], small_composite=symbols['small_composite'])
    result, native_detail = apply_native_detail(result, toolchain, out/'native-detail')
    result, small_runtime = apply_small_runtime(result, toolchain, out/'small-runtime', small_ui['symbols'])
    result, numeric_prefix = apply_numeric_prefix(result, toolchain, out/'numeric-prefix')
    if len(result) != len(base):
        raise ValueError('ROM growth forbidden')
    preservation = verify(base, result, json.loads((ROOT/'source/v13b/preservation.json').read_text('utf8')))
    return result, dict(boot=boot, performance=performance, consumers=consumers, small_ui=small_ui,
                       native_detail=native_detail, small_runtime=small_runtime,
                       numeric_prefix=numeric_prefix, preservation=preservation,
                       input_sha256=hashlib.sha256(base).hexdigest(),
                       output_sha256=hashlib.sha256(result).hexdigest())
