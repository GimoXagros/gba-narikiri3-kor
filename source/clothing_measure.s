.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global clothing_measure
.thumb_func
clothing_measure:
    movs r2, #0
1:
    ldrb r1, [r0]
    cmp r1, #0
    beq 5f
    cmp r1, #0x88
    blo 3f
    cmp r1, #0x94
    bhi 3f
    ldrb r3, [r0, #1]
    cmp r3, #0x40
    blo 3f
    cmp r3, #0xfc
    bhi 3f
    cmp r3, #0x7f
    beq 3f
    cmp r1, #0x88
    bne 2f
    cmp r3, #0x9f
    blo 3f
2:
    adds r2, #1
    adds r0, #2
    b 1b
3:
    @ Preserve the original single-byte and dakuten width convention.
    cmp r1, #0x1f
    bls 4f
    cmp r1, #0xde
    beq 4f
    adds r2, #1
4:
    adds r0, #1
    b 1b
5:
    adds r0, r2, #0
    bx lr
