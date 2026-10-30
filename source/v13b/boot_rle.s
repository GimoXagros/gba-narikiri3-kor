.syntax unified
.cpu arm7tdmi
.arm
.text
.global boot_rle
boot_rle:
    ldr r1,scratch
    swi 0x140000
    ldr r0,scratch
    mov r1,#0x06000000
    adr r2,info
    swi 0x100000
    ldr pc,return_pc
// Native initialization clears EWRAM before game state is created.
scratch: .word 0x02000000
return_pc: .word 0x08fce218
info: .hword 4800
    .byte 1,16
    .word 0x7ffe
