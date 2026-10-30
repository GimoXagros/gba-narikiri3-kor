.syntax unified
.cpu arm7tdmi
.thumb
.section .normalize,"ax"
.global normalize_large_spaces
.thumb_func
normalize_large_spaces:
 push {r0,lr}
loop:
 ldrb r1,[r0]
 cmp r1,#0
 beq done
 cmp r1,#32
 bne multi
 movs r1,#23
 strb r1,[r0]
multi:
 adds r0,#1
 cmp r1,#0x80
 blo loop
 ldrb r2,[r0]
 cmp r1,#0x81
 bne advance
 cmp r2,#0x40
 bne advance
 movs r1,#1
 strb r1,[r0]
 subs r0,#1
 movs r1,#22
 strb r1,[r0]
 adds r0,#1
advance:
 adds r0,#1
 b loop
done:
 pop {r0,r1}
 bx r1
.section .mission,"ax"
.global mission_large_half
.thumb_func
mission_large_half:
 movs r4,r0
 bl normalize_large_spaces
 ldr r3,=0x08001661
 bl call_r3
 movs r0,r4
 ldr r3,=0x08003629
 bl call_r3
 ldr r3,=0x080c61fb
 bx r3
call_r3:
 bx r3
.ltorg
