.syntax unified
.cpu arm7tdmi
.thumb
.text
.global first,second
.thumb_func
first:
 ldr r3,=trampoline+1
 b common
.thumb_func
second:
 ldr r3,=0x080cdf55
common:
 push {r4-r7,lr}
 movs r4,r3
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
 ldr r3,=0x51b34ac7
 str r3,[sp,#56]
 bl call_r4
 ldr r3,[sp,#60]
 mov r10,r3
 add sp,#64
 ldr r0,[sp,#16]
 pop {r4-r7}
 pop {r3}
 bx r3
call_r4:
 bx r4
.ltorg


trampoline:
 push {r4-r7,lr}
 mov r7,r10
 mov r6,r9
 mov r5,r8
 ldr r3,=0x080cde01
 bx r3
.ltorg
