.syntax unified
.cpu arm7tdmi
.thumb
.text
.global monster_stream
.thumb_func
monster_stream:
 push {r4-r7,lr}
 sub sp,#120
 str r0,[sp,#64]
 str r1,[sp,#68]
 cmp r5,#211
 bhi fallback_early
 lsls r2,r5,#3
 lsls r3,r5,#6
 subs r3,r2
 ldr r2,=0x081021ac
 ldr r3,[r2,r3]
 cmp r1,r3
 bne fallback_early
 movs r4,r1
 movs r5,#0
 movs r6,#0
scan:
 ldrb r2,[r4]
 cmp r2,#0
 beq measured
 adds r6,#1
 cmp r6,#62
 bhi fallback_early
 cmp r2,#0x20
 beq scan_space
 cmp r2,#0x88
 blo fallback_early
 cmp r2,#0x95
 bhi fallback_early
 adds r4,#1
 adds r5,#1
scan_space:
 adds r4,#1
 adds r5,#1
 b scan
fallback_early:
 b fallback
measured:
 ldr r4,[sp,#64]
 movs r2,#4
 ldrsb r2,[r4,r2]
 cmp r2,#0
 blt fallback_early
 lsls r2,#1
 adds r5,r2
 movs r3,#2
 ldrsb r3,[r4,r3]
 cmp r3,#32
 bgt fallback_early
 lsls r3,#1
 cmp r5,r3
 bgt fallback_early
 adds r5,#1
 lsrs r5,#1
 str r5,[sp,#96]
 movs r3,#5
 ldrsb r3,[r4,r3]
 cmp r3,#0
 blt fallback_early
 cmp r3,#19
 bgt fallback_early
 lsls r3,#6
 adds r3,r2
 ldr r5,=0x03000060
 adds r5,r3
 ldrb r3,[r4,#7]
 lsls r3,#12
 str r3,[sp,#104]
 movs r3,#0
 str r3,[sp,#72]
 add r2,sp,#72
 ldr r3,=UI_CACHE_CONTEXT
 bl call_r3
 str r2,[sp,#92]
 ldr r0,=0x03000054
 ldr r0,[r0]
 movs r1,#0x80
 lsls r1,#2
 ldrb r0,[r0,r1]
 movs r1,#15
 ands r0,r1
 ldr r1,=0x11111111
 muls r0,r1
 str r0,[sp,#100]
 ldr r4,[sp,#68]
 movs r6,#0
next:
 ldrb r0,[r4]
 cmp r0,#0
 bne character
 b finished
character:
 movs r7,#2
 cmp r0,#0x20
 beq blank
 ldrb r1,[r4,#1]
 subs r0,#0x85
 movs r2,#192
 muls r0,r2
 adds r0,r1
 subs r0,#0x40
 lsls r0,#3
 ldr r1,=0x08fbd354
 adds r0,r1
 str r5,[sp,#108]
 str r6,[sp,#112]
 str r7,[sp,#116]
 ldr r1,[sp,#100]
 ldr r3,=0x08fbcb9d
 bl call_r3
 ldr r5,[sp,#108]
 ldr r6,[sp,#112]
 ldr r7,[sp,#116]
 adds r4,#2
 b compose
blank:
 movs r7,#1
 adds r4,#1
 ldr r0,[sp,#100]
 mov r1,sp
 str r0,[r1,#0]
 str r0,[r1,#4]
 str r0,[r1,#8]
 str r0,[r1,#12]
 str r0,[r1,#16]
 str r0,[r1,#20]
 str r0,[r1,#24]
 str r0,[r1,#28]
compose:
 cmp r6,#0
 bne shifted
 cmp r7,#2
 bne buffer_first
 mov r0,sp
 bl upload
 cmp r0,#0
 bne fallback
 b next
shifted:
 mov r0,sp
 add r1,sp,#32
 adds r1,#2
 ldrh r2,[r0,#0]
 strh r2,[r1,#0]
 ldrh r2,[r0,#4]
 strh r2,[r1,#4]
 ldrh r2,[r0,#8]
 strh r2,[r1,#8]
 ldrh r2,[r0,#12]
 strh r2,[r1,#12]
 ldrh r2,[r0,#16]
 strh r2,[r1,#16]
 ldrh r2,[r0,#20]
 strh r2,[r1,#20]
 ldrh r2,[r0,#24]
 strh r2,[r1,#24]
 ldrh r2,[r0,#28]
 strh r2,[r1,#28]
 add r0,sp,#32
 bl upload
 cmp r0,#0
 bne fallback
 cmp r7,#1
 bne buffer_second
 movs r6,#0
 b next
buffer_second:
 mov r0,sp
 adds r0,#2
 b buffer
buffer_first:
 mov r0,sp
buffer:
 add r1,sp,#32
 ldrh r2,[r0,#0]
 strh r2,[r1,#0]
 ldrh r2,[r0,#4]
 strh r2,[r1,#4]
 ldrh r2,[r0,#8]
 strh r2,[r1,#8]
 ldrh r2,[r0,#12]
 strh r2,[r1,#12]
 ldrh r2,[r0,#16]
 strh r2,[r1,#16]
 ldrh r2,[r0,#20]
 strh r2,[r1,#20]
 ldrh r2,[r0,#24]
 strh r2,[r1,#24]
 ldrh r2,[r0,#28]
 strh r2,[r1,#28]
 movs r6,#1
 b next
finished:
 cmp r6,#0
 beq success
 add r0,sp,#32
 movs r1,r5
 ldr r2,[sp,#104]
 ldr r3,[sp,#92]
 ldr r7,=UI_FINAL_COMPOSITE
 bl call_r7
 cmp r0,#0
 bne fallback
success:
 ldr r1,[sp,#64]
 ldr r0,[sp,#96]
 strb r0,[r1,#4]
 movs r0,#0
done:
 add sp,#120
 pop {r4-r7}
 pop {r1}
 bx r1
fallback:
 ldr r0,[sp,#64]
 ldr r1,[sp,#68]
 movs r2,#0
 ldr r3,=SMALL_UI_RENDER
 bl call_r3
 b done
upload:
 push {lr}
 movs r1,r5
 ldr r2,[sp,#96]
 ldr r3,=0x08fbbd41
 bl call_r3
 ldr r1,=0x03000058
 ldr r1,[r1]
 adds r1,#0x2f
 cmp r0,r1
 beq pressure
 ldr r1,[sp,#108]
 orrs r0,r1
 strh r0,[r5]
 adds r5,#2
 ldr r1,=0x03001461
 movs r0,#1
 strb r0,[r1]
 movs r0,#0
 b uploaded
pressure:
 movs r0,#1
uploaded:
 pop {r1}
 bx r1
call_r3:
 bx r3
call_r7:
 bx r7
.ltorg
