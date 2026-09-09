"""Bounded BIOS type-30 resources; original input is never modified."""
import struct


def unpack(data, at, end, expected_size):
    if not 0 <= at <= end - 4 <= len(data) - 4:
        raise ValueError('RLE source extent is invalid')
    header = struct.unpack_from('<I', data, at)[0]
    if header != (expected_size << 8) | 0x30:
        raise ValueError('RLE type or decoded length differs')
    cursor = at + 4
    result = bytearray()
    while len(result) < expected_size:
        if cursor >= end:
            raise ValueError('RLE control exceeds source extent')
        flag = data[cursor]
        cursor += 1
        count = (flag & 127) + 3 if flag & 128 else flag + 1
        if len(result) + count > expected_size:
            raise ValueError('RLE run exceeds decoded extent')
        stored = 1 if flag & 128 else count
        if cursor + stored > end:
            raise ValueError('RLE payload exceeds source extent')
        result.extend(data[cursor:cursor + 1] * count if flag & 128 else data[cursor:cursor + count])
        cursor += stored
    return bytes(result), cursor


def pack_literals(data):
    if not data or len(data) > 0xffffff:
        raise ValueError('Invalid BIOS RLE payload size')
    result = bytearray(struct.pack('<I', (len(data) << 8) | 0x30))
    for start in range(0, len(data), 128):
        block = data[start:start + 128]
        result.append(len(block) - 1)
        result.extend(block)
    return bytes(result)
