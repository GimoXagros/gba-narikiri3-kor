"""Independent 12x16 font-to-4bpp-buffer reference for isolated CPU checks."""
import struct


def color_lut(mode):
    background = 11 if mode else 0
    return bytes([background * 17, background * 16 + 15, 240 + background, 255])


def expected_buffer(rom, positions, mode):
    background = 11 if mode else 0
    result = bytearray([background * 17] * 0xf00)
    for cell_x, cell_y, slot in positions:
        if not 0 <= cell_x < 20 or not 0 <= cell_y < 2:
            raise ValueError('Large glyph exceeds original 240x32 font buffer')
        rows = struct.unpack_from('<16H', rom, 0xddcc4 + slot * 32)
        for row_y, bits in enumerate(rows):
            for col_x in range(12):
                x, y = cell_x * 12 + col_x, cell_y * 16 + row_y
                at = ((y // 8) * 30 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                shift = 4 * (x % 2)
                color = 15 if bits & (1 << col_x) else background
                result[at] = (result[at] & ~(15 << shift)) | (color << shift)
    return bytes(result)
