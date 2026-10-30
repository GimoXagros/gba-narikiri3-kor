.syntax unified
.cpu arm7tdmi
.thumb
.section .title,"ax"
.global title_half_measure
.thumb_func
title_half_measure:
 movs r1,#0
measure_loop:
 ldrb r2,[r0]
 adds r0,#1
 cmp r2,#0
 beq measure_done
 cmp r2,#22
 beq marker_two
 cmp r2,#23
 beq half_cell
 cmp r2,#0x80
 blo full_cell
 adds r0,#1
full_cell:
 adds r1,#1
half_cell:
 adds r1,#1
 b measure_loop
marker_two:
 adds r0,#1
 b half_cell
measure_done:
 lsls r0,r1,#1
 adds r1,r1,r0
 ldr r3,=0x08008de5
 bx r3
.ltorg
