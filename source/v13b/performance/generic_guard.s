.syntax unified
.cpu arm7tdmi
.thumb
.text
.global generic_guard
.thumb_func
generic_guard:
 mov r2,r10
 ldr r3,=0x03007000
 cmp r2,r3
 blo fallback
 ldr r3,=0x03007e00
 cmp r2,r3
 bhs fallback
 ldr r2,[r2,#56]
 ldr r3,=0x51b34ac7
 cmp r2,r3
 bne fallback
 mov r2,r10
 ldr r3,=0x08fbbf71
 bx r3
fallback:
 push {r4-r7,lr}
 sub sp,#40
 str r1,[sp,#32]
 movs r4,r0
 ldr r3,=0x08fc6ba5
 bx r3
.ltorg
