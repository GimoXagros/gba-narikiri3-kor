.syntax unified
.cpu arm7tdmi
.thumb
.text
.global small_ui_format, small_all_format, small_direct, small_ui_render, small_native_format
.global small_native_helper
.thumb_func
small_native_helper:
 push {r4,r5,lr}
 movs r5,r0
 adds r2,#4
 ldr r4,=0x03001468
 movs r0,r4
 ldr r3,=0x080025cd
 bl call_r3
 movs r0,r5
 movs r1,r4
 ldr r3,=0x08001a11
 bl call_r3
 pop {r4,r5}
 pop {r0}
 bx r0
.thumb_func
small_native_format:
@ Entry already saved r1-r3 and LR, preserving the fourth variadic argument.
 push {r0}
 ldr r0,[sp,#4]
 ldr r2,=0x080cd817
 cmp r0,r2
 beq dispatch_monster
 ldr r1,=scope_table
find_scope:
 ldr r2,[r1]
 cmp r2,#0
 beq dispatch_native
 cmp r0,r2
 beq found_scope
 adds r1,#8
 b find_scope
found_scope:
 ldr r2,=0x080044f7
 cmp r0,r2
 bne checked_scope
 ldr r0,[sp,#8]
 ldr r2,=trap_format_pointers
 ldr r3,[r2]
 cmp r0,r3
 beq checked_scope
 ldr r3,[r2,#4]
 cmp r0,r3
 bne dispatch_native
checked_scope:
 ldr r2,[r1,#4]
 cmp r2,#1
 beq dispatch_ui
 cmp r2,#2
 beq dispatch_direct
 cmp r2,#3
 beq dispatch_center
 b dispatch_all
dispatch_monster:
 pop {r0}
 ldr r1,[sp,#4]
 movs r2,#0
 ldr r3,=0x08fbbb2d
 bl call_r3
 b dispatch_return
dispatch_all:
 pop {r0}
 ldr r1,[sp,#4]
 add r2,sp,#8
 bl all_format_helper
 b dispatch_return
dispatch_ui:
 pop {r0}
 ldr r1,[sp,#4]
 add r2,sp,#8
 bl ui_format_helper
 b dispatch_return
dispatch_center:
 pop {r0}
 ldr r1,[sp,#4]
 add r2,sp,#8
 bl centered_format_helper
 b dispatch_return
dispatch_direct:
 pop {r0}
 ldr r1,[sp,#4]
 movs r2,#0
 bl small_ui_render
 ldr r0,[sp]
 b dispatch_cleanup
dispatch_native:
 pop {r0}
 ldr r1,[sp,#4]
 add r2,sp,#4
 ldr r3,=0x08001d89
 bl call_r3
 ldr r0,=0x08001db5
dispatch_return:
 ldr r0,=0x08001db5
dispatch_cleanup:
 pop {r3}
 add sp,#12
 bx r3
.thumb_func
small_ui_format:
 push {r1-r3}
 push {lr}
 ldr r1,[sp,#4]
 add r2,sp,#8
 bl ui_format_helper
 pop {r3}
 add sp,#12
 bx r3
.thumb_func
small_all_format:
 push {r1-r3}
 push {lr}
 ldr r1,[sp,#4]
 add r2,sp,#8
 bl all_format_helper
 pop {r3}
 add sp,#12
 bx r3
.thumb_func
ui_format_helper:
 push {r4-r7,lr}
 sub sp,#256
 movs r4,r0
 movs r5,r1
 movs r6,r2
 movs r7,#0
@ Mark literal lexical spaces before expanding %s. Names and numeric padding
@ remain ordinary 20 and will retain eight-pixel width in small_ui_render.
1:
 ldrb r0,[r5,r7]
 cmp r0,#0
 beq 4f
 cmp r7,#254
 bhs 5f
 cmp r0,#0x20
 bne 3f
 cmp r7,#0
 beq 3f
 subs r1,r7,#1
 ldrb r1,[r5,r1]
 cmp r1,#0x20
 beq 3f
 adds r1,r7,#1
 ldrb r1,[r5,r1]
 cmp r1,#0x20
 beq 3f
 cmp r1,#0
 beq 3f
 cmp r1,#0x25
 beq 3f
 movs r0,#0x1f
3:
 mov r1,sp
 strb r0,[r1,r7]
 adds r7,#1
 b 1b
4:
 mov r1,sp
 strb r0,[r1,r7]
 ldr r0,=0x03001468
 movs r2,r6
 ldr r3,=0x080025cd
 bl call_r3
 movs r0,r4
 ldr r1,=0x03001468
 movs r2,#1
 bl small_ui_render
 b 6f
5:
 movs r0,r4
 movs r1,r5
 movs r2,r6
 subs r2,#4
 ldr r3,=0x08001d89
 bl call_r3
6:
 add sp,#256
 pop {r4-r7}
 pop {r3}
 bx r3
.thumb_func
all_format_helper:
 push {r4,lr}
 movs r4,r0
 ldr r0,=0x03001468
 ldr r3,=0x080025cd
 bl call_r3
 movs r0,r4
 ldr r1,=0x03001468
 movs r2,r1
all_space_scan:
 ldrb r3,[r2]
 cmp r3,#0
 beq all_native_render
 cmp r3,#0x20
 beq all_half_render
 adds r2,#1
 cmp r3,#0x80
 blo all_space_scan
 adds r2,#1
 b all_space_scan
all_native_render:
 ldr r3,=0x08001a11
 bl call_r3
 b all_render_done
all_half_render:
 movs r2,#0
 bl small_ui_render
all_render_done:
 pop {r4}
 pop {r3}
 bx r3
.thumb_func
centered_format_helper:
 push {r4,lr}
 movs r4,r0
 ldr r0,=0x03001468
 ldr r3,=0x080025cd
 bl call_r3
 ldr r1,=0x03001468
 movs r2,#0
center_count:
 ldrb r0,[r1]
 cmp r0,#0
 beq center_ready
 adds r1,#1
 adds r2,#1
 cmp r0,#0x20
 beq center_count
 adds r2,#1
 cmp r0,#0x80
 blo center_count
 adds r1,#1
 b center_count
center_ready:
 adds r2,#1
 lsrs r2,#1
 ldrb r0,[r4,#2]
 ldrb r1,[r4]
 subs r0,r1
 subs r0,r2
 asrs r0,#1
 adds r0,r1
 strb r0,[r4,#4]
 movs r0,r4
 ldr r1,=0x03001468
 movs r2,#0
 bl small_ui_render
 pop {r4}
 pop {r3}
 bx r3
.thumb_func
small_direct:
 movs r2,#0
 b small_ui_render
@ r0 window, r1 formatted bytes, r2=1 protects unmarked spaces.
@ Preflight controls first; newline and clear keep original native semantics.
@ Each complete line is rendered independently, never interrupting half phase.
.thumb_func
small_ui_render:
 push {r4-r7,lr}
 sub sp,#84
 str r0,[sp,#64]
 str r1,[sp,#68]
 str r2,[sp,#72]
 ldrh r3,[r0,#4]
 str r3,[sp,#80]
 movs r4,r1
 movs r5,#0
 movs r6,#0
preflight:
 ldrb r0,[r4]
 cmp r0,#0
 beq start_render
 adds r6,#1
 cmp r6,#255
 bhi fallback
 cmp r0,#0x0a
 beq reset_measure
 cmp r0,#0x10
 beq reset_measure
 cmp r0,#0x13
 beq icon_measure
 cmp r0,#0x1f
 beq one_byte
 cmp r0,#0x20
 blo fallback
 beq space_measure
 cmp r0,#0x7f
 bls one_byte
 cmp r0,#0x88
 blo fallback
 cmp r0,#0x95
 bhi fallback
 adds r4,#1
 adds r5,#1
 b one_byte
icon_measure:
 ldrb r1,[r4,#1]
 cmp r1,#18
 bhi fallback
 adds r4,#1
 adds r5,#1
 b one_byte
space_measure:
 ldr r1,[sp,#72]
 adds r5,r5,r1
one_byte:
 adds r5,#1
 cmp r5,#62
 bhi fallback
 adds r4,#1
 b preflight
reset_measure:
 movs r5,#0
 adds r4,#1
 b preflight
start_render:
 ldr r4,[sp,#68]
 movs r5,#0
next_byte:
 ldrb r0,[r4]
 cmp r0,#0
 beq flush_final
 cmp r0,#0x0a
 beq flush_control
 cmp r0,#0x10
 beq flush_control
 cmp r0,#0x13
 bne not_icon
 movs r0,#0x96
 b append_byte
not_icon:
 cmp r0,#0x1f
 bne not_marker
 movs r0,#0x20
 b append_byte
not_marker:
 cmp r0,#0x20
 bne append_byte
 ldr r1,[sp,#72]
 cmp r1,#0
 beq append_byte
 mov r1,sp
 strb r0,[r1,r5]
 adds r5,#1
append_byte:
 mov r1,sp
 strb r0,[r1,r5]
 adds r5,#1
 adds r4,#1
 cmp r0,#0x80
 blo next_byte
 ldrb r0,[r4]
 strb r0,[r1,r5]
 adds r5,#1
 adds r4,#1
 b next_byte
flush_control:
 str r0,[sp,#76]
 bl flush_line
 cmp r0,#0
 bne fallback
 ldr r0,[sp,#76]
 mov r1,sp
 strb r0,[r1]
 movs r0,#0
 strb r0,[r1,#1]
 ldr r0,[sp,#64]
 ldr r3,=0x08001a11
 bl call_r3
 movs r5,#0
 adds r4,#1
 b next_byte
flush_final:
 bl flush_line
 cmp r0,#0
 bne fallback
 b render_done
fallback:
 ldr r1,[sp,#68]
 movs r2,r1
restore_markers:
 ldrb r3,[r2]
 cmp r3,#0
 beq markers_done
 cmp r3,#0x13
 bne restore_not_icon
 adds r2,#1
 b marker_next
restore_not_icon:
 cmp r3,#0x1f
 bne marker_next
 movs r3,#0x20
 strb r3,[r2]
marker_next:
 adds r2,#1
 b restore_markers
markers_done:
 ldr r0,[sp,#64]
 ldr r2,[sp,#80]
 strh r2,[r0,#4]
 ldr r0,[sp,#64]
 ldr r1,[sp,#68]
 ldr r3,=0x08001a11
 bl call_r3
render_done:
 add sp,#84
 pop {r4-r7}
 pop {r3}
 bx r3
.thumb_func
flush_line:
 push {lr}
@ Caller buffer is above this saved return word.
 movs r0,#0
 cmp r5,#0
 beq flush_done
 add r1,sp,#4
 movs r0,#0
 strb r0,[r1,r5]
 ldr r0,[sp,#68]
 movs r2,#0
 ldr r3,=ui_label_print+1
 bl call_r3
@ Pressure failure is explicit to caller QA, not a silent global reroute.
flush_done:
 pop {r3}
 bx r3
.thumb_func
call_r3:
 bx r3
.ltorg
