
.syntax unified
.cpu arm7tdmi
.thumb
.text
.global cursor
.thumb_func
cursor:
 push {r1-r3,lr}
 movs r6,#0x70
 ldr r3,[sp,#20]
 mov r0,r10
 cmp r0,r3
 bne inactive
 ldr r1,=0x03007000
 cmp r3,r1
 blo inactive
 ldr r1,=0x03007e00
 cmp r3,r1
 bhs inactive
 ldr r0,[r3,#56]
 ldr r1,=0x51b34ac7
 cmp r0,r1
 bne inactive
 ldr r0,[sp,#24]
 cmp r0,#1
 beq scan
 ldr r0,[r3,#20]
 cmp r0,#0x70
 blo scan
 cmp r0,#0xee
 bhs exhausted
 movs r6,r0
 b scan
inactive:
 movs r3,#0
scan:
 movs r0,r6
 subs r0,#0x70
 lsrs r1,r0,#3
 movs r2,#7
 ands r0,r2
 movs r2,#1
 lsls r2,r0
 ldrb r0,[r7,r1]
 tst r0,r2
 beq selected
 adds r6,#1
 cmp r6,#0xae
 bne gap
 adds r6,#2
gap:
 cmp r6,#0xee
 blo scan
exhausted:
 movs r6,#0xed
 b done
selected:
 adds r0,r6,#1
 cmp r0,#0xae
 bne store
 adds r0,#2
store:
 cmp r3,#0
 beq upload_now
 str r0,[r3,#20]
upload_now:
 pop {r1-r3}
 pop {r0}
 ldr r0,=0x08fbc01d
 bx r0
done:
 movs r0,r6
 pop {r1-r3,pc}
.ltorg
