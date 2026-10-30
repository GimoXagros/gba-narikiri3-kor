.syntax unified
.cpu arm7tdmi
.thumb
.section .guard,"ax"
.global prefix
.thumb_func
prefix:
 push {r4-r7,lr}
 movs r4,r0
 movs r5,r1
 ldr r3,=0x080cd7f7
 cmp lr,r3
 bne reject
 cmp r5,#1
 blo reject
 cmp r5,#154
 bhi reject
 movs r3,#3
 tst r4,r3
 bne reject
 ldr r2,[r4]
 ldr r3,=0x0d100102
 cmp r2,r3
 bne reject
 ldrb r2,[r4,#4]
 cmp r2,#2
 bne reject
 ldrh r2,[r4,#6]
 ldr r3,=0x0d01
 cmp r2,r3
 bne reject
 ldrb r2,[r4,#5]
 cmp r2,#2
 blo reject
 cmp r2,#12
 bhi reject
 movs r3,#1
 tst r2,r3
 bne reject
 ldr r3,=0x03000058
 ldr r3,[r3]
 cmp r3,#0
 bne reject
 ldr r3,=draw+1
 bx r3
reject:
 movs r0,r4
 movs r1,r5
 pop {r4-r7}
 pop {r3}
 mov lr,r3
 ldr r3,=original+1
 bx r3
.thumb_func
original:
 push {lr}
 movs r2,r1
 cmp r2,#9
 bgt original_large
 ldr r1,=0x081be68c
 ldr r3,=0x080ccb8b
 bx r3
original_large:
 ldr r3,=0x080ccb95
 bx r3
.ltorg
.section .draw,"ax"
.thumb_func
draw:
 movs r3,r5
 ldr r0,=0x03001468
 ldr r1,=0x03001568
 lsls r2,#6
 ldr r7,=0x03000064
 adds r7,r2
 ldr r6,=0xd020
 movs r2,#0
 cmp r5,#100
 blo hundred_done
 subs r5,#100
 movs r2,#1
hundred_done:
 adds r2,r6
 strh r2,[r7]
 adds r2,#16
 strb r2,[r0]
 cmp r3,#100
 blo hundred_scratch_done
 strb r2,[r1,#2]
hundred_scratch_done:
 movs r2,#0
ten_loop:
 cmp r5,#10
 blo ten_done
 subs r5,#10
 adds r2,#1
 b ten_loop
ten_done:
 adds r2,r6
 strh r2,[r7,#2]
 adds r2,#16
 strb r2,[r0,#1]
 cmp r3,#10
 blo ten_scratch_done
 strb r2,[r1,#1]
ten_scratch_done:
 adds r5,r6
 strh r5,[r7,#4]
 adds r5,#16
 strb r5,[r0,#2]
 strb r5,[r1]
 movs r2,#0
 strb r2,[r0,#3]
 adds r0,#4
 ldr r1,=0x03001588
 str r0,[r1]
 movs r2,#5
 strb r2,[r4,#4]
 ldr r0,=0x03001461
 movs r1,#1
 strb r1,[r0]
 pop {r4-r7}
 pop {r0}
 bx r0
.ltorg
