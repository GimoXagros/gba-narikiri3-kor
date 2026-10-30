.syntax unified
.cpu arm7tdmi
.thumb
.text
.global fast_match
.thumb_func
fast_match:
 push {r4-r7,lr}
 movs r4,r0
 movs r5,r1
 movs r6,#0x70
slot:
 lsls r0,r6,#5
 adds r0,r5
 ldr r1,[r0,#12]
 ldr r2,[r4,#12]
 cmp r1,r2
 bne next
 ldr r1,[r0,#16]
 ldr r2,[r4,#16]
 cmp r1,r2
 bne next
 ldr r1,[r0,#8]
 ldr r2,[r4,#8]
 cmp r1,r2
 bne next
 ldr r1,[r0,#20]
 ldr r2,[r4,#20]
 cmp r1,r2
 bne next
 ldr r1,[r0,#4]
 ldr r2,[r4,#4]
 cmp r1,r2
 bne next
 ldr r1,[r0,#24]
 ldr r2,[r4,#24]
 cmp r1,r2
 bne next
 ldr r1,[r0,#0]
 ldr r2,[r4,#0]
 cmp r1,r2
 bne next
 ldr r1,[r0,#28]
 ldr r2,[r4,#28]
 cmp r1,r2
 bne next
 b done
next:
 adds r6,#1
 cmp r6,#0xae
 bne no_gap
 adds r6,#2
no_gap:
 cmp r6,#0xee
 blo slot
done:
 movs r0,r6
 pop {r4-r7}
 pop {r1}
 bx r1
