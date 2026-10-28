.syntax unified
.cpu arm7tdmi
.thumb
.text
.global scoped_tile
.thumb_func
scoped_tile:
 push {r4-r7,lr}
 movs r4,r0
 movs r5,r1
 movs r7,r2
 mov r3,r10
 cmp r2,r3
 bne fallback
 ldr r3,[r2]
 cmp r3,#0
 beq fallback
 ldr r6,[r2,#20]
 cmp r6,#0x70
 blo fallback
 cmp r6,#0xee
 bhs fallback
 cmp r6,#0xae
 beq fallback
 cmp r6,#0xaf
 beq fallback
scan:
 cmp r6,#0xae
 bne scan_slot
 adds r6,#2
scan_slot:
 movs r0,r6
 subs r0,#0x70
 lsrs r1,r0,#3
 movs r2,#7
 ands r0,r2
 movs r2,#1
 lsls r2,r0
 adds r1,#4
 ldrb r0,[r7,r1]
 tst r0,r2
 beq found
 adds r6,#1
 cmp r6,#0xee
 blo scan
 b fallback
found:
 orrs r0,r2
 strb r0,[r7,r1]
 adds r0,r6,#1
 cmp r0,#0xae
 bne cursor_store
 adds r0,#2
cursor_store:
 str r0,[r7,#20]
 ldr r0,=0x03000054
 ldr r0,[r0]
 lsls r1,r6,#5
 adds r0,r1
 ldmia r4!,{r1-r3,r5}
 stmia r0!,{r1-r3,r5}
 ldmia r4!,{r1-r3,r5}
 stmia r0!,{r1-r3,r5}
 ldr r0,=0x03000058
 ldr r0,[r0]
 adds r0,r6
 pop {r4-r7}
 pop {r1}
 bx r1
fallback:
 movs r0,r4
 movs r1,r5
 movs r2,r7
 pop {r4-r7}
 pop {r3}
 mov lr,r3
 ldr r3,=0x08fbbf71
 bx r3
.ltorg
