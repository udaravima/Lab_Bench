"""Generate the phase1-module KiCad project.

Currently draws: root sheet, control-core (complete), stubs for the
remaining sheets. Connectivity is label-based; EXPECTED_NETS at the bottom
is the single source of truth checked by check_netlist.py.

Run:  python3 gen_phase1.py   (from tools/, writes into the parent dir)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
import kicad_gen as kg          # noqa: E402  (shared, hardware/common)
import sheets_common as sc      # noqa: E402

kg.add_lib_dir(os.path.join(HERE, "..", "lib"))

PROJECT = "phase1-module"
OUT = os.path.join(HERE, "..")

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

R_FP = "Resistor_SMD:R_0603_1608Metric"      # 0603: hand-assembled board
C_FP = "Capacitor_SMD:C_0603_1608Metric"


def _sheet(name):
    path = f"/{ROOT_UUID}/{dict((n, u) for n, u, _ in SHEETS)[name]}"
    sh = kg.Sheet(PROJECT, path)

    def res(ref, val, x, y, rot=0):
        return sh.add(kg.Placed(kg.get_symbol("Device", "R"), ref, val, x, y, rot, footprint=R_FP))

    def cap(ref, val, x, y, rot=0, fp=C_FP):
        return sh.add(kg.Placed(kg.get_symbol("Device", "C"), ref, val, x, y, rot, footprint=fp))

    def gl(net, part, pin, shape="passive"):
        sh.glabel(net, part.pin_pos(pin), rot=part.label_rot(pin), shape=shape)

    def ll(net, part, pin):
        sh.label(net, part.pin_pos(pin), rot=part.label_rot(pin))

    return sh, res, cap, gl, ll


C_BULK = "Capacitor_SMD:C_1210_3225Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"


def build_power_stage():
    sh, res, cap, gl, ll = _sheet("power-stage")
    LM = kg.get_symbol("labbench", "LM5145RGYR")
    QN = kg.get_symbol("Device", "Q_NMOS_GDS")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")
    DS = kg.get_symbol("Diode", "BAT54W")
    L = kg.get_symbol("Device", "L")

    u3 = sh.add(kg.Placed(LM, "U3", "LM5145RGYR", 76.2, 106.68,
                          footprint="labbench:LM5145_RGY0020B"))
    # -- enable chain: UVLO divider + kill FET
    r20 = res("R20", "100K 1%", 30.48, 78.74)
    r21 = res("R21", "13K 1%", 30.48, 93.98)
    gl("VBUS_F", r20, 1, shape="input")
    ll("PS_EN", r20, 2)
    ll("PS_EN", r21, 1)
    sh.power("AGND", *r21.pin_pos(2), ground=True)
    ll("PS_EN", u3, 1)
    q5 = sh.add(kg.Placed(Q2N, "Q5", "2N7002", 15.24, 106.68, footprint=SOT23))
    ll("PS_EN", q5, 3)
    sh.power("AGND", *q5.pin_pos(2), ground=True)
    gl("EN_KILL", q5, 1, shape="input")
    # kill logic: EN_KILL = NOT(HW_EN) OR PS_OFF, made with Q6 + diode-OR
    q6 = sh.add(kg.Placed(Q2N, "Q6", "2N7002", 15.24, 137.16, footprint=SOT23))
    gl("HW_EN", q6, 1, shape="input")
    sh.power("AGND", *q6.pin_pos(2), ground=True)
    ll("KILL_HW", q6, 3)
    r22 = res("R22", "100K", 30.48, 124.46)
    sh.power("5V0", *r22.pin_pos(1))
    ll("KILL_HW", r22, 2)
    d4 = sh.add(kg.Placed(DS, "D4", "BAT54W", 43.18, 137.16,
                          footprint="Package_TO_SOT_SMD:SOT-323_SC-70"))
    ll("KILL_HW", d4, 1)
    gl("EN_KILL", d4, 3, shape="output")
    sh.no_connect(d4.pin_pos(2))
    d3 = sh.add(kg.Placed(DS, "D3", "BAT54W", 43.18, 152.4,
                          footprint="Package_TO_SOT_SMD:SOT-323_SC-70"))
    gl("PS_OFF", d3, 1, shape="input")
    gl("EN_KILL", d3, 3, shape="output")
    sh.no_connect(d3.pin_pos(2))
    r23 = res("R23", "100K", 58.42, 144.78)
    gl("EN_KILL", r23, 1)
    sh.power("AGND", *r23.pin_pos(2), ground=True)
    r19 = res("R19", "100K", 15.24, 158.75)
    gl("HW_EN", r19, 1, shape="input")
    sh.power("AGND", *r19.pin_pos(2), ground=True)

    # -- housekeeping pins
    r26 = res("R26", "28.7K 1%", 40.64, 55.88)      # RT: 10^4/350kHz (ds eq.3)
    ll("PS_RT", u3, 2)
    ll("PS_RT", r26, 1)
    sh.power("AGND", *r26.pin_pos(2), ground=True)
    c18 = cap("C18", "47n", 53.34, 55.88)
    ll("PS_SS", u3, 3)
    ll("PS_SS", c18, 1)
    sh.power("AGND", *c18.pin_pos(2), ground=True)
    sh.no_connect(u3.pin_pos(7))                    # SYNCOUT
    r16 = res("R16", "100K", 66.04, 55.88)          # SYNCIN: high=FPWM, low=DEM (safe default)
    gl("PS_FPWM", u3, 8, shape="input")
    gl("PS_FPWM", r16, 1)
    sh.power("AGND", *r16.pin_pos(2), ground=True)
    sh.no_connect(u3.pin_pos(9))
    sh.no_connect(u3.pin_pos(16))
    r18 = res("R18", "100K", 78.74, 55.88)
    gl("PS_PGOOD", u3, 10, shape="output")
    gl("PS_PGOOD", r18, 2)
    sh.power("3V3", *r18.pin_pos(1))
    sh.power("AGND", *u3.pin_pos(6), ground=True)
    sh.power("AGND", *u3.pin_pos(15), ground=True)  # EP pin
    sh.power("AGND", *u3.pin_pos(21), ground=True)  # EP pad
    sh.power("PGND", *u3.pin_pos(12), ground=True)
    c29 = cap("C29", "2.2u", 91.44, 55.88)
    ll("PS_VCC", u3, 14)
    ll("PS_VCC", c29, 1)
    sh.power("PGND", *c29.pin_pos(2), ground=True)
    r29 = res("R29", "4.7", 106.68, 55.88, rot=90)  # VIN pin RC filter (ds 8.x note)
    gl("VBUS_F", r29, 1, shape="input")
    ll("PS_VIN", r29, 2)
    ll("PS_VIN", u3, 20)
    c28 = cap("C28", "100n", 118.11, 60.96)
    ll("PS_VIN", c28, 1)
    sh.power("PGND", *c28.pin_pos(2), ground=True)

    # -- compensation: Type-III around internal EA (COMP<->FB), values (bench/FRA)
    r24 = res("R24", "8.2K", 33.02, 172.72, rot=90)
    c24 = cap("C24", "8.2n", 53.34, 172.72, rot=90)
    gl("FB", r24, 1, shape="input")
    ll("COMP_Z", r24, 2)
    ll("COMP_Z", c24, 1)
    ll("PS_COMP", c24, 2)
    c25 = cap("C25", "120p", 43.18, 185.42, rot=90)
    gl("FB", c25, 1)
    ll("PS_COMP", c25, 2)
    ll("PS_COMP", u3, 4)
    gl("FB", u3, 5, shape="input")
    r25 = res("R25", "1.0K", 78.74, 172.72, rot=90) # feedforward branch across R_top
    c26 = cap("C26", "3.3n", 99.06, 172.72, rot=90)
    gl("VOUT_INT", r25, 1, shape="input")
    ll("COMP_FF", r25, 2)
    ll("COMP_FF", c26, 1)
    gl("FB", c26, 2)

    # -- half bridge
    q1 = sh.add(kg.Placed(QN, "Q1", "CSD18563Q5A", 154.94, 78.74, footprint="labbench:PowerFET_SON5x6_GDS"))
    q2 = sh.add(kg.Placed(QN, "Q2", "CSD18563Q5A", 154.94, 116.84, footprint="labbench:PowerFET_SON5x6_GDS"))
    gl("VBUS_F", q1, 2, shape="input")
    gl("SW", q1, 3)
    gl("SW", q2, 2)
    sh.power("PGND", *q2.pin_pos(3), ground=True)
    ll("HO_G", q1, 1)
    ll("HO_G", u3, 18)
    ll("LO_G", q2, 1)
    ll("LO_G", u3, 13)
    gl("SW", u3, 19)
    c27 = cap("C27", "100n", 127.0, 91.44, rot=90)
    ll("PS_BST", u3, 17)
    ll("PS_BST", c27, 1)
    gl("SW", c27, 2)
    r28 = res("R28", "365 1%", 127.0, 104.14, rot=90)  # ILIM->SW, 11A valley @ 6.7mR (ds eq.6)
    ll("PS_ILIM", u3, 11)
    ll("PS_ILIM", r28, 1)
    gl("SW", r28, 2)
    c19 = cap("C19", "15p", 111.76, 111.76)
    ll("PS_ILIM", c19, 1)
    sh.power("PGND", *c19.pin_pos(2), ground=True)

    l1 = sh.add(kg.Placed(L, "L1", "XAL1350-103ME 10u/14A", 180.34, 96.52, rot=90,
                          footprint="Inductor_SMD:L_Coilcraft_XAL1350-XXX"))
    gl("SW", l1, 1)
    gl("VOUT_INT", l1, 2, shape="output")
    # input/output banks + preload + snubber (DNP); one component per physical cap
    CPOL = kg.get_symbol("Device", "C_Polarized")
    cin = [cap(r, "22u/50V X7R", x, 146.05, fp="Capacitor_SMD:C_1210_3225Metric")
           for r, x in (("C20", 146.05), ("C75", 154.94), ("C76", 163.83), ("C77", 172.72))]
    c21 = sh.add(kg.Placed(CPOL, "C21", "220u/50V", 181.61, 146.05,
                           footprint="Capacitor_SMD:CP_Elec_10x10.5"))
    for c in cin + [c21]:
        gl("VBUS_F", c, 1, shape="input")
        sh.power("PGND", *c.pin_pos(2), ground=True)
    cpoly = [sh.add(kg.Placed(CPOL, r, "220u/25V poly", x, 146.05,
                              footprint="Capacitor_SMD:CP_Elec_8x11.9"))
             for r, x in (("C22", 193.04), ("C78", 201.93))]
    cout = [cap(r, "22u/25V X7R", x, 146.05, fp="Capacitor_SMD:C_1210_3225Metric")
            for r, x in (("C23", 210.82), ("C79", 219.71), ("C80", 228.6), ("C81", 237.49))]
    r27 = res("R27", "2.2K 1W preload", 246.38, 146.05)
    r27.footprint = "Resistor_SMD:R_2512_6332Metric"
    for c in cpoly + cout + [r27]:
        gl("VOUT_INT", c, 1, shape="input")
        sh.power("PGND", *c.pin_pos(2), ground=True)
    r17 = res("R17", "DNP snub", 255.27, 146.05)
    c17 = cap("C17", "DNP", 255.27, 160.02)
    gl("SW", r17, 1)
    ll("SNUB", r17, 2)
    ll("SNUB", c17, 1)
    sh.power("PGND", *c17.pin_pos(2), ground=True)

    sh.text("POWER STAGE: LM5145 sync buck, 350kHz (RT 28.7K), valley ILIM 11A (R28 365R\\n"
            "to SW, RDS(on) sensing). SYNCIN: MCU PS_FPWM (low=DEM battery-safe default).\\n"
            "EN chain: UVLO 10.5V divider; Q5 kills EN when EN_KILL = NOT(HW_EN) OR PS_OFF.\\n"
            "Type-III comp values are FRA starting points (docs/06 s.6).", 15.24, 33.02)
    return sh


def build_io():
    sh, res, cap, gl, ll = _sheet("io")
    C2 = kg.get_symbol("Connector_Generic", "Conn_01x02")
    C8 = kg.get_symbol("Connector_Generic", "Conn_01x08")
    FUSE = kg.get_symbol("Device", "Fuse")
    TVS = kg.get_symbol("Device", "D_TVS")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")
    DF = kg.get_symbol("Diode", "1N4148W")

    j1 = sh.add(kg.Placed(C2, "J1", "VBUS IN", 38.1, 78.74,
                          footprint="TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-2-5.0-H_1x02_P5.00mm_Horizontal"))
    ll("VBUS", j1, 1)
    sh.power("PGND", *j1.pin_pos(2), ground=True)
    f1 = sh.add(kg.Placed(FUSE, "F1", "10A blade", 63.5, 76.2, rot=90,
                          footprint="Fuse:Fuse_Blade_Mini_directSolder"))
    ll("VBUS", f1, 1)
    gl("VBUS_F", f1, 2, shape="output")
    d5 = sh.add(kg.Placed(TVS, "D5", "SMBJ33A", 82.55, 88.9,
                          footprint="Diode_SMD:D_SMB"))
    gl("VBUS_F", d5, 1, shape="input")
    sh.power("PGND", *d5.pin_pos(2), ground=True)

    j4 = sh.add(kg.Placed(C2, "J4", "OUTPUT", 38.1, 116.84,
                          footprint="TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-2-5.0-H_1x02_P5.00mm_Horizontal"))
    gl("VOUT", j4, 1, shape="input")
    sh.power("PGND", *j4.pin_pos(2), ground=True)

    j5 = sh.add(kg.Placed(C8, "J5", "BACKPLANE", 38.1, 165.1,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical"))
    gl("CAN_H", j5, 1)
    gl("CAN_L", j5, 2)
    gl("HW_EN", j5, 3, shape="input")
    gl("SLOT_ID0", j5, 4)
    gl("SLOT_ID1", j5, 5)
    gl("SLOT_ID2", j5, 6)
    sh.power("PGND", *j5.pin_pos(7), ground=True)   # PRESENT strap
    sh.power("PGND", *j5.pin_pos(8), ground=True)

    j6 = sh.add(kg.Placed(C2, "J6", "FAN", 130.81, 78.74,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"))
    sh.power("5V0", *j6.pin_pos(1))
    ll("FAN_NEG", j6, 2)
    q8 = sh.add(kg.Placed(Q2N, "Q8", "2N7002", 130.81, 106.68, footprint=SOT23))
    gl("FAN_PWM", q8, 1, shape="input")
    sh.power("PGND", *q8.pin_pos(2), ground=True)
    ll("FAN_NEG", q8, 3)
    d6 = sh.add(kg.Placed(DF, "D6", "1N4148W", 148.59, 78.74, rot=90,
                          footprint="Diode_SMD:D_SOD-323"))
    sh.power("5V0", *d6.pin_pos(1))                 # K to rail (flyback)
    ll("FAN_NEG", d6, 2)                            # A to switched node

    fl = sh.pwr_flag(190.5, 63.5)
    sh.power("PGND", *fl.pin_pos(1), ground=True)
    fl = sh.pwr_flag(205.74, 63.5)
    sh.glabel("VBUS_F", fl.pin_pos(1))
    fl = sh.pwr_flag(220.98, 63.5)
    sh.glabel("VOUT", fl.pin_pos(1))
    fl = sh.pwr_flag(236.22, 63.5)
    sh.label("VBUS", fl.pin_pos(1))

    sh.text("IO: fused VBUS in (10A @ 150W/24V=6.3A nom), SMBJ33A TVS, output terminals,\\n"
            "backplane header (CAN, HW_EN, slot straps, PRESENT->PGND), fan low-side switch.\\n"
            "FAN_PWM: route to MCU PB10 in phase 2; phase 1 may strap fan always-on.", 15.24, 33.02)
    return sh


# ---- shared sheets (hardware/common/sheets_common.py) with Phase-1 values --

def _shared(name, builder, params):
    def build():
        path = f"/{ROOT_UUID}/{dict((n, u) for n, u, _ in SHEETS)[name]}"
        return builder(kg.Sheet(PROJECT, path), params)
    return build


P1_CONTROL_CORE = {
    "r_top": "25.5K 0.1%",    # ceiling 0.8V x 26.5 = 21.2V (LM5145 FB = 0.8V)
    "r_inj": "3.9K",
    "note": "CONTROL CORE - dual error amps + diode-OR minimum selector into LM5145 FB node.\\n"
            "Whichever amp demands the LOWER output wins -> automatic CV/CC crossover.\\n"
            "Accuracy is owned by the 0.1% dividers + DAC + amp offset (see docs/06 s.4).",
}
P1_SENSING = {
    "shunts": [("R30", "2m/1W Kelvin")],
    "div_top": "69.8K 0.1%",
    "droop": None,
    "note": "SENSING: 2m shunt (Kelvin) between VOUT_INT and disconnect. INA240A3 (x100,\\n"
            "0.2V/A, 1.6V @ 8A) feeds the CC loop; INA228 feeds telemetry. V divider /8 from\\n"
            "VOUT terminals. NT1 = the single AGND-PGND tie point: at the shunt ground pad.",
}
P1_DISCONNECT = {
    "extra_fets": [],
    "fet_val": "60V NFET",
    "ovp_top": "158K 1%",
    "ovp_bot": "20K 1%",
    "ref_tl431": False,
    "note": "OUTPUT DISCONNECT: back-to-back NFETs (blocks battery back-feed when off),\\n"
            "LTC7004 charge-pump gate driver. INP = OUT_REQ AND NOT(EN_KILL) AND NOT(OVP).\\n"
            "OVP: VOUT_INT/8.9 vs 2.5V ref -> trips at 22.25V, independent of firmware.",
}
P1_AUX_RAILS = {
    "vin_net": "VBUS_F",
    "en_pgd": False,
    "note": "AUX RAILS: VBUS 12-30V -> LMR36015 (60V, 400kHz, adj) -> 5V0 -> NCP1117 -> 3V3.\\n"
            "FB divider 100K/24.9K -> 5.016V (VREF=1.0V). NC pin ties to SW per datasheet.\\n"
            "Layout: CIN loop tight; BOOT cap adjacent; VCC LDO cap 1uF, no external loads.",
}
P1_MCU_CAN = {
    "vbus_net": "VBUS_F",
    "pb4": "nc",
    "note": "MCU: STM32G431CBT6. SPI1->DAC, I2C1->INA228, FDCAN1->TCAN1042 (VCC 5V bus\\n"
            "drive, VIO 3V3 logic). 8MHz crystal for CAN clock accuracy. OUT_REQ on PB14\\n"
            "(PB4 NJTRST reset pull-up would close the disconnect at boot). Slot straps\\n"
            "PB11-13 use internal pull-ups; backplane grounds them per slot.",
}

BUILDERS = {
    "control-core": _shared("control-core", sc.build_control_core, P1_CONTROL_CORE),
    "aux-rails": _shared("aux-rails", sc.build_aux_rails, P1_AUX_RAILS),
    "sensing": _shared("sensing", sc.build_sensing, P1_SENSING),
    "disconnect": _shared("disconnect", sc.build_disconnect, P1_DISCONNECT),
    "power-stage": build_power_stage,
    "mcu-can": _shared("mcu-can", sc.build_mcu_can, P1_MCU_CAN),
    "io": build_io,
}


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
    for name, _, _ in SHEETS:
        builder = BUILDERS.get(name)
        sheet = builder() if builder else build_stub(name)
        open(os.path.join(OUT, f"{name}.kicad_sch"), "w").write(sheet.emit())
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
    "DAC_REFIO": {"U1.10", "C4.1"},
    "DAC_NSYNC": {"U1.7", "U10.12"},
    "DAC_SDI":   {"U1.8", "U10.15"},
    "DAC_SCLK":  {"U1.6", "U10.13"},
    # -- cross-sheet regulation nets
    "FB":        {"R5.2", "R8.2", "R1.2", "R2.1", "U3.5", "R24.1", "C25.1", "C26.2"},
    "V_MEAS":    {"U2.3", "R32.2", "R33.1", "C32.1", "U10.8"},
    "I_MEAS":    {"U2.5", "R31.2", "C31.1", "U10.9"},
    "~VOUT_INT": {"R1.1", "L1.2", "C22.1", "C78.1", "C23.1", "C79.1", "C80.1",
                  "C81.1", "R27.1", "R30.1", "U4.8",
                  "U5.10", "R45.1", "R25.1"},
    "VOUT_SW":   {"R30.2", "U4.1", "U5.9", "Q3.2"},
    "~VOUT":     {"Q4.2", "U5.8", "R32.1", "J4.1"},
    # -- power-stage
    "PS_EN":     {"R20.2", "R21.1", "U3.1", "Q5.3"},
    "KILL_HW":   {"Q6.3", "R22.2", "D4.1"},
    "EN_KILL":   {"D4.3", "D3.3", "R23.1", "Q5.1", "Q7.1"},
    "PS_OFF":    {"D3.1", "U10.40"},
    "HW_EN":     {"Q6.1", "R19.1", "J5.3", "U10.43"},
    "PS_RT":     {"U3.2", "R26.1"},
    "PS_SS":     {"U3.3", "C18.1"},
    "PS_FPWM":   {"U3.8", "R16.1", "U10.29"},
    "PS_PGOOD":  {"U3.10", "R18.2", "U10.39"},
    "PS_VCC":    {"U3.14", "C29.1"},
    "PS_VIN":    {"R29.2", "U3.20", "C28.1"},
    "COMP_Z":    {"R24.2", "C24.1"},
    "PS_COMP":   {"C24.2", "C25.2", "U3.4"},
    "COMP_FF":   {"R25.2", "C26.1"},
    "~SW":       {"U3.19", "Q1.3", "Q2.2", "L1.1", "C27.2", "R28.2", "R17.1"},
    "HO_G":      {"U3.18", "Q1.1"},
    "LO_G":      {"U3.13", "Q2.1"},
    "PS_BST":    {"U3.17", "C27.1"},
    "PS_ILIM":   {"U3.11", "R28.1", "C19.1"},
    "SNUB":      {"R17.2", "C17.1"},
    # -- sensing
    "INA240_OUT": {"U4.5", "R31.1"},
    "I2C_SCL":   {"U5.5", "R62.2", "U10.31"},
    "I2C_SDA":   {"U5.4", "R63.2", "U10.30"},
    "INA_ALERT": {"U5.3", "U10.44"},
    # -- disconnect
    "DISC_GATE": {"Q3.1", "Q4.1", "U6.6", "U6.7"},
    "DISC_SRC":  {"Q3.3", "Q4.3", "U6.8", "C41.2"},
    "LTC_BST":   {"U6.9", "C41.1"},
    "DISC_INP":  {"R43.2", "U6.4", "R44.1", "Q7.3", "Q9.3"},
    "OUT_REQ":   {"R43.1", "U10.28"},
    "OVP_DIV":   {"R45.2", "R46.1", "C44.1", "U7.3"},
    "REF_2V5":   {"R47.2", "R48.1", "U7.4"},
    "OVP_TRIP":  {"U7.1", "Q9.1"},
    # -- aux rails
    "SW_AUX":    {"U8.12", "L2.1", "C52.2"},
    "AUX_BOOT":  {"U8.4", "C52.1"},
    "AUX_VCC":   {"U8.5", "C53.1"},
    "AUX_FB":    {"U8.7", "R50.2", "R51.1"},
    "AUX_PG":    {"U8.8", "R52.2", "U10.42"},
    # -- mcu-can
    "VBUS_SNS":  {"R60.2", "R61.1", "C62.1", "U10.14"},
    "NTC_FET":   {"R67.2", "RT1.1", "U10.16"},
    "NTC_IND":   {"R68.2", "RT2.1", "U10.17"},
    "SLOT_ID0":  {"J5.4", "U10.25"},
    "SLOT_ID1":  {"J5.5", "U10.26"},
    "SLOT_ID2":  {"J5.6", "U10.27"},
    "UART_TX":   {"U10.10", "J3.2"},
    "UART_RX":   {"U10.11", "J3.3"},
    "SWDIO":     {"U10.37", "J2.2"},
    "SWCLK":     {"U10.38", "J2.3"},
    "NRST":      {"U10.7", "J2.4", "C68.1"},
    "OSC_IN":    {"U10.5", "Y1.1", "C66.1"},
    "OSC_OUT":   {"U10.6", "Y1.3", "C67.1"},
    "LED_A":     {"D7.2", "R66.1"},
    "LED_SINK":  {"U10.18", "D7.1"},
    "BOOT0":     {"U10.45", "R65.1"},
    "CAN_TX":    {"U10.34", "U11.1"},
    "CAN_RX":    {"U10.33", "U11.4"},
    "CAN_STB":   {"U11.8", "U10.32", "R64.1"},
    "CAN_H":     {"U11.7", "J5.1"},
    "CAN_L":     {"U11.6", "J5.2"},
    # -- io
    "VBUS":      {"J1.1", "F1.1"},
    "FAN_PWM":   {"U10.22", "Q8.1"},
    "FAN_NEG":   {"J6.2", "Q8.3", "D6.2"},
    "~VBUS_F":   {"F1.2", "D5.1", "Q1.2", "C20.1", "C75.1", "C76.1", "C77.1",
                  "C21.1", "R29.1", "R20.1",
                  "U8.2", "U8.10", "U8.9", "C50.1", "C51.1", "R60.1"},
    # -- power rails (superset: must contain at least these)
    "~3V3":      {"U1.1", "C3.1", "U9.2", "C57.1", "R18.1", "R47.1", "R52.1",
                  "R62.1", "R63.1", "R66.2", "R67.1", "R68.1", "U10.1", "U10.20",
                  "U10.21", "U10.24", "U10.36", "U10.48", "U11.5", "C70.1", "J2.1"},
    "~5V0":      {"U2.8", "C5.1", "L2.2", "C54.1", "C55.1", "U9.3", "C56.1",
                  "R22.1", "R50.1", "U6.1", "U6.2", "C42.1", "U7.5", "C43.1",
                  "U11.3", "C69.1", "J6.1", "D6.1", "U4.6", "C33.1"},
    "~AGND":     {"U1.3", "U1.4", "U1.5", "C3.2", "C4.2", "C5.2", "U2.4", "R2.2",
                  "U4.2", "U4.3", "U4.4", "U4.7", "C31.2", "C32.2", "C33.2",
                  "C34.2", "R33.2", "U5.1", "U5.2", "U5.7", "R46.2", "R48.2",
                  "C44.2", "R44.2", "Q7.2", "Q9.2", "R23.2", "R16.2", "R19.2",
                  "R21.2", "R26.2", "C18.2", "U3.6", "U3.15", "U3.21", "Q5.2",
                  "Q6.2", "R61.2", "C62.2", "RT1.2", "RT2.2", "C66.2", "C67.2",
                  "C68.2", "R64.2", "R65.2", "Y1.2", "Y1.4", "U10.19", "U10.23", "U10.35",
                  "U10.47", "U11.2", "C69.2", "C70.2", "J2.5", "J3.1", "NT1.1",
                  "U6.3", "U6.5", "U6.11", "U7.2"},
    "~PGND":     {"U3.12", "Q2.3", "C20.2", "C21.2", "C22.2", "C23.2", "C75.2",
                  "C76.2", "C77.2", "C78.2", "C79.2", "C80.2", "C81.2", "R27.2",
                  "C17.2", "C19.2", "C28.2", "C29.2", "U8.1", "U8.6", "U8.11",
                  "C50.2", "C51.2", "C53.2", "C54.2", "C55.2", "U9.1", "C56.2",
                  "C57.2", "R51.2", "D5.2", "J1.2", "J4.2", "J5.7", "J5.8",
                  "Q8.2", "NT1.2"},
}

if __name__ == "__main__":
    main()
