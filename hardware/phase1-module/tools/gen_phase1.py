"""Generate the phase1-module KiCad project.

Currently draws: root sheet, control-core (complete), stubs for the
remaining sheets. Connectivity is label-based; EXPECTED_NETS at the bottom
is the single source of truth checked by check_netlist.py.

Run:  python3 gen_phase1.py   (from tools/, writes into the parent dir)
"""
import os
import kicad_gen as kg

PROJECT = "phase1-module"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

ROOT_UUID = "e63e39d7-6ac0-4ffa-9e5c-2b84c50a0001"
SHEETS = [  # name, fixed sheet-element uuid, page
    ("power-stage",  "e63e39d7-6ac0-4ffa-9e5c-2b84c50a0010", "2"),
    ("control-core", "e63e39d7-6ac0-4ffa-9e5c-2b84c50a0011", "3"),
    ("sensing",      "e63e39d7-6ac0-4ffa-9e5c-2b84c50a0012", "4"),
    ("disconnect",   "e63e39d7-6ac0-4ffa-9e5c-2b84c50a0013", "5"),
    ("aux-rails",    "e63e39d7-6ac0-4ffa-9e5c-2b84c50a0014", "6"),
    ("mcu-can",      "e63e39d7-6ac0-4ffa-9e5c-2b84c50a0015", "7"),
    ("io",           "e63e39d7-6ac0-4ffa-9e5c-2b84c50a0016", "8"),
]

R_FP = "Resistor_SMD:R_0402_1005Metric"
C_FP = "Capacitor_SMD:C_0402_1005Metric"


