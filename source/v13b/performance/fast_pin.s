.syntax unified
.cpu arm7tdmi
.thumb
.text
.global fast_pin
.thumb_func
fast_pin:

pin_pair:
    movs r3,#15
    tst r0,r3
    bne pin_word
    ldr r1,[r0]
    ldr r2,[r0,#4]
    orrs r1,r2
    ldr r2,[r0,#8]
    orrs r1,r2
    ldr r2,[r0,#12]
    orrs r1,r2
    tst r1,r5
    bne pin_word
    adds r0,#16
    ldr r3,=0x03000560
    cmp r0,r3
    blo pin_pair
    b pin_done
pin_word:
    ldr r1,[r0]
    tst r1,r5
    beq zero_pair
pin_single:
    cmp r0,r4
    beq next_pin
    ldrh r1,[r0]
    lsls r1,#22
    lsrs r1,#22
    subs r1,r6
    cmp r1,#0x7d
    bhi next_pin
    lsrs r2,r1,#3
    movs r3,#7
    ands r1,r3
    movs r3,#1
    lsls r3,r1
    ldrb r1,[r7,r2]
    orrs r1,r3
    strb r1,[r7,r2]
next_pin:
    adds r0,#2
    lsls r1,r0,#30
    bmi pin_single
    ldr r3,=0x03000560
    cmp r0,r3
    blo pin_pair
    b pin_done
zero_pair:
    adds r0,#4
    ldr r3,=0x03000560
    cmp r0,r3
    blo pin_pair

pin_done:
    bx lr
.ltorg
