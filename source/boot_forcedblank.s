.syntax unified
.cpu arm7tdmi
.arm
.section .text
.global loader_start, patch_begin, patch_end, io_literal, dispcnt_init, source_literal, vram_literal, wait_line160
loader_start:
.incbin "loader_before.bin", 0, 12
patch_begin:
ldr r0, source_literal
ldr r1, vram_literal
swi 0x150000
ldr r1, io_literal
wait_line160:
ldrh r2, [r1, #6]
cmp r2, #160
bne wait_line160
mov r2, #3
strb r2, [r1]
patch_end:
.if (patch_end-patch_begin) != 36
.error "Replacement must stay in the36-byte range"
.endif
.incbin "loader_before.bin", 48, 40
io_literal:
.word 0x04000000
dispcnt_init:
.word 0x00000483
source_literal:
.word 0x08fbb600
.incbin "loader_before.bin", 100, 4
vram_literal:
.word 0x06000000
.incbin "loader_before.bin", 108, 24
