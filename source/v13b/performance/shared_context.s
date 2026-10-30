.syntax unified
.cpu arm7tdmi
.thumb
.text
.global redraw_enter,redraw_exit,cache_context_enter
.thumb_func
redraw_enter:
 push {r4-r7,lr}
 mov r7,r9
 mov r6,r8
 push {r6,r7}
 sub sp,#64
 mov r3,r10
 str r3,[sp,#60]
 mov r3,sp
 mov r10,r3
 movs r3,#0
 str r3,[sp]
 str r3,[sp,#20]
 str r3,[sp,#24]
 str r3,[sp,#28]
 str r3,[sp,#32]
 str r3,[sp,#36]
 str r3,[sp,#40]
 str r3,[sp,#44]
 str r3,[sp,#48]
 str r3,[sp,#56]
 ldr r3,[r0,#20]
 ldr r2,=0x080cadd1
 cmp r3,r2
 beq set_marker
 ldr r2,=0x080cd7d5
 cmp r3,r2
 bne no_marker
set_marker:
 ldr r3,=0x51b34ac7
 str r3,[sp,#56]
no_marker:
 ldr r3,=0x08004491
 bx r3
.thumb_func
redraw_exit:
 ldr r3,[sp,#60]
 mov r10,r3
 add sp,#64
 pop {r3,r4}
 mov r8,r3
 mov r9,r4
 pop {r4-r7}
 pop {r0}
 bx r0
.thumb_func
cache_context_enter:
 movs r3,r2
 adds r3,#72
 cmp r3,r10
 bne local_context
 subs r3,#4
 ldr r3,[r3]
 push {r0}
 ldr r0,=0x080044e5
 cmp r0,r3
 pop {r0}
 bne local_context
 mov r2,r10
local_context:
 push {r4-r7,lr}
 sub sp,#12
 str r1,[sp]
 str r2,[sp,#4]
 ldr r3,=0x08fbbf79
 bx r3
.ltorg
