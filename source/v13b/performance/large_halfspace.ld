SECTIONS {
 .support 0x08001244 : { *(.support) }
 .glyph 0x08001338 : { *(.glyph) }
 .print 0x080014F4 : { *(.print) }
 /DISCARD/ : { *(.ARM.attributes) }
 ASSERT(SIZEOF(.support) <= 0x9C, "support exceeds source-owned padding1244..12E0")
 ASSERT(SIZEOF(.glyph) <= 0xDC, "glyph exceeds source-owned padding1338..1414")
 ASSERT(SIZEOF(.print) <= 0x14C, "print exceeds original14F4..1640")
}
