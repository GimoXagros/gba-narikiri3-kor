.syntax unified
.cpu arm7tdmi
.thumb
.section .print,"ax"
.global halfspace_print
.thumb_func
halfspace_print:
    push {r4-r6,lr}
    sub sp,#8
    movs r4,r0
    movs r6,#0
    ldr r5,=0x03000040
    ldrb r0,[r5,#12]
    str r0,[sp,#4]
    b refresh_source
next_character:
    ldrb r2,[r4]
    cmp r2,#10
    bne not_newline
    ldrb r0,[r5,#2]
    lsls r0,#1
    strb r0,[r5,#4]
    movs r0,#0
    bl halfspace_wrap
    adds r4,#1
    b refresh
not_newline:
    cmp r2,#0x18
    beq advance_single
    cmp r2,#0x17
    beq softspace_advance
    cmp r2,#0x16
    bne not_marker
    ldrb r0,[r4,#1]
    cmp r0,#1
    bne not_marker
    adds r4,#1
softspace_advance:
    movs r0,#1
    bl halfspace_wrap
    movs r2,#0
    movs r3,#1
    bl emit_glyph
    adds r4,#1
    b refresh
not_marker:
    movs r0,r2
    subs r0,#0x80
    cmp r0,#0x1f
    bls double_byte
    cmp r2,#0xdf
    ble single_byte
double_byte:
    movs r0,#2
    bl halfspace_wrap
    movs r0,r4
    bl glyph_index
    movs r3,#2
    bl emit_glyph
    adds r4,#2
    b refresh
single_byte:
    cmp r2,#0x10
    bne not_clear
    ldr r3,=0x0800103d
    bl call_r3
    b advance_single
not_clear:
    cmp r2,#0x11
    bne not_wait
    movs r0,#8
    ldrsb r0,[r5,r0]
    movs r1,#9
    ldrsb r1,[r5,r1]
    adds r0,r1
    subs r0,#1
    movs r1,#10
    ldrsb r1,[r5,r1]
    movs r2,#11
    ldrsb r2,[r5,r2]
    adds r1,r2
    subs r1,#1
    movs r2,#7
    ldrsb r2,[r5,r2]
    ldr r3,=0x08002321
    bl call_r3
    b advance_single
not_wait:
    cmp r2,#0x15
    bne not_speed
    adds r4,#1
    ldrb r0,[r4]
    str r0,[sp,#4]
    b advance_single
not_speed:
    cmp r2,#0x12
    bne ascii_glyph
    movs r0,#1
    eors r6,r0
    b advance_single
ascii_glyph:
    movs r0,#2
    bl halfspace_wrap
    movs r0,r4
    movs r1,r6
    ldr r3,=0x08004d91
    bl call_r3
    mov r1,sp
    strh r0,[r1]
    cmp r0,#0
    beq advance_single
    mov r0,sp
    bl glyph_index
    movs r3,#2
    bl emit_glyph
advance_single:
    adds r4,#1
check_start:
    ldrb r1,[r5,#13]
    movs r0,#2
    ands r0,r1
    beq refresh
    ldr r0,=0x030033f8
    ldrh r1,[r0]
    movs r0,#8
    ands r0,r1
    bne done
refresh:
    ldr r0,=0x03001460
    movs r1,#1
    strb r1,[r0]
refresh_source:
    ldrb r0,[r4]
    cmp r0,#0
    bne next_character
done:
    add sp,#8
    pop {r4-r6}
    pop {r0}
    bx r0
call_r3:
    bx r3
.thumb_func
glyph_index:
    ldrb r1,[r0]
    ldrb r2,[r0,#1]
    cmp r1,#0x87
    bhi hangul_lead
    subs r1,#0x81
    b lead_ready
hangul_lead:
    subs r1,#0x85
lead_ready:
    movs r0,#192
    muls r1,r0
    adds r2,r1
    subs r2,#0x40
    bx lr
.ltorg

.section .support,"ax"
.global halfspace_wrap, halfspace_cursor_set, halfspace_clear_bridge
.thumb_func
halfspace_wrap:
    push {r4,lr}
    ldr r4,=0x03000040
    movs r1,#4
    ldrsb r1,[r4,r1]
    movs r2,#2
    ldrsb r2,[r4,r2]
    lsls r2,#1
    cmp r1,r2
    bge wrap
    adds r1,r0
    cmp r1,r2
    ble wrapped
wrap:
    ldrb r0,[r4]
    lsls r0,#1
    strb r0,[r4,#4]
    ldrb r0,[r4,#5]
    adds r0,#1
    strb r0,[r4,#5]
    lsls r0,#24
    asrs r0,#24
    movs r1,#3
    ldrsb r1,[r4,r1]
    cmp r0,r1
    blt wrapped
    movs r0,#8
    ldr r3,=0x080010d9
    bl support_call
    ldrb r0,[r4,#3]
    subs r0,#1
    strb r0,[r4,#5]
wrapped:
    pop {r4}
    pop {r0}
    bx r0
.thumb_func
halfspace_cursor_set:
    ldr r3,=0x03000040
    ldrb r2,[r3]
    adds r2,r0
    lsls r2,#1
    strb r2,[r3,#4]
    ldrb r0,[r3,#1]
    adds r0,r1
    strb r0,[r3,#5]
    bx lr
.thumb_func
halfspace_clear_bridge:
    ldr r0,=0x03000040
    ldrb r1,[r0]
    lsls r1,#1
    strb r1,[r0,#4]
    ldrb r1,[r0,#1]
    ldr r3,=0x08001061
    bx r3
support_call:
    bx r3
.ltorg

.section .glyph,"ax"
.global emit_glyph, halfspace_glyph
.thumb_func
emit_glyph:
    push {r4-r7,lr}
    movs r4,r3
    movs r7,r2
    ldr r5,=0x03000040
    movs r0,#4
    ldrsb r6,[r5,r0]
    movs r0,#5
    ldrsb r1,[r5,r0]
    movs r0,#1
    ands r0,r6
    bne shifted_origin
    cmp r4,#2
    bne shifted_origin
    asrs r0,r6,#1
    ldr r3,=0x08001415
    bl glyph_call
    b advance_cursor
shifted_origin:
    movs r0,#6
    muls r0,r6
    movs r3,#6
    muls r3,r4
    bl halfspace_glyph
advance_cursor:
    adds r6,r4
    strb r6,[r5,#4]
    add r0,sp,#24
    ldr r3,=0x0800149d
    bl glyph_call
    pop {r4-r7}
    pop {r0}
    bx r0
glyph_call:
    bx r3
.ltorg
.thumb_func
halfspace_glyph:
    push {r4-r7,lr}
    sub sp,#12
    lsrs r3,#1
    str r3,[sp]
    movs r4,r0
    lsrs r4,#3
    lsls r4,#5
    movs r5,#7
    ands r0,r5
    lsrs r0,#1
    str r0,[sp,#4]
    adds r4,r0
    movs r0,#240
    lsls r0,#3
    muls r1,r0
    adds r4,r1
    ldr r5,=0x03000560
    adds r5,r4
    lsls r2,#5
    ldr r4,=0x080ddcc4
    adds r4,r2
    movs r0,#0
    str r0,[sp,#8]
    ldr r3,=0x03001464
row:
    ldrh r6,[r4]
    movs r0,r5
    ldr r2,[sp,#4]
    ldr r7,[sp]
pair:
    movs r1,#3
    ands r1,r6
    ldrb r1,[r3,r1]
    strb r1,[r0]
    lsrs r6,#2
    adds r0,#1
    adds r2,#1
    cmp r2,#4
    bne same_tile
    adds r0,#28
    movs r2,#0
same_tile:
    subs r7,#1
    bne pair
    adds r4,#2
    adds r5,#4
    ldr r0,[sp,#8]
    adds r0,#1
    str r0,[sp,#8]
    cmp r0,#8
    bne same_tile_row
    ldr r1,=0x3a0
    adds r5,r1
same_tile_row:
    cmp r0,#16
    blo row
    add sp,#12
    pop {r4-r7}
    pop {r0}
    bx r0
.ltorg
