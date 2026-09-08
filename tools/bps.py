"""Minimal BPS1 encoder/decoder using SourceRead and TargetRead commands."""

from __future__ import annotations

import struct
import zlib


class BpsError(ValueError):
    """Raised when a BPS patch is invalid or does not match its source."""


def _encode_number(value: int) -> bytes:
    if value < 0:
        raise BpsError("BPS numbers cannot be negative")
    output = bytearray()
    while True:
        current = value & 0x7F
        value >>= 7
        if value == 0:
            output.append(current | 0x80)
            return bytes(output)
        output.append(current)
        value -= 1


def _decode_number(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    shift = 1
    while True:
        if position >= len(data):
            raise BpsError("truncated BPS variable-length number")
        current = data[position]
        position += 1
        value += (current & 0x7F) * shift
        if current & 0x80:
            return value, position
        shift <<= 7
        value += shift


def _command(length: int, action: int) -> bytes:
    if length <= 0 or action not in (0, 1):
        raise BpsError("invalid BPS command")
    return _encode_number(((length - 1) << 2) | action)


def create_bps(source: bytes, target: bytes, metadata: bytes = b"") -> bytes:
    patch = bytearray(b"BPS1")
    patch.extend(_encode_number(len(source)))
    patch.extend(_encode_number(len(target)))
    patch.extend(_encode_number(len(metadata)))
    patch.extend(metadata)

    position = 0
    while position < len(target):
        same = position < len(source) and source[position] == target[position]
        end = position + 1
        while end < len(target) and (end < len(source) and source[end] == target[end]) == same:
            end += 1
        length = end - position
        if same:
            patch.extend(_command(length, 0))  # SourceRead
        else:
            patch.extend(_command(length, 1))  # TargetRead
            patch.extend(target[position:end])
        position = end

    patch.extend(struct.pack("<I", zlib.crc32(source) & 0xFFFFFFFF))
    patch.extend(struct.pack("<I", zlib.crc32(target) & 0xFFFFFFFF))
    patch.extend(struct.pack("<I", zlib.crc32(patch) & 0xFFFFFFFF))
    return bytes(patch)


def apply_bps(source: bytes, patch: bytes) -> bytes:
    if not patch.startswith(b"BPS1") or len(patch) < 16:
        raise BpsError("invalid or truncated BPS patch")
    expected_patch_crc = struct.unpack_from("<I", patch, len(patch) - 4)[0]
    if zlib.crc32(patch[:-4]) & 0xFFFFFFFF != expected_patch_crc:
        raise BpsError("BPS patch CRC32 mismatch")

    position = 4
    source_size, position = _decode_number(patch, position)
    target_size, position = _decode_number(patch, position)
    metadata_size, position = _decode_number(patch, position)
    if source_size != len(source):
        raise BpsError("BPS source size mismatch")
    position += metadata_size
    command_end = len(patch) - 12
    if position > command_end:
        raise BpsError("truncated BPS metadata")

    output = bytearray()
    while len(output) < target_size:
        command, position = _decode_number(patch, position)
        action = command & 3
        length = (command >> 2) + 1
        if action == 0:
            start = len(output)
            end = start + length
            if end > len(source):
                raise BpsError("SourceRead exceeds source")
            output.extend(source[start:end])
        elif action == 1:
            end = position + length
            if end > command_end:
                raise BpsError("TargetRead exceeds patch data")
            output.extend(patch[position:end])
            position = end
        else:
            raise BpsError("unsupported BPS copy action in minimal decoder")
    if len(output) != target_size or position != command_end:
        raise BpsError("BPS command stream length mismatch")

    expected_source_crc, expected_target_crc = struct.unpack_from("<II", patch, command_end)
    if zlib.crc32(source) & 0xFFFFFFFF != expected_source_crc:
        raise BpsError("BPS source CRC32 mismatch")
    result = bytes(output)
    if zlib.crc32(result) & 0xFFFFFFFF != expected_target_crc:
        raise BpsError("BPS target CRC32 mismatch")
    return result
