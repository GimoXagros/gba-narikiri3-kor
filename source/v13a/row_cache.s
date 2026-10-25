.syntax unified
.cpu arm7tdmi
.thumb
.text
.global row_cached_tile, row_match_start, row_match_end, row_pin_start, row_pin_end
@ r0=32Bpixels,r1=destshadowcell,r2=20Bper-label context(readyu32+16Bpins).
@ Lazy exactscan onfirstmiss. New/hitIDs pinconservatively; neverunpinoldIDs.
@ Onnofree refresh excludingcurrentdest, thenretryonce. No permanentstate.
.thumb_func
row_cached_tile:
    push {r4-r7,lr}
    sub sp,#12
    str r1,[sp]
    str r2,[sp,#4]
    movs r4,r0
    adds r7,r2,#4
    ldr r0,=0x03000054
    ldr r5,[r0]
    movs r6,#0x70
row_match_start:
match_slot:
    lsls r0,r6,#5
    adds r0,r5
    movs r1,#0
match_word:
    ldr r2,[r0,r1]
    ldr r3,[r4,r1]
    cmp r2,r3
    bne next_match
    adds r1,#4
    cmp r1,#32
    blo match_word
    b found
next_match:
    adds r6,#1
    cmp r6,#0xae
    bne after_gap
    adds r6,#2
after_gap:
    cmp r6,#0xee
    blo match_slot
row_match_end:
    ldr r0,[sp,#4]
    ldr r0,[r0]
    cmp r0,#0
    beq refresh
    movs r0,#0
    str r0,[sp,#8]
    b allocate
refresh:
    movs r0,#0
    str r0,[r7]
    str r0,[r7,#4]
    str r0,[r7,#8]
    str r0,[r7,#12]
    ldr r0,=0x03000058
    ldr r6,[r0]
    adds r6,#0x70
    ldr r5,=0x03c003c0
    ldr r0,=0x03000060
row_pin_start:
pin_pair:
    ldr r1,[r0]
    tst r1,r5
    beq zero_pair
pin_single:
    ldr r3,[sp]
    cmp r0,r3
    beq next_pin
    ldrh r1,[r0]
    lsls r1,#22
    lsrs r1,#22
    subs r1,r6
    cmp r1,#0x7d
    bhi next_pin
    lsrs r2,r1,#3
    movs r3,#7
    ands r1,r3
    movs r3,#1
    lsls r3,r1
    ldrb r1,[r7,r2]
    orrs r1,r3
    strb r1,[r7,r2]
next_pin:
    adds r0,#2
    lsls r1,r0,#30
    bmi pin_single
    ldr r3,=0x03000560
    cmp r0,r3
    blo pin_pair
    b pins_ready
zero_pair:
    adds r0,#4
    ldr r3,=0x03000560
    cmp r0,r3
    blo pin_pair
row_pin_end:
pins_ready:
    ldr r0,[sp,#4]
    movs r1,#1
    str r1,[r0]
    str r1,[sp,#8]
allocate:
    movs r6,#0x70
free_slot:
    movs r0,r6
    subs r0,#0x70
    lsrs r1,r0,#3
    movs r2,#7
    ands r0,r2
    movs r2,#1
    lsls r2,r0
    ldrb r0,[r7,r1]
    tst r0,r2
    beq upload
    adds r6,#1
    cmp r6,#0xae
    bne free_gap
    adds r6,#2
free_gap:
    cmp r6,#0xee
    blo free_slot
    ldr r0,[sp,#8]
    cmp r0,#0
    beq refresh
    movs r6,#0x2f
    b return_id
upload:
    ldr r0,=0x03000054
    ldr r5,[r0]
    lsls r0,r6,#5
    adds r0,r5
    ldmia r4!,{r1-r3,r5}
    stmia r0!,{r1-r3,r5}
    ldmia r4!,{r1-r3,r5}
    stmia r0!,{r1-r3,r5}
found:
    ldr r0,[sp,#4]
    ldr r0,[r0]
    cmp r0,#0
    beq return_id
    movs r0,r6
    subs r0,#0x70
    lsrs r1,r0,#3
    movs r2,#7
    ands r0,r2
    movs r2,#1
    lsls r2,r0
    ldrb r0,[r7,r1]
    orrs r0,r2
    strb r0,[r7,r1]
return_id:
    ldr r0,=0x03000058
    ldr r0,[r0]
    adds r0,r6
    add sp,#12
    pop {r4-r7,pc}
.ltorg
