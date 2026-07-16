"""Build lib/labbench.pretty from VETTED vendor footprints + synthesized parts.

Mirrors merge_vendor.py: only footprints whose pad tables were checked against
the local datasheet get copied (normalized through the pcbnew API and renamed
to their project name). Also generates PowerFET_SON5x6_GDS from the TI Q5A
land pattern (CSD18563Q5A datasheet §7.2, SLPS444C) with pads renumbered to
match the generic Device:Q_NMOS_GDS symbol (1=G, 2=D, 3=S).

Run:  python3 build_fplib.py   (from tools/)
"""
import os
import shutil
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "lib")
VENDOR = os.path.join(LIB, "vendor")
PRETTY = os.path.join(LIB, "labbench.pretty")

# vendor file -> project footprint name  (vetted 2026-07-15 vs local datasheets)
VETTED = {
    "LM5145RGYR_x/LM5145RGYR/KiCad/RGY0020B.kicad_mod":
        "LM5145_RGY0020B",                  # pin15 = isolated EP lead, pad21 = die pad
    "LMR36015AQRNXRQ1_x/LMR36015AQRNXRQ1/KiCad/LMR36015AQRNXRQ1.kicad_mod":
        "LMR36015_RNX_VQFN-HR-12",          # 1,11=PGND 2,10=VIN 12=SW strip 3=NC
    "DAC80502DRXT_x/DAC80502DRXT/KiCad/SON50P250X250X80-10N.kicad_mod":
        "DAC80502_DRX_WSON-10",             # DRX has NO exposed pad (ds mech drawing)
}


def import_vendor():
    tmp = tempfile.mkdtemp(suffix=".pretty")
    for rel, name in VETTED.items():
        src = os.path.join(VENDOR, rel)
        base = os.path.basename(src)[:-len(".kicad_mod")]
        shutil.copy(src, os.path.join(tmp, base + ".kicad_mod"))
        fp = pcbnew.FootprintLoad(tmp, base)
        fp.SetFPID(pcbnew.LIB_ID("labbench", name))
        # UL exports leave Reference as a literal like "REF**" on Fab only; fine.
        pcbnew.FootprintSave(PRETTY, fp)
        print(f"  merged {base} -> labbench:{name}")


