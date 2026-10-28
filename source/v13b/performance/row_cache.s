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
row_match_start:
    mov r0,r10
    adds r0,#4
    cmp r0,r7
    bne normal_match
    subs r0,#4
    ldr r0,[r0]
    cmp r0,#0
    beq refresh
    movs r0,#0
    str r0,[sp,#8]
    b allocate
normal_match:
    movs r0,r4
    movs r1,r5
    ldr r3,=0x08fbcf01
    bl match_call
    movs r6,r0
    cmp r6,#0xee
    beq row_match_end
    b found
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
    mov r12,r4
    ldr r4,[sp]
    ldr r3,=0x08fbd001
    bl match_call
    mov r4,r12
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
    movs r0,r4
    ldr r1,=0x03000054
    ldr r1,[r1]
    ldr r3,=0x08fbcf01
    bl match_call
    movs r6,r0
    cmp r6,#0xee
    bne found
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
match_call:
    bx r3
.ltorg