def build_control_core():
    path = f"/{ROOT_UUID}/{dict((n, u) for n, u, _ in SHEETS)['control-core']}"
    sh = kg.Sheet(PROJECT, path)

    R = kg.get_symbol("Device", "R")
    C = kg.get_symbol("Device", "C")
    DAC = kg.get_symbol("Analog_DAC", "DAC80502")
    OPA = kg.get_symbol("Amplifier_Operational", "OPA2333xxDGK")
    DSCH = kg.get_symbol("Diode", "BAT54W")

    def res(ref, val, x, y, rot=0):
        return sh.add(kg.Placed(R, ref, val, x, y, rot, footprint=R_FP))

    def cap(ref, val, x, y, rot=0):
        return sh.add(kg.Placed(C, ref, val, x, y, rot, footprint=C_FP))

    def gl(net, part, pin, shape="passive"):
        sh.glabel(net, part.pin_pos(pin), rot=part.label_rot(pin), shape=shape)

    def ll(net, part, pin):
        sh.label(net, part.pin_pos(pin), rot=part.label_rot(pin))

    # ---- DAC80502: 16-bit dual reference source (V_REF / I_REF) ----
    u1 = sh.add(kg.Placed(DAC, "U1", "DAC80502", 50.8, 101.6,
                          footprint="Package_SON:WSON-10-1EP_2.5x2.5mm_P0.5mm"))
    gl("V_REF", u1, 2, shape="output")                      # VOUTA
    gl("I_REF", u1, 9, shape="output")                      # VOUTB
    gl("DAC_SPI2C", u1, 5)                                  # mode strap, see note
    gl("DAC_NSYNC", u1, 7, shape="input")
    gl("DAC_SDI", u1, 8, shape="input")
    gl("DAC_SCLK", u1, 6, shape="input")
    sh.power("3V3", *u1.pin_pos(1))
    sh.power("AGND", *u1.pin_pos(4), ground=True)
    sh.power("AGND", *u1.pin_pos(3), ground=True)           # RSTSEL low: POR to zero-scale
    ll("DAC_REFIO", u1, 10)
    c_ref = cap("C4", "150n", 81.28, 111.76)
    ll("DAC_REFIO", c_ref, 1)
    sh.power("AGND", *c_ref.pin_pos(2), ground=True)
    c_dac = cap("C3", "100n", 27.94, 111.76)
    sh.power("3V3", *c_dac.pin_pos(1))
    sh.power("AGND", *c_dac.pin_pos(2), ground=True)

    # ---- CV error amplifier (U2A): Type-II integrator + diode-OR row ----
    u2a = sh.add(kg.Placed(OPA, "U2", "OPA2189", 137.16, 76.2, unit=1,
                           footprint="Package_SO:VSSOP-8_3x3mm_P0.65mm"))
    gl("V_MEAS", u2a, 3, shape="input")                     # +in
    ll("EAV_INV", u2a, 2)                                   # -in
    r_av = res("R3", "10K 0.1%", 96.52, u2a.pin_pos(2)[1], rot=90)
    gl("V_REF", r_av, 1, shape="input")
    ll("EAV_INV", r_av, 2)
    c_fv = cap("C1", "10n", 96.52, 58.42, rot=90)           # Type-II: integrator
    r_zv = res("R4", "33K", 121.92, 58.42, rot=90)          # Type-II: zero
    ll("EAV_INV", c_fv, 1)
    ll("EAV_FB", c_fv, 2)
    ll("EAV_FB", r_zv, 1)
    ll("EA_V_OUT", r_zv, 2)
    d_v = sh.add(kg.Placed(DSCH, "D1", "BAT54W", 160.02, 76.2, rot=180,
                           footprint="Package_TO_SOT_SMD:SOT-323_SC-70"))
    ll("EA_V_OUT", u2a, 1)
    ll("EA_V_OUT", d_v, 1)                                  # pin 1 = anode (faces EA out)
    ll("EAV_INJ", d_v, 3)                                   # pin 3 = cathode -> R_inj -> FB
    sh.no_connect(d_v.pin_pos(2))                           # pin 2 = NC on SC-70
    r_iv = res("R5", "3.9K", 182.88, 76.2, rot=90)
    ll("EAV_INJ", r_iv, 1)
    gl("FB", r_iv, 2, shape="output")

    # ---- CC error amplifier (U2B): mirror of the CV loop ----
    u2b = sh.add(kg.Placed(OPA, "U2", "OPA2189", 137.16, 127.0, unit=2,
                           footprint="Package_SO:VSSOP-8_3x3mm_P0.65mm"))
    gl("I_MEAS", u2b, 5, shape="input")                     # +in
    ll("EAI_INV", u2b, 6)                                   # -in
    r_ai = res("R6", "10K 0.1%", 96.52, u2b.pin_pos(6)[1], rot=90)
    gl("I_REF", r_ai, 1, shape="input")
    ll("EAI_INV", r_ai, 2)
    c_fi = cap("C2", "22n", 96.52, 109.22, rot=90)
    r_zi = res("R7", "15K", 121.92, 109.22, rot=90)
    ll("EAI_INV", c_fi, 1)
    ll("EAI_FB", c_fi, 2)
    ll("EAI_FB", r_zi, 1)
    ll("EA_I_OUT", r_zi, 2)
    d_i = sh.add(kg.Placed(DSCH, "D2", "BAT54W", 160.02, 127.0, rot=180,
                           footprint="Package_TO_SOT_SMD:SOT-323_SC-70"))
    ll("EA_I_OUT", u2b, 7)
    ll("EA_I_OUT", d_i, 1)                                  # anode
    ll("EAI_INJ", d_i, 3)                                   # cathode
    sh.no_connect(d_i.pin_pos(2))
    r_ii = res("R8", "3.9K", 182.88, 127.0, rot=90)
    ll("EAI_INJ", r_ii, 1)
    gl("FB", r_ii, 2, shape="output")

    # ---- op-amp power unit (U2C) + decoupling ----
    u2c = sh.add(kg.Placed(OPA, "U2", "OPA2189", 50.8, 154.94, unit=3,
                           footprint="Package_SO:VSSOP-8_3x3mm_P0.65mm"))
    sh.power("5V0", *u2c.pin_pos(8))
    sh.power("AGND", *u2c.pin_pos(4), ground=True)
    c_op = cap("C5", "100n", 71.12, 154.94)
    sh.power("5V0", *c_op.pin_pos(1))
    sh.power("AGND", *c_op.pin_pos(2), ground=True)

    # ---- base divider: hardware output ceiling 0.8V * 26.5 = 21.2V ----
    r_top = res("R1", "25.5K 0.1%", 218.44, 88.9)
    r_bot = res("R2", "1.0K 0.1%", 218.44, 106.68)
    gl("VOUT_INT", r_top, 1, shape="input")
    gl("FB", r_top, 2, shape="output")
    gl("FB", r_bot, 1, shape="output")
    sh.power("AGND", *r_bot.pin_pos(2), ground=True)

    # ---- power flags (temporary home until aux-rails is drawn) ----
    for i, net in enumerate(("3V3", "5V0", "AGND")):
        f = sh.pwr_flag(33.02 + 12.7 * i, 177.8)
        sh.power(net, *f.pin_pos(1), ground=(net == "AGND"))

    sh.text("CONTROL CORE - dual error amps + diode-OR minimum selector into LM5145 FB node.\\n"
            "Whichever amp demands the LOWER output wins -> automatic CV/CC crossover.\\n"
            "Accuracy is owned by the 0.1% dividers + DAC + amp offset (see docs/06 s.4).", 33.02, 40.64)
    sh.text("VERIFY vs datasheet before ordering: DAC80502 SPI2C strap level for SPI mode,\\n"
            "REFIO cap value, WSON vs VSSOP package choice. DAC runs on 3V3 (STM32 logic levels).",
            33.02, 190.5)
    return sh


