
.syntax unified
.cpu arm7tdmi
.thumb
.text
.global fast_clear
.thumb_func
fast_clear:
 ldr r1,=0x02000000
 cmp r0,r1
 blo fallback
 ldr r1,=0x0203fff8
 cmp r0,r1
 bls geometry
 ldr r1,=0x03000000
 cmp r0,r1
 blo fallback
 ldr r1,=0x03007ff8
 cmp r0,r1
 bhi fallback
 ldr r1,=0x03000058
 cmp r0,r1
 blo geometry
 ldr r1,=0x03000560
 cmp r0,r1
 blo fallback
geometry:
 movs r1,#0
 ldrsb r1,[r0,r1]
 cmp r1,#0
 blt fallback
 movs r2,#2
 ldrsb r2,[r0,r2]
 cmp r2,#32
 bgt fallback
 cmp r1,r2
 bgt fallback
 movs r1,#1
 ldrsb r1,[r0,r1]
 cmp r1,#0
 blt fallback
 movs r2,#3
 ldrsb r2,[r0,r2]
 cmp r2,#20
 bgt fallback
 cmp r1,r2
 bgt fallback
 push {r4-r7,lr}
 mov r7,r9
 mov r6,r8
 push {r6,r7}
 movs r4,r0
 ldr r1,=0x03001462
 mov r9,r1
 ldrb r2,[r4,#1]
 ldrb r5,[r4,#3]
 ldrb r7,[r4,#2]
 movs r6,#7
 ldrsb r6,[r4,r6]
 lsls r6,#12
 ldr r1,=0x03000058
 ldr r1,[r1]
 adds r1,#0x10
 orrs r6,r1
 cmp r2,r5
 bge cleanup
row:
 ldrb r3,[r4]
 lsls r0,r2,#6
 ldr r1,=0x03000060
 adds r0,r1
 lsls r1,r3,#1
 adds r0,r1
 cmp r3,r7
 bge next
cell:
 strh r6,[r0]
 adds r0,#2
 adds r3,#1
 cmp r3,r7
 blt cell
next:
 adds r2,#1
 cmp r2,r5
 blt row
cleanup:
 ldr r0,=0x080017ff
 bx r0
fallback:
 ldr r3,=0x080017a1
 bx r3
.ltorg

.global clear_gate
.thumb_func
clear_gate:
 ldr r3,[sp]
 ldr r2,=0x080044cd
 cmp r3,r2
 beq clear_dispatch
 ldr r3,=SMALL_NATIVE_FORMAT
 bx r3
clear_dispatch:
 pop {r3}
 mov lr,r3
 pop {r1-r3}
 b fast_clear
.ltorg
