.syntax unified
.cpu arm7tdmi
.thumb
.text
.global keyboard_draw
.global keyboard_insert
.thumb_func
keyboard_draw:
    @ Entry replaces D63E0. Preserve the original saved-register frame.
    push {r4,r5,r6,lr}
    cmp r0,#29
    bls valid_page
    movs r0,#0
valid_page:
    movs r6,r0
    @ Header has its own original 18-cell window, global + 650.
    ldr r4,=0x02003380
    ldr r0,[r4]
    ldr r1,=0x650
    adds r0,r1
    ldr r3,=0x080017a1
    bl call_r3
    ldr r0,[r4]
    ldr r1,=0x650
    adds r0,r1
    lsls r2,r6,#2
    ldr r1,=0x090b2400
    ldr r1,[r1,r2]
    ldr r3,=0x08001da9
    bl call_r3
    movs r0,#24
    muls r0,r6
    ldr r5,=0x090b2000
    adds r5,r0
    @ Original clear, six-row render loop, and epilogue.
    ldr r3,=0x080d63ff
    bx r3
.thumb_func
keyboard_insert:
    @ Entry replaces D6470. Slot storage stays 5 x 4 bytes.
    push {r4,lr}
    movs r4,r0
    ldrb r0,[r4,#21]
    cmp r0,#5
    bhs rejected
    ldrb r1,[r4,#22]
    cmp r1,#15
    bhs rejected
    ldrb r2,[r4,#23]
    cmp r2,#6
    bhs rejected
    ldrb r3,[r4,#20]
    cmp r3,#29
    bhi rejected
    lsls r0,#2
    adds r0,r4
    movs r1,r0
    cmp r3,#27
    bhs original_page
    movs r0,#90
    muls r3,r0
    movs r0,#15
    muls r2,r0
    adds r3,r2
    ldrb r0,[r4,#22]
    adds r3,r0
    lsls r3,#1
    ldr r0,=0x090b0000
    ldrh r0,[r0,r3]
    @ Unused cells are zero in the candidate table and do not add a slot.
    cmp r0,#0
    beq rejected
    movs r2,#0
    str r2,[r1]
    strh r0,[r1]
    b counted
original_page:
    @ Original writers assume the selected four-byte slot is empty.
    movs r0,#0
    str r0,[r1]
    cmp r3,#27
    beq ascii_page
    cmp r3,#28
    beq katakana_page
    ldr r3,=0x080d6559
    b original_insert
ascii_page:
    ldr r3,=0x080d6609
    b original_insert
katakana_page:
    ldr r3,=0x080d64b5
original_insert:
    movs r0,r4
    bl call_r3
counted:
    ldr r3,=0x080d64a3
    bx r3
rejected:
    pop {r4}
    pop {r0}
    bx r0
call_r3:
    bx r3
.balign 4,0
.ltorg
