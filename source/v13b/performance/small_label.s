.syntax unified
.cpu arm7tdmi
.thumb
.text
.global small_item_name_hook, small_item_name_wrapper, small_label_print
@ Diagnostic8-byte hook atCAE18 reconstructs overwrittenargs and explicitreturn.
.thumb_func
small_item_name_hook:
    ldr r1,[r4]
    movs r0,r5
    movs r2,r6
    bl small_item_name_wrapper
    cmp r0,#0
    beq completed_suffix
    ldr r3,=0x080cae21
    bx r3
completed_suffix:
    ldr r3,=0x080cae33
    bx r3
.thumb_func
small_item_name_wrapper:
    push {r4-r6,lr}
    movs r4,r0
    movs r5,r1
    movs r6,r2
    cmp r6,#122
    bhi original_name
    movs r3,r6
    lsrs r3,#3
    ldr r0,=eligible_item_bits
    ldrb r0,[r0,r3]
    movs r3,#7
    ands r3,r6
    movs r2,#1
    lsls r2,r3
    tst r0,r2
    beq original_name
    movs r0,#24
    muls r0,r6
    ldr r2,=0x08105758
    adds r2,r0
    ldr r3,[r2]
    cmp r3,r5
    bne original_name
    ldrb r2,[r2,#12]
    movs r3,#16
    ands r2,r3
    movs r0,r4
    movs r1,r5
    bl small_label_print
    cmp r0,#0
    beq name_done
original_name:
    movs r0,r4
    movs r1,r5
    ldr r3,=0x08001da9
    bl label_call_r3
    movs r0,#1
name_done:
    pop {r4-r6}
    pop {r1}
    bx r1

@ Private static-item-name API.123tableIDs andrawpointer identities arechecked.
@ r2=suffixflag10. Compose the originalg5icon before the caller resetsqtyx.
@ Per-callphase only; no arbitrary1A10 continuation ABI ischanged.
.thumb_func
small_label_print:
    push {r4-r7,lr}
    sub sp,#112
    str r0,[sp,#64]
    str r1,[sp,#68]
    str r2,[sp,#88]
    movs r4,r0
    movs r5,r1
    movs r6,#0
    movs r7,r1
    adds r7,#64
measure_label:
    cmp r5,r7
    bhs early_label_bad
    ldrb r0,[r5]
    cmp r0,#0
    beq measured
    adds r6,#1
    adds r5,#1
    cmp r0,#0x20
    beq measure_label
    adds r6,#1
    cmp r0,#0x80
    blo measure_label
    adds r5,#1
    b measure_label
measured:
    ldr r0,[sp,#88]
    cmp r0,#0
    beq no_icon_width
    adds r6,#2
no_icon_width:
    movs r0,#4
    ldrsb r0,[r4,r0]
    cmp r0,#0
    blt early_label_bad
    lsls r0,#1
    str r0,[sp,#72]
    movs r1,#2
    ldrsb r1,[r4,r1]
    cmp r1,#32
    bgt early_label_bad
    lsls r1,#1
    adds r0,r6
    cmp r0,r1
    bgt early_label_bad
    movs r0,#5
    ldrsb r0,[r4,r0]
    cmp r0,#0
    blt early_label_bad
    cmp r0,#19
    bgt early_label_bad
    ldrb r0,[r4,#7]
    lsls r0,#12
    str r0,[sp,#76]
    movs r0,#0
    str r0,[sp,#92]
    b label_loop
early_label_bad:
    b label_bad
label_loop:
    ldr r5,[sp,#68]
    ldrb r0,[r5]
    cmp r0,#0
    bne next_label_glyph
    ldr r0,[sp,#88]
    cmp r0,#0
    bne suffix_pending
    b finish_label
suffix_pending:
    movs r0,#0
    str r0,[sp,#88]
    ldr r0,[sp,#72]
    movs r1,#1
    tst r0,r1
    bne shifted_suffix
native_suffix:
    bl output_cell
    ldr r0,=0x03000058
    ldr r0,[r0]
    adds r0,#0xf5
    ldr r1,[sp,#76]
    orrs r0,r1
    strh r0,[r4]
    ldr r0,[sp,#72]
    adds r0,#2
    str r0,[sp,#72]
    b label_success
shifted_suffix:
    movs r0,#0
    str r0,[sp,#84]
    movs r0,#8
    str r0,[sp,#80]
    ldr r0,=0x03000054
    ldr r0,[r0]
    ldr r1,=0x1ea0
    adds r0,r1
    b copy_bitmap
next_label_glyph:
    movs r1,#8
    str r1,[sp,#80]
    movs r1,#2
    str r1,[sp,#84]
    cmp r0,#0x20
    beq blank_source
    cmp r0,#0x7e
    bhi hangul_source
    cmp r0,#0x21
    blo early_label_bad
    subs r0,#0x10
    lsls r0,#5
    ldr r1,=0x03001462
    ldrb r1,[r1]
    ldr r2,=0x080fbcc4
    cmp r1,#0
    beq ascii_atlas
    ldr r2,=0x080fdcc4
ascii_atlas:
    adds r0,r2
    movs r1,#1
    str r1,[sp,#84]
    b copy_bitmap
blank_source:
    movs r1,#4
    str r1,[sp,#80]
    movs r1,#1
    str r1,[sp,#84]
    ldr r0,=0x03000054
    ldr r0,[r0]
    movs r1,#0x80
    lsls r1,#2
    adds r0,r1
copy_bitmap:
    mov r1,sp
    movs r2,#8
copy_blank:
    ldmia r0!,{r3}
    stmia r1!,{r3}
    subs r2,#1
    bne copy_blank
    b compose_label
hangul_source:
    cmp r0,#0x88
    blo early_label_bad
    cmp r0,#0x95
    bhi early_label_bad
    ldrb r1,[r5,#1]
    subs r0,#0x85
    movs r2,#192
    muls r0,r2
    adds r0,r1
    subs r0,#0x40
    lsls r0,#3
    ldr r1,=0x08fbd354
    adds r0,r1
    ldr r1,[r0]
    ldr r2,[r0,#4]
    orrs r1,r2
    beq early_label_bad
    ldr r1,=0x03000054
    ldr r1,[r1]
    movs r2,#0x80
    lsls r2,#2
    ldrb r1,[r1,r2]
    movs r2,#15
    ands r1,r2
    ldr r2,=0x11111111
    muls r1,r2
    ldr r3,=0x08fc6c93
    bl label_call_r3
compose_label:
    ldr r0,[sp,#72]
    movs r1,#1
    tst r0,r1
    bne stream_glyph
    ldr r0,[sp,#80]
    cmp r0,#8
    bne stream_glyph
    movs r7,#0
    bl output_cell
    mov r0,sp
    b cache_final_tile
stream_glyph:
    movs r6,#0
    ldr r7,[sp,#80]
    lsrs r7,#2
stream_half:
    mov r0,sp
    adds r0,r6
    add r1,sp,#32
    ldr r2,[sp,#72]
    movs r3,#1
    ands r2,r3
    lsls r2,#1
    adds r1,r2
    movs r3,#8
copy_half_rows:
    ldrh r4,[r0]
    strh r4,[r1]
    adds r0,#4
    adds r1,#4
    subs r3,#1
    bne copy_half_rows
    cmp r2,#0
    beq half_buffered
    bl output_cell
    add r0,sp,#32
cache_final_tile:
    movs r1,r4
    add r2,sp,#92
    ldr r3,=row_cached_tile+1
    bl label_call_r3
    ldr r1,=0x03000058
    ldr r1,[r1]
    adds r1,#0x2f
    cmp r0,r1
    beq label_pressure
    ldr r1,[sp,#76]
    orrs r0,r1
    strh r0,[r4]
    ldr r1,=0x03001461
    movs r0,#1
    strb r0,[r1]
    cmp r7,#0
    beq fast_glyph_complete
half_buffered:
    ldr r0,[sp,#72]
    adds r0,#1
    str r0,[sp,#72]
    adds r6,#2
    subs r7,#1
    bne stream_half
    b advance_source
fast_glyph_complete:
    ldr r0,[sp,#72]
    adds r0,#2
    str r0,[sp,#72]
advance_source:
    ldr r0,[sp,#68]
    ldr r1,[sp,#84]
    adds r0,r1
    str r0,[sp,#68]
    b label_loop
finish_label:
    ldr r0,[sp,#72]
    movs r1,#1
    ands r0,r1
    beq label_success
    bl output_cell
    add r0,sp,#32
    movs r1,r4
    ldr r2,[sp,#76]
    add r3,sp,#92
    bl small_composite
    cmp r0,#0
    bne label_done
label_success:
    ldr r0,[sp,#72]
    adds r0,#1
    lsrs r0,#1
    ldr r4,[sp,#64]
    strb r0,[r4,#4]
    movs r0,#0
    b label_done
label_pressure:
    movs r0,#1
    b label_done
label_bad:
    movs r0,#3
label_done:
    add sp,#112
    pop {r4-r7}
    pop {r1}
    bx r1
@ r4returns currentoutputmapcell; doesnot touchr6/r7 streamstate.
output_cell:
    ldr r4,[sp,#64]
    movs r0,#5
    ldrsb r0,[r4,r0]
    lsls r0,#6
    ldr r4,[sp,#72]
    lsrs r4,#1
    lsls r4,#1
    adds r4,r0
    ldr r0,=0x03000060
    adds r4,r0
    bx lr
label_call_r3:
    bx r3
.ltorg

.balign 4
eligible_item_bits:
    .byte 0x7e,0x53,0xff,0xdf,0xf,0x0,0xfc,0xfd,0xfe,0xfc,0xbf,0xb3,0x17,0xe7,0x1f,0x4
