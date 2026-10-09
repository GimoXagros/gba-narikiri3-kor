.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global pixel_even, pixel_odd, pixel_kernel_end

@ Drop-in replacements for original 080011A8 and 080012E0 entry points.
@ r0: 32-byte-aligned destination tile, r1: 16 source halfwords.
@ The 4-byte color lookup at 03001464 remains live and mode-dependent.
@ Both entries preserve r4-r10, SP and the unchanged 08001414 caller.
.thumb_func
pixel_even:
    push {r4-r7, lr}
    sub sp, #8
    movs r6, r0
    movs r7, r0
    adds r7, #32
    ldr r3, =0x03001464
    movs r0, r1
    adds r0, #16
    str r0, [sp]
    adds r0, #16
    str r0, [sp, #4]
even_row:
    ldrh r4, [r1]
    bl expand_four
    str r5, [r6]
    bl expand_four
    ldr r2, [r7]
    lsrs r2, #16
    lsls r2, #16
    orrs r5, r2
    str r5, [r7]
    adds r1, #2
    adds r6, #4
    adds r7, #4
    ldr r2, [sp]
    cmp r1, r2
    bne even_continue
    ldr r2, =0x3a0
    adds r6, r2
    adds r7, r2
even_continue:
    ldr r2, [sp, #4]
    cmp r1, r2
    bne even_row
    add sp, #8
    pop {r4-r7}
    pop {r0}
    mov lr, r0
    bx r0

@ r4 consumes four successive two-bit indices. r5 receives 4 LUT bytes.
.thumb_func
expand_four:
    movs r0, #3
    ands r0, r4
    ldrb r5, [r3, r0]
    lsrs r4, #2
    movs r0, #3
    ands r0, r4
    ldrb r2, [r3, r0]
    lsls r2, #8
    orrs r5, r2
    lsrs r4, #2
    movs r0, #3
    ands r0, r4
    ldrb r2, [r3, r0]
    lsls r2, #16
    orrs r5, r2
    lsrs r4, #2
    movs r0, #3
    ands r0, r4
    ldrb r2, [r3, r0]
    lsls r2, #24
    orrs r5, r2
    lsrs r4, #2
    bx lr

@ r0 receives two LUT bytes; r4 consumes four source bits.
.thumb_func
expand_two:
    movs r0, #3
    ands r0, r4
    ldrb r0, [r3, r0]
    lsrs r4, #2
    movs r2, #3
    ands r2, r4
    ldrb r2, [r3, r2]
    lsls r2, #8
    orrs r0, r2
    lsrs r4, #2
    bx lr
.ltorg

@ Fixed original second entry. The gap contains only new code and padding.
.org 0x138, 0
.thumb_func
pixel_odd:
    push {r4-r7, lr}
    sub sp, #8
    movs r6, r0
    movs r7, r0
    adds r7, #32
    ldr r3, =0x03001464
    movs r0, r1
    adds r0, #16
    str r0, [sp]
    adds r0, #16
    str r0, [sp, #4]
odd_row:
    ldrh r4, [r1]
    bl expand_two
    ldr r2, [r6]
    lsls r2, #16
    lsrs r2, #16
    lsls r0, #16
    orrs r0, r2
    str r0, [r6]
    bl expand_four
    str r5, [r7]
    adds r1, #2
    adds r6, #4
    adds r7, #4
    ldr r2, [sp]
    cmp r1, r2
    bne odd_continue
    ldr r2, =0x3a0
    adds r6, r2
    adds r7, r2
odd_continue:
    ldr r2, [sp, #4]
    cmp r1, r2
    bne odd_row
    add sp, #8
    pop {r4-r7}
    pop {r0}
    mov lr, r0
    bx r0
.ltorg
.org 0x26c, 0
pixel_kernel_end:
