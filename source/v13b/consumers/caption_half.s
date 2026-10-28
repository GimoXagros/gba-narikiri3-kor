.syntax unified
.cpu arm7tdmi
.thumb
.section .caption,"ax"
.global caption_half_build
.thumb_func
caption_half_build:
 push {r4-r7,lr}
 sub sp,#4
 adds r0,#4
 str r0,[sp]
 movs r4,r0
 movs r5,r1
 movs r6,#0
 movs r7,#0
caption_loop:
 ldrb r0,[r5]
 cmp r0,#0
 beq caption_end
 movs r0,r5
 movs r1,r6
 bl width_bridge
 adds r7,#1
 cmp r2,#6
 beq copy_half
 adds r7,#1
 ldrb r0,[r5]
 strb r0,[r4]
 adds r4,#1
 adds r5,#1
 cmp r0,#128
 blo next
 ldrb r0,[r5]
 strb r0,[r4]
 adds r4,#1
 adds r5,#1
 b next
copy_half:
 ldrb r0,[r5]
 adds r5,#1
 movs r1,#23
 cmp r0,#128
 blo store_half
 movs r1,#22
 strb r1,[r4]
 adds r4,#1
 movs r1,#1
 adds r5,#1
store_half:
 strb r1,[r4]
 adds r4,#1
next:
 adds r6,#1
 b caption_loop
caption_end:
 strb r0,[r4]
 movs r1,#38
 subs r1,r1,r7
 asrs r1,#1
 cmp r1,#0
 ble caption_return
 ldr r2,[sp]
shift:
 ldrb r0,[r4]
 strb r0,[r4,r1]
 subs r4,#1
 cmp r4,r2
 bhs shift
 movs r0,#23
fill:
 strb r0,[r2]
 adds r2,#1
 subs r1,#1
 bne fill
caption_return:
 add sp,#4
 pop {r4-r7}
 pop {r0}
 bx r0
width_bridge:
 ldr r3,=0x08e7304d
 bx r3
.ltorg
