.syntax unified
.cpu arm7tdmi
.thumb
.text
.global skill_half_display
.thumb_func
skill_half_display:
 push {lr}
 sub sp,#64
 mov r1,sp
copy:
 ldrb r2,[r0]
 adds r0,#1
 cmp r2,#0
 beq ready
 cmp r2,#32
 bne not_ascii
 movs r2,#23
not_ascii:
 strb r2,[r1]
 adds r1,#1
 cmp r2,#0x80
 blo copy
 ldrb r3,[r0]
 adds r0,#1
 cmp r2,#0x81
 bne trail
 cmp r3,#0x40
 bne trail
 subs r1,#1
 movs r2,#0x16
 strb r2,[r1]
 adds r1,#1
 movs r3,#1
trail:
 strb r3,[r1]
 adds r1,#1
 b copy
ready:
 strb r2,[r1]
 mov r0,sp
 ldr r3,=0x080014f5
 bl call_r3
 add sp,#64
 pop {r3}
 bx r3
call_r3:
 bx r3
.ltorg
