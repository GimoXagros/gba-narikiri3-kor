.syntax unified
.cpu arm7tdmi
.thumb
.text
.global small_composite
@ Internalfinal-low-half flush. Allcomplete8pxcells use originalcache directly.
@ r0=tilewithfinallow4px,r1=mapcell,r2=palette; keepneighborhigh4px.
.thumb_func
small_composite:
    push {r4-r7,lr}
    sub sp,#36
    str r3,[sp,#32]
    movs r4,r1
    movs r5,r0
    movs r6,r2
    ldrh r0,[r4]
    movs r1,r0
    lsrs r1,#10
    lsls r1,#10
    cmp r1,r6
    bne bad_cell
    lsls r0,#22
    lsrs r0,#22
    ldr r1,=0x03000058
    ldr r1,[r1]
    subs r0,r1
    cmp r0,#255
    bhi bad_cell
    lsls r0,#5
    ldr r1,=0x03000054
    ldr r1,[r1]
    adds r0,r1
    mov r1,sp
    movs r2,#8
merge_row:
    ldmia r0!,{r3}
    lsrs r3,#16
    lsls r3,#16
    ldrh r7,[r5]
    orrs r3,r7
    stmia r1!,{r3}
    adds r5,#4
    subs r2,#1
    bne merge_row
    mov r0,sp
    movs r1,r4
    ldr r2,[sp,#32]
    ldr r3,=row_cached_tile+1
    bl partial_call
    ldr r1,=0x03000058
    ldr r1,[r1]
    adds r1,#0x2f
    cmp r0,r1
    beq pressure
    orrs r0,r6
    strh r0,[r4]
    ldr r1,=0x03001461
    movs r0,#1
    strb r0,[r1]
    movs r0,#0
    b done
pressure:
    movs r0,#1
    b done
bad_cell:
    movs r0,#2
done:
    add sp,#36
    pop {r4-r7}
    pop {r1}
    bx r1
partial_call:
    bx r3
.ltorg
