.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global small_font_hook
.global cached_tile
.global hangul_nibble_lut
.global expand_rows_start, expand_rows_end, cache_match_start, cache_match_end, cache_pin_start, cache_pin_end, cached_tile_end
.type small_font_hook,%function
.thumb_func
small_font_hook:
    @ Installed at 08001A38. r4=window, r5=current byte, r6=palette,
    @ r7=kana mode, [sp]=current source pointer. No relocated instructions.
    cmp r5, #0x88
    blo check_kana
    cmp r5, #0x95
    bls hangul
check_kana:
    cmp r5, #0xa0
    blo original_dispatch
    cmp r5, #0xdd
    bls kana
original_dispatch:
    movs r0, r5
    subs r0, #0x20
    cmp r0, #0x5f
    bhi original_other
    ldr r3, =0x08001a41
    bx r3
original_other:
    ldr r3, =0x08001a71
    bx r3
hangul:
    ldr r1, [sp]
    ldrb r1, [r1, #1]
    movs r0, r5
    subs r0, #0x85
    movs r2, #192
    muls r0, r2
    adds r0, r1
    subs r0, #0x40
    lsls r0, #3
    ldr r1, shared_font_1bpp
    adds r0, r1
    ldr r1, [r0]
    ldr r2, [r0, #4]
    orrs r1, r2
    beq original_dispatch
    push {r0-r3,r5-r7,lr}
    sub sp, #32
    movs r0, r4
    ldr r3, =0x080019c9
    bl call_r3
    ldr r0, [sp, #32] @ saved 1bpp glyph source
    ldr r1, shared_vram_base
    ldr r1, [r1]
    movs r2, #0x80
    lsls r2, #2
    adds r1, r2
    ldrb r1, [r1] @ background from current space tile
    movs r2, #15
    ands r1, r2
    ldr r6, shared_nibble_fill
    muls r1, r6 @ replicate background; foreground LUT F overrides every nibble
expand_rows_start:
    bl shared_rows
expand_rows_end:
    mov r0, sp
    bl window_cell
    bl cached_tile
    ldr r6, [sp, #52] @ original palette
    bl write_cell
    ldr r1, [sp, #64]
    adds r1, #1
    str r1, [sp, #64] @ consume the second byte; original loop consumes first
    add sp, #32
    pop {r0-r3,r5-r7}
    pop {r0} @ saved LR; function's own stack still holds its return address
    ldr r3, =0x08001c03
    bx r3
kana:
    push {r0-r3,r5-r7,lr}
    movs r0, r4
    ldr r3, =0x080019c9
    bl call_r3
    movs r0, r5
    subs r0, #0x30
    cmp r5, #0xa6
    blo kana_slot
    cmp r7, #0
    beq kana_slot
    adds r0, #0x40
kana_slot:
    lsls r0, #5
    ldr r1, shared_kana_mode
    ldrb r1, [r1]
    ldr r2, =0x080fbcc4
    cmp r1, #0
    beq kana_source
    ldr r2, =0x080fdcc4
kana_source:
    adds r0, r2
    bl window_cell
    bl cached_tile
    bl write_cell
    pop {r0-r3,r5-r7}
    pop {r0}
    cmp r5, #0xa6
    blo kana_punctuation_return
    ldr r3, =0x08001ae9 @ preserve original dakuten/handakuten handling
    bx r3
kana_punctuation_return:
    ldr r3, =0x08001c03
    bx r3
.thumb_func
call_r3:
    bx r3
.thumb_func
write_cell:
    mov r3, lr
    bl window_cell
    lsls r2, r6, #12
    orrs r0, r2
    strh r0, [r1]
    bx r3
.thumb_func
window_cell:
    @ Signed x/y bytes 4/5; retain r0.
    movs r1, #4
    ldrsb r1, [r4, r1]
    lsls r1, #1
    movs r2, #5
    ldrsb r2, [r4, r2]
    lsls r2, #6
    adds r1, r2
    ldr r2, =0x03000060
    adds r1, r2
    bx lr
.ltorg

@ Content-addressed 124-tile cache; no persistent scratch RAM.
@ Bank 70..AD and B0..ED. AE/AF/EE/EF voicing marks stay fixed.
@ Match is by all 32 pixel bytes. Allocation pins every referenced BG0
@ shadow tile except the cell being replaced. Other references to the old
@ destination tile still pin it, so unrelated glyphs are never evicted.
@ r0=32-byte glyph, r1=destination shadow cell. Returns absolute tile ID.
@ r4-r7 preserved; no state is retained after the current consumer call.
.thumb_func
cached_tile:
    push {r4-r7,lr}
    sub sp, #40
    str r1, [sp, #32]
    movs r4, r0
    ldr r7, =0x03000058
    ldr r7, [r7]
    ldr r0, shared_vram_base
    ldr r5, [r0]
    movs r6, #0x70
cache_match_start:
match_slot:
    lsls r0, r6, #5
    adds r0, r5
    movs r1, #0
match_word:
    ldr r2, [r0, r1]
    ldr r3, [r4, r1]
    cmp r2, r3
    bne next_match
    adds r1, #4
    cmp r1, #32
    blo match_word
    b found
next_match:
    adds r6, #1
    cmp r6, #0xae
    bne after_gap
    adds r6, #2
after_gap:
    cmp r6, #0xee
    blo match_slot
cache_match_end:
    @ Keep destination in r4 during the full shadow scan; retain glyph for upload.
    str r4, [sp, #36]
    ldr r4, [sp, #32]
    @ Mark all 256 atlas-relative IDs currently in the BG0 shadow map.
    mov r0, sp
    movs r1, #0
    movs r2, #4 @ relative bitmap has only 126 bits
clear_used:
    stmia r0!, {r1}
    subs r2, #1
    bne clear_used
    ldr r0, =0x03000060

    @ A pair whose absolute IDs are both below 64 cannot own slots
    @ atlas_base+70..atlas_base+ED for a nonnegative, nonwrapping base.
    ldr r5, =0x03c003c0
    adds r7, #0x70 @ pin comparisons and bitset are tile 70-relative
    movs r6, #0x50 @ Original BG0 shadow is 640 halfwords; large-font bitmap follows.
    lsls r6, #4
    adds r6, r0
cache_pin_start:
pin_loop:
    ldr r1, [r0]
    ands r1, r5
    beq zero_pair
pin_single:
    cmp r0, r4
    beq next_pin
    ldrh r1, [r0]
    lsls r1, #22
    lsrs r1, #22
    subs r1, r7
    cmp r1, #0x7d
    bhi next_pin
    lsrs r2, r1, #3
    movs r3, #7
    ands r1, r3
    movs r3, #1
    lsls r3, r1
    mov r1, sp
    adds r2, r1
    ldrb r1, [r2]
    orrs r1, r3
    strb r1, [r2]
next_pin:
    adds r0, #2
    lsls r1, r0, #30
    bmi pin_single
    cmp r0, r6
    blo pin_loop
    b pin_done
zero_pair:
    adds r0, #4
    cmp r0, r6
    blo pin_loop
pin_done:
cache_pin_end:
    subs r7, #0x70 @ restore atlas base for found path
    movs r6, #0
free_slot:
    lsrs r0, r6, #3
    mov r1, sp
    ldrb r1, [r1, r0]
    movs r0, #7
    ands r0, r6
    movs r2, #1
    lsls r2, r0
    tst r1, r2
    beq upload
    adds r6, #1
    cmp r6, #0x3e
    bne free_gap
    adds r6, #2
free_gap:
    cmp r6, #0x7e
    blo free_slot
    @ Development-only visible exhaustion marker '?'. Release is blocked
    @ until all relevant screen working sets are independently bounded.
    movs r6, #0x2f
    b found
upload:
    adds r6, #0x70
    ldr r4, [sp, #36]
    ldr r5, shared_vram_base
    ldr r5, [r5]
    lsls r0, r6, #5
    adds r0, r5
copy_word:
    ldmia r4!, {r1-r3,r5}
    stmia r0!, {r1-r3,r5}
    ldmia r4!, {r1-r3,r5}
    stmia r0!, {r1-r3,r5}
found:
    adds r0, r7, r6
    add sp, #40
    pop {r4-r7,pc}
cached_tile_end:
.ltorg
    .space 30, 0

.syntax unified
.cpu arm7tdmi
.thumb
.text
.global shared_rows
.type shared_rows,%function
.thumb_func
shared_rows:
    @ Common exact 1bpp nibble expansion for both existing consumers.
    @ r0=source, r1=background nibbles, sp=destination.
    @ r5 exits at eight; r0/r1/r4 are unchanged.
    ldr r7, =hangul_nibble_lut
    movs r5, #0
    mov r2, sp
row:
    ldrb r3, [r0, r5]
    lsls r6, r3, #28
    lsrs r6, #27
    ldrh r6, [r7, r6]
    lsrs r3, #4
    lsls r3, #1
    ldrh r3, [r7, r3]
    lsls r3, #16
    orrs r6, r3
    orrs r6, r1
    stmia r2!, {r6}
    adds r5, #1
    cmp r5, #8
    blo row
    bx lr

.ltorg
.syntax unified
.cpu arm7tdmi
.thumb
.text
.global simple_font_hook
.type simple_font_hook,%function
.thumb_func
simple_font_hook:
    @ 08001DDC: r2=byte,r3=source,r1=map cell,r4=palette flags.
    @ The simple consumer has no voicing composition or simple_kana controls.
    cmp r2,#0x88
    blo simple_kana_check
    cmp r2,#0x95
    bls simple_hangul
simple_kana_check:
    cmp r2,#0xa1
    blo simple_original
    cmp r2,#0xdd
    bls simple_kana
simple_original:
    movs r0,r2
    subs r0,#0x20
    cmp r0,#0x5e
    bhi simple_original_other
    ldr r0,=0x08001de5
    bx r0
simple_original_other:
    ldr r0,=0x08001df5
    bx r0
simple_hangul:
    movs r0,r2
    subs r0,#0x85
    movs r2,#192
    muls r0,r2
    ldrb r2,[r3,#1]
    adds r0,r2
    subs r0,#0x40
    lsls r0,#3
    ldr r2,shared_font_1bpp
    adds r0,r2
    ldr r2,[r0]
    @ Preserve the current map pointer while validating the glyph entry.
    push {r1}
    ldr r1,[r0,#4]
    orrs r2,r1
    pop {r1}
    beq simple_invalid
    push {r1,r3-r7,lr}
    sub sp,#36
    ldr r1,shared_vram_base
    ldr r1,[r1]
    movs r2,#0x80
    lsls r2,#2
    adds r1,r2
    ldrb r1,[r1]
    movs r2,#15
    ands r1,r2
    ldr r6,shared_nibble_fill
    muls r1,r6
    bl shared_rows
    mov r0,sp
    ldr r1,[sp,#36] @ saved destination shadow cell
    bl cached_tile
    movs r2,r0
    add sp,#36
    pop {r1,r3-r7}
    pop {r0}
    mov lr,r0
    adds r3,#1
    b simple_write
simple_invalid:
    ldrb r2,[r3]
    b simple_original
simple_kana:
    push {r1,r3-r7,lr}
    sub sp,#4
    movs r0,r2
    subs r0,#0x30
    lsls r0,#5
    ldr r1,shared_kana_mode
    ldrb r1,[r1]
    ldr r2,=0x080fbcc4
    cmp r1,#0
    beq simple_atlas
    ldr r2,=0x080fdcc4
simple_atlas:
    adds r0,r2
    ldr r1,[sp,#4] @ saved destination shadow cell
    bl cached_tile
    movs r2,r0
    add sp,#4
    pop {r1,r3-r7}
    pop {r0}
    mov lr,r0
simple_write:
    ldr r0,=0x08001dff
    bx r0
.ltorg

.balign 4
hangul_nibble_lut:
    .hword 0x0000,0x000f,0x00f0,0x00ff,0x0f00,0x0f0f,0x0ff0,0x0fff
    .hword 0xf000,0xf00f,0xf0f0,0xf0ff,0xff00,0xff0f,0xfff0,0xffff

.ltorg
.balign 4
.global shared_font_1bpp, shared_vram_base, shared_nibble_fill, shared_kana_mode
shared_font_1bpp:
    .word 0x08fbd354
shared_vram_base:
    .word 0x03000054
shared_nibble_fill:
    .word 0x11111111
shared_kana_mode:
    .word 0x03001462
