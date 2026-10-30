.syntax unified
.cpu arm7tdmi
.thumb
.text
.global popup_names
.thumb_func
popup_names:
 push {r4-r7,lr}
 movs r4,r0
 movs r5,r1
 ldr r2,=formats
1:
 ldr r3,[r2]
 adds r2,#4
 cmp r3,#0
 beq native
 cmp r3,r4
 bne 1b
 ldr r7,[r5,#4]
 ldr r2,=0x08000000
 cmp r7,r2
 blo native
 ldr r2,=0x08ffffc0
 cmp r7,r2
 bhi native
 movs r2,#0
2:
 ldrb r3,[r7,r2]
 cmp r3,#0
 beq copy
 adds r2,#1
 cmp r2,#63
 blo 2b
 b native
copy:
 sub sp,#80
 mov r6,sp
 ldmia r5!,{r0-r3}
 stmia r6!,{r0-r3}
 mov r0,sp
 str r6,[r0,#4]
 movs r5,#0
3:
 ldrb r2,[r7]
 adds r7,#1
 cmp r2,#0
 beq ready
 cmp r2,#0x80
 bhs pair
 cmp r2,#32
 bne single
 cmp r5,#0
 beq single
 ldrb r3,[r7]
 cmp r3,#0
 beq single
 cmp r3,#32
 beq single
 movs r2,#23
single:
 strb r2,[r6]
 adds r6,#1
 movs r5,#0
 cmp r2,#32
 beq 3b
 movs r5,#1
 b 3b
pair:
 ldrb r3,[r7]
 adds r7,#1
 cmp r2,#0x81
 bne store_pair
 cmp r3,#0x40
 bne store_pair
 cmp r5,#0
 beq padding
 ldrb r0,[r7]
 cmp r0,#0
 beq padding
 cmp r0,#0x81
 bne half
 ldrb r0,[r7,#1]
 cmp r0,#0x40
 beq padding
half:
 movs r2,#0x16
 movs r3,#1
 b store_pair
padding:
 movs r5,#0
 b write_pair
store_pair:
 movs r5,#1
write_pair:
 strb r2,[r6]
 strb r3,[r6,#1]
 adds r6,#2
 b 3b
ready:
 strb r2,[r6]
 movs r0,r4
 mov r1,sp
 bl original
 add sp,#80
 b done
native:
 movs r0,r4
 movs r1,r5
 bl original
done:
 pop {r4-r7}
 pop {r0}
 bx r0
.thumb_func
original:
 push {r4,lr}
 movs r3,r0
 adds r2,r1,#4
 ldr r4,=0x03001468
 ldr r0,=0x08001649
 bx r0
.balign 4
formats:
 .word 0x08147374,0x0814744c,0x08147464
 .word 0x081488b0,0x08148978,0x08147238,0x081474c4,0
.ltorg
