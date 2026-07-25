#!/usr/bin/env python3
"""Generate main/font8x16.h from a system PSF console font (default
Lat15-VGA16 — the classic IBM VGA glyphs, 8x16, ASCII == glyph index for
0x20..0x7E in every Lat15 font). Machine-extracted so the bitmaps are
never hand-typed. Verify: python3 gen_font.py --show 'A0*'
"""
import gzip
import struct
import sys
import os

FONT = "/usr/share/consolefonts/Lat15-VGA16.psf.gz"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "main", "font8x16.h")


def load_psf(path):
    data = gzip.open(path, "rb").read()
    if data[:2] == b"\x36\x04":                       # PSF1
        mode, charsize = data[2], data[3]
        n = 512 if (mode & 1) else 256
        glyphs = [data[4 + i * charsize:4 + (i + 1) * charsize]
                  for i in range(n)]
        assert charsize == 16, charsize
        return glyphs
    magic, ver, hdr, flags, length, charsize, h, w = struct.unpack(
        "<IIIIIIII", data[:32])
    assert magic == 0x864AB572, hex(magic)            # PSF2
    assert (w, h) == (8, 16) and charsize == 16, (w, h, charsize)
    return [data[hdr + i * charsize:hdr + (i + 1) * charsize]
            for i in range(length)]


def main():
    glyphs = load_psf(FONT)
    if len(sys.argv) > 2 and sys.argv[1] == "--show":
        for ch in sys.argv[2]:
            print(repr(ch))
            for row in glyphs[ord(ch)]:
                print("".join("#" if row & (0x80 >> b) else "." for b in range(8)))
        return
    with open(OUT, "w") as f:
        f.write("/* font8x16.h -- ASCII 0x20..0x7E of the classic VGA 8x16\n"
                " * console font, machine-extracted from %s\n"
                " * by tools/gen_font.py (do not hand-edit). Row-major, MSB =\n"
                " * leftmost pixel. */\n" % FONT)
        f.write("#pragma once\n#include <stdint.h>\n\n"
                "#define FONT_W 8\n#define FONT_H 16\n"
                "#define FONT_FIRST 0x20\n#define FONT_LAST 0x7E\n\n"
                "static const uint8_t font8x16[95][16] = {\n")
        for c in range(0x20, 0x7F):
            rows = ", ".join("0x%02X" % b for b in glyphs[c])
            f.write("    { %s }, /* %s */\n"
                    % (rows, chr(c) if c != 0x2A else "star"))
        f.write("};\n")
    print("wrote", os.path.normpath(OUT), "(95 glyphs)")


if __name__ == "__main__":
    main()
