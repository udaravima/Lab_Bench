"""Synthesized box symbols for parts with no vetted vendor ECAD download.

Each symbol's pin map is transcribed from the local datasheet's pin-function
table (docs/datasheets/, page refs below) — same vetting bar as
merge_vendor.py, just with the s-expression built here instead of unzipped.
merge_vendor.py includes these blocks when it rebuilds labbench.kicad_sym.
"""

FONT = "(effects (font (size 1.27 1.27)))"


def box_symbol(name, left, right, bottom=(), width=20.32, descr=""):
    """A rectangle with 2.54-grid pins. left/right/bottom: [(number, pin_name)].
    Returns the (symbol ...) block in the exact shape kicad_gen.Symbol parses."""
    rows = max(len(left), len(right))
    half_h = ((rows - 1) * 2.54) / 2 + 2.54
    half_w = width / 2
    pins = []

    def pin(num, pname, x, y, rot):
        pins.append(
            f'      (pin passive line (at {x} {y} {rot}) (length 2.54) '
            f'(name "{pname}" {FONT}) (number "{num}" {FONT}))')

    for i, (num, pname) in enumerate(left):
        pin(num, pname, -half_w - 2.54, round(half_h - 2.54 - i * 2.54, 2), 0)
    for i, (num, pname) in enumerate(right):
        pin(num, pname, half_w + 2.54, round(half_h - 2.54 - i * 2.54, 2), 180)
    for i, (num, pname) in enumerate(bottom):
        x = round((i - (len(bottom) - 1) / 2) * 2.54, 2)
        pin(num, pname, x, -half_h - 2.54, 90)

    pin_block = "\n".join(pins)
    return f"""(symbol "{name}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes)
    (property "Reference" "U" (at {-half_w} {half_h + 1.27} 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "{name}" (at {-half_w} {-half_h - 1.27} 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "{descr}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (symbol "{name}_0_1"
      (rectangle (start {-half_w} {half_h}) (end {half_w} {-half_h})
        (stroke (width 0.254) (type default)) (fill (type background)))
    )
    (symbol "{name}_1_1"
{pin_block}
    )
  )"""


def lm5143rhar():
    """LM5143 dual synchronous buck controller, VQFN-40 RHA0040P.
    Pin map: lm5143.pdf Table 7-1 (verified 2026-07-16). EP = pad 41,
    'connect the exposed pad on the bottom to AGND and PGND on the PCB'."""
    left = [                       # control / analog side
        ("31", "EN1"), ("40", "EN2"), ("37", "RT"), ("38", "DITH"),
        ("34", "MODE"), ("33", "DEMB"), ("39", "SYNCOUT"), ("32", "RES"),
        ("30", "SS1"), ("1", "SS2"), ("29", "COMP1"), ("2", "COMP2"),
        ("28", "FB1"), ("3", "FB2"), ("27", "CS1"), ("26", "VOUT1"),
        ("4", "CS2"), ("5", "VOUT2"), ("36", "VDDA"), ("35", "AGND"),
    ]
    right = [                      # power / gate-drive side
        ("25", "VIN"), ("6", "VCCX"), ("15", "VCC"), ("16", "VCC"),
        ("20", "HB1"), ("22", "HO1"), ("23", "HOL1"), ("21", "SW1"),
        ("18", "LO1"), ("19", "LOL1"), ("17", "PGND1"), ("11", "HB2"),
        ("9", "HO2"), ("8", "HOL2"), ("10", "SW2"), ("13", "LO2"),
        ("12", "LOL2"), ("14", "PGND2"), ("24", "PG1"), ("7", "PG2"),
    ]
    bottom = [("41", "EP")]
    return box_symbol("LM5143RHAR", left, right, bottom, width=25.4,
                      descr="lm5143.pdf Table 7-1 (pin map verified 2026-07-16)")


def lm5069mm2():
    """LM5069-2 hot-swap controller (auto-retry), VSSOP-10 DGS.
    Pin map: lm5069.pdf Pin Functions (verified 2026-07-16). No exposed pad."""
    left = [("2", "VIN"), ("3", "UVLO"), ("4", "OVLO"), ("7", "PWR"), ("6", "TIMER")]
    right = [("1", "SENSE"), ("10", "GATE"), ("9", "OUT"), ("8", "PGD"), ("5", "GND")]
    return box_symbol("LM5069MM-2", left, right, width=17.78,
                      descr="lm5069.pdf Pin Functions (pin map verified 2026-07-16)")


def tpd2e001drl():
    """TPD2E001 2-channel USB ESD, DRL (SOT-5X3).
    Pin map: tpd2e001.pdf Pin Functions, DRL column (verified 2026-07-17):
    1=VCC, 2=NC, 3=IO1, 4=GND, 5=IO2."""
    left = [("3", "IO1"), ("5", "IO2")]
    right = [("1", "VCC"), ("4", "GND"), ("2", "NC")]
    return box_symbol("TPD2E001DRL", left, right, width=12.7,
                      descr="tpd2e001.pdf Pin Functions DRL (verified 2026-07-17)")


SYNTH = {
    "LM5143RHAR": (lm5143rhar, "lm5143.pdf Table 7-1 (2026-07-16)"),
    "LM5069MM-2": (lm5069mm2, "lm5069.pdf Pin Functions (2026-07-16)"),
    "TPD2E001DRL": (tpd2e001drl, "tpd2e001.pdf Pin Functions DRL (2026-07-17)"),
}
