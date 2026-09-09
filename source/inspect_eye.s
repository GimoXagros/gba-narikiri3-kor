.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global inspect_eye_text
.thumb_func
inspect_eye_text:
    @ Dedicated 16x16 affine byte-map consumer, not the regular 4bpp UI.
    @ Resource 440 supplies 240 8bpp tiles at 06008000. The last 16 slots
    @ before 0600C000 are unused by that resource. Assign by visible position,
    @ with no persistent cache or borrowed RAM: title F0..F8, labels F9..FE.
    push {r4-r7, lr}
    sub sp, #8
    movs r6, r0
    movs r7, r1
    movs r4, r2
    ldr r5, map_pointer
    ldr r5, [r5]
    lsls r0, r7, #4
    adds r5, r5, r0
    adds r5, r5, r6
    movs r0, #0
    str r0, [sp]
next_character:
    ldrb r0, [r4]
    cmp r0, #0
    beq done
    cmp r0, #0x12
    bne check_bounds
    ldr r0, [sp]
    movs r1, #1
    eors r0, r1
    str r0, [sp]
    adds r4, #1
    b next_character
check_bounds:
    cmp r6, #14
    bhs done
    cmp r7, #8
    bhs done
    cmp r0, #0x88
    blo legacy_character
    cmp r0, #0x94
    bhi legacy_character
    ldrb r1, [r4, #1]
    cmp r1, #0x40
    blo legacy_character
    cmp r1, #0xfc
    bhi legacy_character
    cmp r1, #0x7f
    beq legacy_character
    cmp r0, #0x88
    bne hangul_character
    cmp r1, #0x9f
    blo legacy_character
hangul_character:
    subs r0, #0x85
    movs r2, #192
    muls r0, r2
    adds r0, r0, r1
    subs r0, #0x40
    lsls r0, r0, #3
    ldr r1, font_pointer
    adds r0, r0, r1
    @ Only the title and three two-letter labels contain Hangul.
    cmp r6, #1
    blo done
    cmp r7, #0
    bne label_slot
    cmp r6, #9
    bhi done
    movs r1, #0xef
    b got_slot
label_slot:
    cmp r6, #2
    bhi done
    cmp r7, #3
    beq attack_slot
    cmp r7, #5
    beq resistance_slot
    cmp r7, #7
    bne done
    movs r1, #0xfc
    b got_slot
attack_slot:
    movs r1, #0xf8
    b got_slot
resistance_slot:
    movs r1, #0xfa
got_slot:
    adds r1, r1, r6
    str r1, [sp, #4]
    lsls r1, r1, #6
    ldr r2, tile_pointer
    adds r1, r1, r2
    bl draw_hangul
    ldr r0, [sp, #4]
    strb r0, [r5]
    adds r4, #2
    b advance_cell
legacy_character:
    ldr r1, [sp]
    cmp r1, #0
    beq legacy_index
    adds r0, #0x40
legacy_index:
    lsls r0, r0, #1
    ldr r1, legacy_lookup
    adds r1, r1, r0
    movs r0, #0
    ldrsh r0, [r1, r0]
    ldr r1, resource_pointer
    ldr r1, [r1]
    adds r1, r1, r0
    ldrb r0, [r1]
    strb r0, [r5]
    adds r4, #1
advance_cell:
    adds r5, #1
    adds r6, #1
    b next_character
done:
    add sp, #8
    pop {r4-r7}
    pop {r0}
    bx r0
.align 2
map_pointer: .word 0x02000104
resource_pointer: .word 0x020000f8
font_pointer: .word 0x09001000
tile_pointer: .word 0x06008000
legacy_lookup: .word 0x087c1938

.thumb_func
draw_hangul:
    @ GBA VRAM requires halfword/word stores, never byte stores.
    push {r4-r7, lr}
    movs r4, r0
    movs r5, r1
    movs r6, #8
next_row:
    ldrb r7, [r4]
    adds r4, #1
    movs r2, #4
next_pair:
    movs r0, #0xa1
    movs r1, #1
    tst r7, r1
    beq first_pixel_ready
    movs r0, #0xaf
first_pixel_ready:
    lsrs r7, r7, #1
    movs r3, #0xa1
    tst r7, r1
    beq second_pixel_ready
    movs r3, #0xaf
second_pixel_ready:
    lsls r3, r3, #8
    orrs r0, r3
    strh r0, [r5]
    adds r5, #2
    lsrs r7, r7, #1
    subs r2, #1
    bne next_pair
    subs r6, #1
    bne next_row
    pop {r4-r7}
    pop {r0}
    bx r0
