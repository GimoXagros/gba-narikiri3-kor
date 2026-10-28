.syntax unified
.cpu arm7tdmi
.thumb
.section .predicate,"ax"
.global ordinary_space_width
.thumb_func
ordinary_space_width:
 movs r2,#12
 cmp r1,#0
 beq pred_done
 movs r1,r0
 adds r1,#1
 ldrb r3,[r0]
 cmp r3,#0x20
 beq ascii_space
 cmp r3,#0x81
 bne pred_done
 ldrb r3,[r0,#1]
 cmp r3,#0x40
 bne pred_done
 adds r1,#1
ascii_space:
 ldrb r3,[r1]
next_char:
 cmp r3,#0
 beq pred_done
 cmp r3,#10
 beq pred_done
 cmp r3,#0x20
 beq pred_done
 cmp r3,#0x81
 bne previous
 ldrb r3,[r1,#1]
 cmp r3,#0x40
 beq pred_done
previous:
 subs r0,#1
 ldrb r3,[r0]
 cmp r3,#0x20
 beq pred_done
 cmp r3,#0x40
 bne half
 subs r0,#1
 ldrb r3,[r0]
 cmp r3,#0x81
 beq pred_done
half:
 movs r2,#6
pred_done:
 bx lr
.section .writer,"ax"
.global record_sprite_width
.thumb_func
record_sprite_width:
 mov r0,r8
 movs r1,r6
 bl ordinary_space_width
 mov r1,r10
 adds r1,#1
 lsls r1,#2
 add r1,r9
 adds r1,r6
 strb r2,[r1]
 mov r0,r8
 ldrb r0,[r0]
 lsrs r0,#7
 adds r0,#1
 add r8,r0
 adds r7,#4
 adds r6,#1
 cmp r6,r10
 ldr r3,=0x08015c45
 bx r3
.ltorg
.section .position,"ax"
.global position_half_sprites
.thumb_func
position_half_sprites:
 push {r4-r6,lr}
 movs r3,r0
 movs r5,r0
 movs r4,r1
 movs r6,r2
find_end:
 ldmia r5!,{r0}
 cmp r0,#0
 bne find_end
position_loop:
 ldmia r3!,{r0}
 cmp r0,#0
 beq finished
 strh r4,[r0,#12]
 strh r6,[r0,#14]
 ldrb r1,[r5]
 adds r5,#1
 adds r4,r1
 b position_loop
finished:
 pop {r4-r6}
 pop {r0}
 bx r0


.section .count,"ax"
.global count_sprite_chars
.thumb_func
count_sprite_chars:
 movs r1,#0
count_loop:
 ldrb r2,[r0]
 cmp r2,#0
 beq count_done
 cmp r2,#10
 beq count_done
 lsrs r2,#7
 adds r2,#1
 adds r0,r0,r2
 adds r1,#1
 b count_loop
count_done:
 movs r0,r1
 bx lr
.global alloc_sprite_bytes
.thumb_func
alloc_sprite_bytes:
 push {lr}
 bl count_sprite_chars
 lsls r1,r0,#2
 adds r0,r0,r1
 adds r0,#7
 movs r1,#3
 bics r0,r1
 pop {r1}
 bx r1
.section .ascii,"ax"
.global draw_sprite_char
.thumb_func
draw_sprite_char:
 push {lr}
 sub sp,#4
 ldrb r2,[r1]
 cmp r2,#0x80
 bhs draw_char
 subs r2,#32
 lsls r2,#1
 ldr r3,=0x08741d80
 ldr r3,[r3]
 ldrh r2,[r3,r2]
 mov r1,sp
 strh r2,[r1]
draw_char:
 ldr r3,=0x080021a9
 bl sprite_draw_jump
 add sp,#4
 pop {r1}
 bx r1
.ltorg

sprite_draw_jump:
 bx r3
