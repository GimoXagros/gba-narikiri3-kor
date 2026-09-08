.syntax unified
.cpu arm7tdmi
.thumb
.text
.global name_import
.thumb_func
name_import:
    push {r4,r5,r6,r7,lr}
    sub sp,#4
    movs r5,r0
    movs r4,r1
    movs r1,#20
    ldr r3,clear
    bl call_r3
    movs r6,#0
    movs r7,#0
    strb r7,[r5,#21]
next:
    ldrb r2,[r4]
    cmp r2,#0
    beq done
    cmp r2,#18
    bne character
    movs r0,#1
    subs r6,r0,r6
    adds r4,#1
    b next
character:
    lsls r0,r7,#2
    adds r1,r5,r0
    cmp r2,#0x80
    blo legacy
    cmp r2,#0x9f
    bls doublebyte
    cmp r2,#0xdf
    bhi doublebyte
legacy:
    cmp r6,#0
    beq copy_legacy
    movs r0,#18
    strb r0,[r1]
    adds r1,#1
copy_legacy:
    strb r2,[r1]
    adds r1,#1
    adds r4,#1
    ldrb r2,[r4]
    cmp r2,#222
    beq mark
    cmp r2,#223
    bne counted
mark:
    strb r2,[r1]
    adds r4,#1
    b counted
doublebyte:
    ldrb r0,[r4,#1]
    cmp r0,#0
    beq done
    strb r2,[r1]
    strb r0,[r1,#1]
    adds r4,#2
counted:
    adds r7,#1
    strb r7,[r5,#21]
    cmp r7,#5
    blo next
done:
    movs r0,r5
    ldr r3,redraw
    bl call_r3
    add sp,#4
    pop {r4,r5,r6,r7}
    pop {r0}
    bx r0
call_r3:
    bx r3
.balign 4,0
clear: .word 0x08004975
redraw: .word 0x080d6435