def powerfet_son5x6():
    """TI Q5A (VSON 5x6) land pattern, GDS pad numbering.

    Datasheet fig M0139-01 (mid-tolerance): small-lead pads 0.75x0.645 on
    1.27 pitch, column right edge +3.455; drain 4.95x4.51 with four
    0.655x0.645 lead extensions, pattern left edge -3.455. Package pins:
    1-3 = S (bottom..), 4 = G (top), 5-8 + tab = D.
    """
    fp = pcbnew.FOOTPRINT(pcbnew.BOARD())
    fp.SetFPID(pcbnew.LIB_ID("labbench", "PowerFET_SON5x6_GDS"))
    fp.SetAttributes(pcbnew.FP_SMD)
    fp.SetDescription("TI SON 5x6 single NFET (Q5A/CSD18563Q5A land, SLPS444C 7.2); "
                      "pads renumbered for Device:Q_NMOS_GDS (1=G 2=D 3=S)")
    fp.SetKeywords("mosfet son 5x6 q5a nexfet")

    def pad(num, x, y, w, h, paste_ratio=0.0):
        p = pcbnew.PAD(fp)
        p.SetNumber(str(num))
        p.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT)
        p.SetRoundRectRadiusRatio(0.1)
        p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        p.SetLayerSet(pcbnew.PAD.SMDMask())
        p.SetPos0(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        p.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(w), pcbnew.FromMM(h)))
        p.SetDrawCoord()
        if paste_ratio:
            p.SetLocalSolderPasteMarginRatio(paste_ratio)
        fp.Add(p)

    # gate (package pin 4, top right)
    pad(1, 3.08, -1.905, 0.75, 0.645)
    # sources (package pins 3,2,1 top->bottom)
    for y in (-0.635, 0.635, 1.905):
        pad(3, 3.08, y, 0.75, 0.645)
    # drain tab + lead extensions (package pins 5-8 + die pad); reduced paste
    pad(2, -0.325, 0.0, 4.95, 4.51, paste_ratio=-0.12)
    for y in (-1.905, -0.635, 0.635, 1.905):
        pad(2, -3.0775, y, 0.755, 0.645)

    def line(layer, x1, y1, x2, y2, w=0.12):
        s = pcbnew.FP_SHAPE(fp)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart0(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
        s.SetEnd0(pcbnew.VECTOR2I(pcbnew.FromMM(x2), pcbnew.FromMM(y2)))
        s.SetLayer(layer)
        s.SetWidth(pcbnew.FromMM(w))
        s.SetDrawCoord()
        fp.Add(s)

    def rect(layer, x1, y1, x2, y2, w=0.05):
        for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
                     ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
            line(layer, a[0], a[1], b[0], b[1], w)

    # body 6.0 x 4.9 on Fab; silk = top/bottom edges only (pads occupy sides)
    rect(pcbnew.F_Fab, -3.0, -2.45, 3.0, 2.45, 0.1)
    line(pcbnew.F_SilkS, -2.9, -2.56, 2.35, -2.56)
    line(pcbnew.F_SilkS, -2.9, 2.56, 2.35, 2.56)
    # pin-1 (gate) marker: dot beside top-right pad
    c = pcbnew.FP_SHAPE(fp)
    c.SetShape(pcbnew.SHAPE_T_CIRCLE)
    c.SetStart0(pcbnew.VECTOR2I(pcbnew.FromMM(3.9), pcbnew.FromMM(-1.905)))
    c.SetEnd0(pcbnew.VECTOR2I(pcbnew.FromMM(4.0), pcbnew.FromMM(-1.905)))
    c.SetLayer(pcbnew.F_SilkS)
    c.SetWidth(pcbnew.FromMM(0.2))
    c.SetDrawCoord()
    fp.Add(c)
    rect(pcbnew.F_CrtYd, -3.7, -2.71, 3.7, 2.71)

    ref = fp.Reference()
    ref.SetPos0(pcbnew.VECTOR2I(0, pcbnew.FromMM(-3.3)))
    ref.SetDrawCoord()
    val = fp.Value()
    val.SetPos0(pcbnew.VECTOR2I(0, pcbnew.FromMM(3.3)))
    val.SetLayer(pcbnew.F_Fab)
    val.SetDrawCoord()

    pcbnew.FootprintSave(PRETTY, fp)
    print("  generated labbench:PowerFET_SON5x6_GDS")


def lm5143_rha0040p():
    """TI RHA0040P (VQFNP 6x6, 40 pin) land pattern, lm5143.pdf p.68:
    40 pads 0.25x0.6 on 0.5 pitch (10/side, centers +/-2.6 from center,
    row -2.25..+2.25), EP 3.3x3.3 = pad 41. None of the stock Texas_RHA
    variants match (EP 4.6/4.15/2.9/3.52x2.62 vs 3.3 square)."""
    fp = pcbnew.FOOTPRINT(pcbnew.BOARD())
    fp.SetFPID(pcbnew.LIB_ID("labbench", "LM5143_RHA0040P"))
    fp.SetAttributes(pcbnew.FP_SMD)
    fp.SetDescription("TI VQFNP-40 RHA0040P 6x6mm P0.5mm EP3.3x3.3 "
                      "(lm5143.pdf land pattern, verified 2026-07-16)")
    fp.SetKeywords("vqfn 40 rha0040p lm5143")

    def pad(num, x, y, w, h, paste_ratio=0.0):
        p = pcbnew.PAD(fp)
        p.SetNumber(str(num))
        p.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT)
        p.SetRoundRectRadiusRatio(0.2)
        p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        p.SetLayerSet(pcbnew.PAD.SMDMask())
        p.SetPos0(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        p.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(w), pcbnew.FromMM(h)))
        p.SetDrawCoord()
        if paste_ratio:
            p.SetLocalSolderPasteMarginRatio(paste_ratio)
        fp.Add(p)

    row = [round(-2.25 + 0.5 * i, 2) for i in range(10)]
    for i, y in enumerate(row):                 # 1-10 left column, top->bottom
        pad(1 + i, -2.6, y, 0.6, 0.25)
    for i, x in enumerate(row):                 # 11-20 bottom row, left->right
        pad(11 + i, x, 2.6, 0.25, 0.6)
    for i, y in enumerate(reversed(row)):       # 21-30 right column, bottom->top
        pad(21 + i, 2.6, y, 0.6, 0.25)
    for i, x in enumerate(reversed(row)):       # 31-40 top row, right->left
        pad(31 + i, x, -2.6, 0.25, 0.6)
    pad(41, 0, 0, 3.3, 3.3, paste_ratio=-0.2)   # EP, reduced paste

    def line(layer, x1, y1, x2, y2, w=0.12):
        s = pcbnew.FP_SHAPE(fp)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart0(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
        s.SetEnd0(pcbnew.VECTOR2I(pcbnew.FromMM(x2), pcbnew.FromMM(y2)))
        s.SetLayer(layer)
        s.SetWidth(pcbnew.FromMM(w))
        s.SetDrawCoord()
        fp.Add(s)

    def rect(layer, x1, y1, x2, y2, w=0.05):
        for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
                     ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
            line(layer, a[0], a[1], b[0], b[1], w)

    rect(pcbnew.F_Fab, -3.0, -3.0, 3.0, 3.0, 0.1)
    # silk corners only (pads occupy all four sides); pin-1 dot at top-left
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        line(pcbnew.F_SilkS, sx * 3.11, sy * 3.11, sx * 3.11, sy * 2.75)
        line(pcbnew.F_SilkS, sx * 3.11, sy * 3.11, sx * 2.75, sy * 3.11)
    c = pcbnew.FP_SHAPE(fp)
    c.SetShape(pcbnew.SHAPE_T_CIRCLE)
    c.SetStart0(pcbnew.VECTOR2I(pcbnew.FromMM(-3.6), pcbnew.FromMM(-2.25)))
    c.SetEnd0(pcbnew.VECTOR2I(pcbnew.FromMM(-3.5), pcbnew.FromMM(-2.25)))
    c.SetLayer(pcbnew.F_SilkS)
    c.SetWidth(pcbnew.FromMM(0.2))
    c.SetDrawCoord()
    fp.Add(c)
    rect(pcbnew.F_CrtYd, -3.25, -3.25, 3.25, 3.25)

    ref = fp.Reference()
    ref.SetPos0(pcbnew.VECTOR2I(0, pcbnew.FromMM(-4.1)))
    ref.SetDrawCoord()
    val = fp.Value()
    val.SetPos0(pcbnew.VECTOR2I(0, pcbnew.FromMM(4.1)))
    val.SetLayer(pcbnew.F_Fab)
    val.SetDrawCoord()

    pcbnew.FootprintSave(PRETTY, fp)
    print("  generated labbench:LM5143_RHA0040P")


def write_fp_lib_table():
    path = os.path.join(LIB, "..", "fp-lib-table")
    with open(path, "w") as f:
        f.write('(fp_lib_table\n  (version 7)\n'
                '  (lib (name "labbench")(type "KiCad")'
                '(uri "${KIPRJMOD}/lib/labbench.pretty")(options "")(descr "project footprints"))\n)\n')
    print(f"  wrote {os.path.relpath(path, HERE)}")


if __name__ == "__main__":
    os.makedirs(PRETTY, exist_ok=True)
    import_vendor()
    powerfet_son5x6()
    lm5143_rha0040p()
    write_fp_lib_table()
    print("build_fplib: done")
