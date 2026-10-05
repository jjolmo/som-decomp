"""Load WRAM from a ZSNES v143 save state (WRAM starts at file offset 0xC13, verified by matching the object table
entries against ROM). usage (library): wram = load_wram(path)"""
WRAM_OFF = 0xC13
def load_wram(path):
    d = open(path, 'rb').read()
    assert d.startswith(b'ZSNES Save State File V143')
    return bytearray(d[WRAM_OFF:WRAM_OFF+0x20000])
