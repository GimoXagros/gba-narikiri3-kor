.syntax unified
.cpu arm7tdmi
.thumb
.text
.global fast_halfspace_glyph
.thumb_func
fast_halfspace_glyph:
 push {r4-r7,lr}
 sub sp,#28
 str r3,[sp,#24]
 lsls r2,#5
 ldr r4,=0x080ddcc4
 adds r4,r2
 movs r2,#240
 muls r1,r2
 lsls r1,#3
 lsrs r2,r0,#3
 lsls r2,#5
 adds r1,r2
 movs r2,#7
 ands r0,r2
 lsrs r0,#1
 adds r1,r0
 ldr r5,=0x03000560
 adds r5,r1
 movs r1,#0
 str r1,[sp]
 adds r1,#1
 cmp r0,#3
 bne offset1
 adds r1,#28
offset1:
 str r1,[sp,#4]
 adds r1,#1
 cmp r0,#2
 bne offset2
 adds r1,#28
offset2:
 str r1,[sp,#8]
 adds r1,#1
 cmp r0,#1
 bne offset3
 adds r1,#28
offset3:
 str r1,[sp,#12]
 adds r1,#1
 cmp r0,#0
 bne offset4
 adds r1,#28
offset4:
 str r1,[sp,#16]
 adds r1,#1
 cmp r0,#3
 bne offset5
 adds r1,#28
offset5:
 str r1,[sp,#20]
 ldr r6,=0x03001464
 movs r7,#16
row:
 ldrh r0,[r4]
 adds r4,#2
 movs r1,#3
 ands r1,r0
 ldrb r1,[r6,r1]
 ldr r2,[sp,#0]
 strb r1,[r5,r2]
 lsrs r0,#2
 movs r1,#3
 ands r1,r0
 ldrb r1,[r6,r1]
 ldr r2,[sp,#4]
 strb r1,[r5,r2]
 lsrs r0,#2
 movs r1,#3
 ands r1,r0
 ldrb r1,[r6,r1]
 ldr r2,[sp,#8]
 strb r1,[r5,r2]
 lsrs r0,#2
 ldr r1,[sp,#24]
 cmp r1,#12
 bne next_row
 movs r1,#3
 ands r1,r0
 ldrb r1,[r6,r1]
 ldr r2,[sp,#12]
 strb r1,[r5,r2]
 lsrs r0,#2
 movs r1,#3
 ands r1,r0
 ldrb r1,[r6,r1]
 ldr r2,[sp,#16]
 strb r1,[r5,r2]
 lsrs r0,#2
 movs r1,#3
 ands r1,r0
 ldrb r1,[r6,r1]
 ldr r2,[sp,#20]
 strb r1,[r5,r2]
 lsrs r0,#2
next_row:
 adds r5,#4
 subs r7,#1
 beq done
 cmp r7,#8
 bne row
 ldr r0,=0x3a0
 adds r5,r0
 b row
done:
 add sp,#28
 pop {r4-r7}
 pop {r0}
 bx r0
.ltorg
