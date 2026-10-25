.syntax unified
.cpu arm7tdmi
.arm
.text
.global boot_bitunpack
boot_bitunpack:
    ldr r2,first_info_ptr
    swi 0x100000
    ldr r0,second_src
    ldr r1,second_dst
    ldr r2,second_info_ptr
    swi 0x100000
    ldr pc,return_pc
first_info_ptr: .word first_info
second_info_ptr: .word second_info
second_src: .word 0x08fbc3dc
second_dst: .word 0x06009700
return_pc: .word 0x08fce218
first_info: .hword 2416
    .byte 1,16
    .word 0x7ffe
second_info: .hword 2384
    .byte 1,16
    .word 0x7ffe
