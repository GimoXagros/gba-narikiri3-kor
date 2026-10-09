.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global native_dynamic_start, native_dynamic_end
.thumb_func
native_dynamic_start:
push {r4,r5,r6,r7,lr}
sub sp,#12
str r1,[sp,#4]
str r2,[sp,#8]
movs r4,r0
ldr r5,bank_literal
movs r0,#1
bl palette_allocator
movs r7,r0
movs r0,r5
movs r1,#47
movs r2,r7
movs r3,#0
bl palette_loader
ldr r0,resource_table_literal
lsls r4,r4,#2
ldr r1,[r0,r4]
str r1,[sp]
movs r0,r5
bl bank_getter
ldr r0,[r0]
lsrs r0,r0,#13
bl tile_allocator
movs r6,r0
ldr r1,[sp]
movs r0,r5
movs r2,r6
movs r3,#0
bl resource_loader
ldr r0,frame_table_literal
ldr r2,[r0,r4]
str r7,[sp]
ldr r0,[sp,#4]
ldr r1,[sp,#8]
movs r3,r6
bl sprite_factory
add sp,#12
pop {r4,r5,r6,r7}
pop {r1}
bx r1
.balign 4
bank_literal: .word 0x08750a00
resource_table_literal: .word 0x08dd22dc
frame_table_literal: .word 0x08dd221c
.space 116-(.-native_dynamic_start),0
native_dynamic_end:
.thumb_set palette_allocator,0x080046d8
.thumb_set palette_loader,0x0800a804
.thumb_set bank_getter,0x08003444
.thumb_set tile_allocator,0x080045ec
.thumb_set resource_loader,0x0800a7bc
.thumb_set sprite_factory,0x08002a30