def build_root():
    sh = kg.Sheet(PROJECT, "/")
    sh.uuid = ROOT_UUID
    x, y = 38.1, 38.1
    for name, su, page in SHEETS:
        sh.items.append(f"""  (sheet (at {x} {y}) (size 38.1 15.24) (fields_autoplaced)
    (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0))
    (uuid {su})
    (property "Sheetname" "{name}" (at {x} {y - 0.8} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
    (property "Sheetfile" "{name}.kicad_sch" (at {x} {y + 15.24 + 0.6} 0) (effects (font (size 1.27 1.27)) (justify left top)))
    (instances (project "{PROJECT}" (path "/{ROOT_UUID}" (page "{page}"))))
  )""")
        x += 50.8
        if x > 200:
            x, y = 38.1, y + 30.48
    sh.text("Lab_Bench phase-1 module - 150W CV/CC prototype. Generated schematic;\\n"
            "see hardware/phase1-module/CAPTURE-GUIDE.md and docs/06.", 38.1, 139.7)
    return sh


def build_stub(name):
    path = f"/{ROOT_UUID}/{dict((n, u) for n, u, _ in SHEETS)[name]}"
    sh = kg.Sheet(PROJECT, path)
    sh.text(f"{name}: not yet drawn - see docs/06-phase1-circuit-design.md", 38.1, 38.1)
    return sh


def main():
    root = build_root()
    open(os.path.join(OUT, f"{PROJECT}.kicad_sch"), "w").write(root.emit())
    cc = build_control_core()
    open(os.path.join(OUT, "control-core.kicad_sch"), "w").write(cc.emit())
    for name, _, _ in SHEETS:
        if name == "control-core":
            continue
        open(os.path.join(OUT, f"{name}.kicad_sch"), "w").write(build_stub(name).emit())
    pro = os.path.join(OUT, f"{PROJECT}.kicad_pro")
    if not os.path.exists(pro):
        open(pro, "w").write('{\n  "meta": { "filename": "%s.kicad_pro", "version": 1 },\n'
                             '  "schematic": { "legacy_lib_dir": "", "legacy_lib_list": [] }\n}\n' % PROJECT)
    print("generated:", PROJECT)


# Single source of truth for connectivity, asserted by check_netlist.py.
# net name -> set of "REF.PIN" (net names may appear with sheet-path prefixes).
EXPECTED_NETS = {
    "V_REF":     {"U1.2", "R3.1"},
    "I_REF":     {"U1.9", "R6.1"},
    "EAV_INV":   {"R3.2", "U2.2", "C1.1"},
    "EAV_FB":    {"C1.2", "R4.1"},
    "EA_V_OUT":  {"U2.1", "R4.2", "D1.1"},
    "EAV_INJ":   {"D1.3", "R5.1"},
    "EAI_INV":   {"R6.2", "U2.6", "C2.1"},
    "EAI_FB":    {"C2.2", "R7.1"},
    "EA_I_OUT":  {"U2.7", "R7.2", "D2.1"},
    "EAI_INJ":   {"D2.3", "R8.1"},
    "FB":        {"R5.2", "R8.2", "R1.2", "R2.1"},
    "VOUT_INT":  {"R1.1"},
    "V_MEAS":    {"U2.3"},
    "I_MEAS":    {"U2.5"},
    "DAC_REFIO": {"U1.10", "C4.1"},
    "DAC_NSYNC": {"U1.7"},
    "DAC_SDI":   {"U1.8"},
    "DAC_SCLK":  {"U1.6"},
    "DAC_SPI2C": {"U1.5"},
    "3V3":       {"U1.1", "C3.1"},
    "5V0":       {"U2.8", "C5.1"},
    "AGND":      {"U1.4", "U1.3", "C3.2", "C4.2", "C5.2", "U2.4", "R2.2"},
}

if __name__ == "__main__":
    main()
