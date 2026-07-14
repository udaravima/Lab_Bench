"""Merge vetted vendor symbols from lib/vendor/ into lib/labbench.kicad_sym.

Only symbols listed in VETTED are merged — a symbol earns its place here by
having its pin map diffed against the part datasheet (see lib/PARTS-TO-DOWNLOAD.md).

Run: python3 merge_vendor.py   (from tools/)
"""
import glob
import os
import re
import kicad_gen as kg

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "lib")

# symbol name -> datasheet the pin map was verified against (date of check)
VETTED = {
    "LM5145RGYR":        "lm5145.pdf (2026-07-14)",
    "TCAN1042HGVDR":     "tcan1042hgv-q1.pdf (2026-07-14)",
    "INA228AIDGSR":      "ina228.pdf (2026-07-14)",
    "TLV7011DBVR":       "tlv7022.pdf family ds (2026-07-14)",
    "LTC7004EMSE#TRPBF": "ltc7004.pdf (2026-07-14)",
}


def main():
    blocks = {}
    for f in glob.glob(os.path.join(LIB, "vendor", "*_x", "*", "KiCad", "*.kicad_sym")):
        text = open(f).read()
        m = re.search(r'\(symbol "([^"]+)"', text)
        if not m or m.group(1) not in VETTED:
            continue
        name = m.group(1)
        blocks[name] = kg._find_block(text, '(symbol "%s"' % name)
    missing = set(VETTED) - set(blocks)
    if missing:
        raise SystemExit(f"vetted symbols not found in vendor dir: {missing}")
    body = "\n".join(f"  {b}" for _, b in sorted(blocks.items()))
    out = os.path.join(LIB, "labbench.kicad_sym")
    with open(out, "w") as fh:
        fh.write("(kicad_symbol_lib (version 20211014) (generator labbench_merge)\n")
        fh.write(body)
        fh.write("\n)\n")
    print(f"merged {len(blocks)} symbols -> {out}")
    for n in sorted(blocks):
        print(f"   {n:24s} verified vs {VETTED[n]}")


if __name__ == "__main__":
    main()
