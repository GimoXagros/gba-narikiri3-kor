"""B3TJ first-save regression: validate the game checksum and complete state.

EEPROM stores each transferred 64-bit word in reverse byte order. 08008C08
copies the live timer (literal 08008C48) to block+9DC; 080089D4 writes header
and sum32(body), checked by 08008A08. This routine never changes save bytes.
"""
import hashlib,struct

REFERENCE_TIMER=17767
# dev04: only the planned new-game ship base changed from 드림호 to 드림.
# tools/verify_default_save_change.py proves both complete name fields and
# all other bytes against the previous reference, retaining checksum checks.
REFERENCE_STATE_HASH='439a1bf22c6323169984dc9eb24d393a3dcbf5ba16b32aa9524209c699898e56'

def opening_save(raw):
    if len(raw)!=8192:raise ValueError('Expected 8 KiB EEPROM')
    decoded=bytearray(b''.join(raw[i:i+8][::-1] for i in range(0,len(raw),8)))
    if decoded[:8]!=b'NARIKIRI' or struct.unpack_from('<I',decoded,8)[0]!=0x0131cd45:raise ValueError('Save signature/revision differs')
    checksum=struct.unpack_from('<I',decoded,12)[0]
    if checksum!=(sum(struct.unpack('<956I',decoded[16:0xf00]))&0xffffffff):raise ValueError('Game sum32 validation failed')
    timer=struct.unpack_from('<I',decoded,0x9dc)[0]
    if abs(timer-REFERENCE_TIMER)>3:raise ValueError('Opening timer differs beyond the observed three-frame envelope')
    decoded[12:16]=bytes(4);decoded[0x9dc:0x9e0]=bytes(4)
    normalized=hashlib.sha256(decoded).hexdigest()
    if normalized!=REFERENCE_STATE_HASH:raise ValueError('Opening state differs outside the verified timer/checksum fields')
    return {'game_checksum_valid':True,'all_other_save_bytes_identical':True,'normalized_state_sha256':normalized,'play_timer_frames':timer,'timer_delta_from_mgba_reference':timer-REFERENCE_TIMER,'timing_claim':'Recorded, not an audio/performance equivalence claim'}
