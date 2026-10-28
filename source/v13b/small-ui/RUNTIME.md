# Small-list redraw implementation

The source build retains the 16 MiB ROM size, all stored text locations, and all
stored text pointers. It changes selected rendering code, not the name encoding
or glyph width. Original Korean glyphs remain 8 pixels wide; separator display
uses the existing half-width policy.

`small_ui.s` dispatches the exact encyclopedia name caller `080CD817` to
`runtime_stream.s`. The stream verifies species ID 0–211 and equality with the
immutable name pointer in the original species table. ASCII, control-bearing,
unsupported, oversized, and mismatched-pointer inputs use `small_ui_render`.
The builder certifies all immutable names accepted by the fast parser against
the Hangul mapping and verifies that their glyph data is nonempty.

The fast route validates the shared context once per name, rasterizes eight
rows through a nibble lookup table, and uploads aligned glyphs directly through
the scoped allocator. Shifted glyphs preserve the neighboring half-tile. It
retains live-tile pinning, palette composition, and the existing allocator's
full-pool match/fallback behavior. If allocation or final composition fails,
the general renderer redraws the original name from the unchanged descriptor.
The descriptor cursor is committed only after the complete stream succeeds.

The name stream omits the generic formatter's temporary copy of the name.
The exact callback returns directly; the next row formats fresh output before
reading that scratch. This is a scoped lifetime result, not a claim that all
formatter RAM is globally dead. The interrupt-visible tilemap dirty byte
`03001461` remains written. The separately implemented numeric-prefix path
preserves its formatter scratch and dirty-byte side effects.

## Reserved code ranges

| ROM offset | Capacity | Purpose |
| --- | ---: | --- |
| FBBB2C | 532 | Immutable-name stream |
| FBBD40 | 192 | Validated-context tile allocation |
| FBBE00 | 224 | Bounded rectangle clear and caller gateway |
| FBBEE0 | 144 | Reserved for numeric-prefix drawing |
| FBCB9C | 220 | Eight-row glyph raster helper |
| FBCC78 | 180 | Pin scan helper |
| FBCF64 | 156 | Reserved tail of fast-match allocation for numeric guard |
| FBD280 | 212 | Tail of generic-guard allocation for allocation cursor |

The boot decoder, native detail helper, existing fast-match entry, and font
payload are outside these writes. The applier checks empty reclaimed ranges,
recognizes the exact inherited bytes in reused allocation tails, checks every
hook's original instructions, and checks Thumb branch range before writing.
It never searches arbitrary padding for code space.

The pin scan skips a word pair only when both tile IDs have bit 8 set and the
atlas base is zero. Such IDs cannot belong to the 0x70–0xED cache pool. Other
bases and mixed pairs take the existing precise per-entry path. The allocation
cursor is used only with the validated shared stack context and resets when
the pin map is refreshed; live tiles are never reclaimed by that shortcut.

## Verification boundaries

Independent checks cover the 212 immutable monster names in both atlas modes,
RAM/ASCII/control fallbacks, register/stack/descriptor preservation, live-pool
pressure, and full controller-driven item/monster list traces. A separate
654-case CPU oracle compares the native clear against the bounded clear.
Final release claims must bind the exact rebuilt ROM hash to the final runtime
and packaging reports. CPU fixtures and earlier prototype timings alone do
not establish a release or hardware result.

The isolated “five or more Hangul glyphs” batch-route experiment was not adopted:
the native list already shared its cache context, and routing added instructions
without improving measured frame counts. The adopted implementation therefore
does not infer a universal performance crossover from string length.
