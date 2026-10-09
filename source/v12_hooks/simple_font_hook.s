.syntax unified
.cpu arm7tdmi
.thumb
.text
.global simple_font_hook
.type simple_font_hook,%function
.thumb_func
simple_font_hook:
    @ 08001DDC: r2=byte,r3=source,r1=map cell,r4=palette flags.
    @ The simple consumer has no voicing composition or kana controls.
    cmp r2,#0x88
    blo kana_check
    cmp r2,#0x95
    bls hangul
kana_check:
    cmp r2,#0xa1
    blo original
    cmp r2,#0xdd
    bls kana
original:
    movs r0,r2
    subs r0,#0x20
    cmp r0,#0x5e
    bhi original_other
    ldr r0,=0x08001de5
    bx r0
original_other:
    ldr r0,=0x08001df5
    bx r0
hangul:
    movs r0,r2
    subs r0,#0x85
    movs r2,#192
    muls r0,r2
    ldrb r2,[r3,#1]
    adds r0,r2
    subs r0,#0x40
    lsls r0,#3
    ldr r2,=0x09001000
    adds r0,r2
    ldr r2,[r0]
    @ Preserve the current map pointer while validating the glyph entry.
    push {r1}
    ldr r1,[r0,#4]
    orrs r2,r1
    pop {r1}
    beq invalid
    push {r1,r3-r7,lr}
    sub sp,#36
    ldr r1,=0x03000054
    ldr r1,[r1]
    movs r2,#0x80
    lsls r2,#2
    adds r1,r2
    ldrb r1,[r1]
    movs r2,#15
    ands r1,r2
    movs r5,#0
    mov r2,sp
row:
    ldrb r3,[r0,r5]
    movs r6,#0
    movs r7,#8
pixel:
    lsls r6,#4
    lsls r3,#1
    mov r12,r0
    movs r0,#0x80
    lsls r0,#1
    tst r3,r0
    beq background
    movs r0,#15
    orrs r6,r0
    b next_pixel
background:
    orrs r6,r1
next_pixel:
    mov r0,r12
    subs r7,#1
    bne pixel
    stmia r2!,{r6}
    adds r5,#1
    cmp r5,#8
    blo row
    mov r0,sp
    ldr r1,[sp,#36] @ saved destination shadow cell
    bl cached_tile
    movs r2,r0
    add sp,#36
    pop {r1,r3-r7}
    pop {r0}
    mov lr,r0
    adds r3,#1
    b write
invalid:
    ldrb r2,[r3]
    b original
kana:
    push {r1,r3-r7,lr}
    sub sp,#4
    movs r0,r2
    subs r0,#0x30
    lsls r0,#5
    ldr r1,=0x03001462
    ldrb r1,[r1]
    ldr r2,=0x080fbcc4
    cmp r1,#0
    beq atlas
    ldr r2,=0x080fdcc4
atlas:
    adds r0,r2
    ldr r1,[sp,#4] @ saved destination shadow cell
    bl cached_tile
    movs r2,r0
    add sp,#4
    pop {r1,r3-r7}
    pop {r0}
    mov lr,r0
write:
    ldr r0,=0x08001dff
    bx r0
.ltorg
