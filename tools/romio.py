"""ROM loader shared by the tools. The ROM path is always passed on the command line (first argument)."""
import sys
def load(path):
    d = open(path, 'rb').read()
    if len(d) == 2097152 + 512:
        d = d[512:]
    assert len(d) == 2097152, 'expected a 2 MiB HiROM image'
    return d
def rom_from_argv():
    if len(sys.argv) < 2:
        sys.exit('usage: <tool> ROM_PATH [args...]')
    path = sys.argv.pop(1)
    return load(path)
