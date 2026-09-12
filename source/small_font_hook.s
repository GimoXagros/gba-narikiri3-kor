.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global small_font_hook
.global cached_tile
.type small_font_hook,%function
.thumb_func
small_font_hook:
    @ Installed at 08001A38. r4=window, r5=current byte, r6=palette,
    @ r7=kana mode, [sp]=current source pointer. No relocated instructions.
    cmp r5, #0x88
    blo check_kana
    cmp r5, #0x95
    bhi check_kana
    @ Wansung range validation uses the nonempty table entry below.
    b hangul
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
    ldr r1, =0x09001000
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
    ldr r1, =0x03000054
    ldr r1, [r1]
    movs r2, #0x80
    lsls r2, #2
    adds r1, r2
    ldrb r1, [r1] @ background from current space tile
    movs r2, #15
    ands r1, r2
    movs r5, #0
    mov r2, sp
row_loop:
    ldrb r3, [r0, r5]
    movs r6, #0
    movs r7, #8
pixel_loop:
    lsls r6, #4
    lsls r3, #1
    mov r12, r0
    movs r0, #0x80
    lsls r0, #1
    tst r3, r0
    beq background
    movs r0, #15
    orrs r6, r0
    b pixel_done
background:
    orrs r6, r1
pixel_done:
    mov r0, r12
    subs r7, #1
    bne pixel_loop
    stmia r2!, {r6}
    adds r5, #1
    cmp r5, #8
    blo row_loop
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
    ldr r1, =0x03001462
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
    push {lr}
    bl window_cell
    lsls r2, r6, #12
    orrs r0, r2
    strh r0, [r1]
    pop {r1}
    bx r1
.thumb_func
window_cell:
    @ r1=the exact destination shadow cell; r0 (glyph/tile ID) is retained.
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
    sub sp, #36
    str r1, [sp, #32]
    movs r4, r0
    ldr r0, =0x03000054
    ldr r5, [r0]
    movs r6, #0x70
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
    @ Mark all 256 atlas-relative IDs currently in the BG0 shadow map.
    mov r0, sp
    movs r1, #0
    movs r2, #8
clear_used:
    stmia r0!, {r1}
    subs r2, #1
    bne clear_used
    ldr r0, =0x03000060
    ldr r1, =0x03000058
    ldr r7, [r1]
    movs r6, #0x80
    lsls r6, #4
    adds r6, r0
pin_loop:
    ldr r1, [sp, #32]
    cmp r0, r1
    beq next_pin
    ldrh r1, [r0]
    lsls r1, #22
    lsrs r1, #22
    subs r1, r7
    cmp r1, #255
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
    cmp r0, r6
    blo pin_loop
    movs r6, #0x70
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
    cmp r6, #0xae
    bne free_gap
    adds r6, #2
free_gap:
    cmp r6, #0xee
    blo free_slot
    @ Development-only visible exhaustion marker '?'. Release is blocked
    @ until all relevant screen working sets are independently bounded.
    movs r6, #0x2f
    b found
upload:
    lsls r0, r6, #5
    adds r0, r5
    movs r1, #0
copy_word:
    ldr r2, [r4, r1]
    str r2, [r0, r1]
    adds r1, #4
    cmp r1, #32
    blo copy_word
found:
    ldr r0, =0x03000058
    ldr r0, [r0]
    adds r0, r6
    add sp, #36
    pop {r4-r7}
    pop {r1}
    bx r1
.ltorg
