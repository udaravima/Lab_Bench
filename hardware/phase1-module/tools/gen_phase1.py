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
    u1 = sh.add(kg.Placed(DAC, "U1", "DAC80502DRXT", 50.8, 101.6,
                          footprint="Package_SON:WSON-10-1EP_2.5x2.5mm_P0.5mm"))
    gl("V_REF", u1, 2, shape="output")                      # VOUTA
    gl("I_REF", u1, 9, shape="output")                      # VOUTB
    sh.power("AGND", *u1.pin_pos(5), ground=True)           # SPI2C low = SPI mode (ds 8.5.1)
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
    c_dac = cap("C3", "100n", 40.64, 127.0)
    sh.power("3V3", *c_dac.pin_pos(1))
    sh.power("AGND", *c_dac.pin_pos(2), ground=True)

    # ---- CV error amplifier (U2A): Type-II integrator + diode-OR row ----
    u2a = sh.add(kg.Placed(OPA, "U2", "OPA2333", 137.16, 76.2, unit=1,
                           footprint="Package_SO:VSSOP-8_3x3mm_P0.65mm"))
    gl("V_MEAS", u2a, 3, shape="input")                     # +in
    r_av = res("R3", "10K 0.1%", 96.52, u2a.pin_pos(2)[1], rot=90)
    gl("V_REF", r_av, 1, shape="input")
    sh.wire(r_av.pin_pos(2), u2a.pin_pos(2))                # -in run
    sh.label("EAV_INV", (105.41, u2a.pin_pos(2)[1]), rot=90)
    c_fv = cap("C1", "10n", 106.68, 58.42, rot=90)          # Type-II: integrator
    r_zv = res("R4", "33K", 132.08, 58.42, rot=90)          # Type-II: zero
    ll("EAV_INV", c_fv, 1)
    sh.wire(c_fv.pin_pos(2), r_zv.pin_pos(1))
    sh.label("EAV_FB", (119.38, 58.42), rot=90)
    ll("EA_V_OUT", r_zv, 2)
    d_v = sh.add(kg.Placed(DSCH, "D1", "BAT54W", 160.02, 76.2, rot=180,
                           footprint="Package_TO_SOT_SMD:SOT-323_SC-70"))
    sh.wire(u2a.pin_pos(1), d_v.pin_pos(1))                 # out -> anode
    sh.label("EA_V_OUT", (147.32, 76.2), rot=90)
    sh.no_connect(d_v.pin_pos(2))                           # pin 2 = NC on SC-70
    r_iv = res("R5", "3.9K", 182.88, 76.2, rot=90)
    sh.wire(d_v.pin_pos(3), r_iv.pin_pos(1))                # cathode -> R_inj
    sh.label("EAV_INJ", (168.91, 76.2), rot=90)
    gl("FB", r_iv, 2, shape="output")

    # ---- CC error amplifier (U2B): mirror of the CV loop ----
    u2b = sh.add(kg.Placed(OPA, "U2", "OPA2333", 137.16, 127.0, unit=2,
                           footprint="Package_SO:VSSOP-8_3x3mm_P0.65mm"))
    gl("I_MEAS", u2b, 5, shape="input")                     # +in
    r_ai = res("R6", "10K 0.1%", 96.52, u2b.pin_pos(6)[1], rot=90)
    gl("I_REF", r_ai, 1, shape="input")
    sh.wire(r_ai.pin_pos(2), u2b.pin_pos(6))                # -in run
    sh.label("EAI_INV", (105.41, u2b.pin_pos(6)[1]), rot=90)
    c_fi = cap("C2", "22n", 106.68, 109.22, rot=90)
    r_zi = res("R7", "15K", 132.08, 109.22, rot=90)
    ll("EAI_INV", c_fi, 1)
    sh.wire(c_fi.pin_pos(2), r_zi.pin_pos(1))
    sh.label("EAI_FB", (119.38, 109.22), rot=90)
    ll("EA_I_OUT", r_zi, 2)
    d_i = sh.add(kg.Placed(DSCH, "D2", "BAT54W", 160.02, 127.0, rot=180,
                           footprint="Package_TO_SOT_SMD:SOT-323_SC-70"))
    sh.wire(u2b.pin_pos(7), d_i.pin_pos(1))                 # out -> anode
    sh.label("EA_I_OUT", (147.32, 127.0), rot=90)
    sh.no_connect(d_i.pin_pos(2))
    r_ii = res("R8", "3.9K", 182.88, 127.0, rot=90)
    sh.wire(d_i.pin_pos(3), r_ii.pin_pos(1))                # cathode -> R_inj
    sh.label("EAI_INJ", (168.91, 127.0), rot=90)
    gl("FB", r_ii, 2, shape="output")

    # ---- op-amp power unit (U2C) + decoupling ----
    u2c = sh.add(kg.Placed(OPA, "U2", "OPA2333", 50.8, 154.94, unit=3,
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
        f = sh.pwr_flag(33.02 + 25.4 * i, 172.72)
        sh.power(net, *f.pin_pos(1), ground=(net == "AGND"))

    sh.text("CONTROL CORE - dual error amps + diode-OR minimum selector into LM5145 FB node.\\n"
            "Whichever amp demands the LOWER output wins -> automatic CV/CC crossover.\\n"
            "Accuracy is owned by the 0.1% dividers + DAC + amp offset (see docs/06 s.4).", 33.02, 40.64)
    sh.text("DAC80502DRXT (WSON-10): SPI2C->AGND = SPI mode; RSTSEL->AGND = zero-code POR\\n"
            "(both verified vs datasheet). DAC runs on 3V3 = STM32 IO rail (IOVDD<=VDD rule).\\n"
            "EAs: OPA2333 (RRIO; OPA2189 rejected - input CM stops 2.5V below V+).",
            33.02, 190.5)
    return sh


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


def build_aux_rails():
    sh, res, cap, gl, ll = _sheet("aux-rails")
    U8 = kg.get_symbol("labbench", "LMR36015AQRNXRQ1")
    U9 = kg.get_symbol("Regulator_Linear", "NCP1117-3.3_SOT223")
    L = kg.get_symbol("Device", "L")

    u8 = sh.add(kg.Placed(U8, "U8", "LMR36015AQRNXRQ1", 76.2, 78.74,
                          footprint="labbench:LMR36015_RNX_VQFN-HR-12"))
    for p in ("2", "10", "9"):                      # VIN x2 + EN tied to VIN (ds: allowed)
        gl("VBUS_F", u8, p, shape="input")
    for p in ("1", "11", "6"):                      # PGND x2 + AGND (ds: tie to system gnd)
        sh.power("PGND", *u8.pin_pos(p), ground=True)
    c50 = cap("C50", "4.7u/50V", 38.1, 83.82, fp=C_BULK)
    c51 = cap("C51", "4.7u/50V", 48.26, 83.82, fp=C_BULK)
    for c in (c50, c51):
        gl("VBUS_F", c, 1, shape="input")
        sh.power("PGND", *c.pin_pos(2), ground=True)
    ll("SW_AUX", u8, 12)
    sh.no_connect(u8.pin_pos(3))                    # NC-type pin; ds: tie to SW in copper
    c52 = cap("C52", "100n", 99.06, 63.5, rot=90)
    ll("AUX_BOOT", c52, 1)
    ll("SW_AUX", c52, 2)
    ll("AUX_BOOT", u8, 4)
    c53 = cap("C53", "1u", 55.88, 99.06)
    ll("AUX_VCC", u8, 5)
    ll("AUX_VCC", c53, 1)
    sh.power("PGND", *c53.pin_pos(2), ground=True)
    l2 = sh.add(kg.Placed(L, "L2", "33u/1.2A", 113.03, 91.44, rot=90,
                          footprint="Inductor_SMD:L_1210_3225Metric"))
    ll("SW_AUX", l2, 1)
    sh.power("5V0", *l2.pin_pos(2))
    r50 = res("R50", "100K 1%", 127.0, 88.9)
    r51 = res("R51", "24.9K 1%", 127.0, 104.14)
    sh.power("5V0", *r50.pin_pos(1))
    ll("AUX_FB", r50, 2)
    ll("AUX_FB", r51, 1)
    ll("AUX_FB", u8, 7)                             # VREF = 1.0V -> 5.016V out
    sh.power("PGND", *r51.pin_pos(2), ground=True)
    for i, val in enumerate(("22u/16V", "22u/16V")):
        c = cap(f"C5{4+i}", val, 141.0 + 10.16 * i, 88.9, fp=C_BULK)
        sh.power("5V0", *c.pin_pos(1))
        sh.power("PGND", *c.pin_pos(2), ground=True)
    r52 = res("R52", "100K", 96.52, 99.06)
    gl("AUX_PG", u8, 8, shape="output")
    gl("AUX_PG", r52, 2)
    sh.power("3V3", *r52.pin_pos(1))

    u9 = sh.add(kg.Placed(U9, "U9", "NCP1117-3.3", 177.8, 78.74,
                          footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2"))
    sh.power("5V0", *u9.pin_pos(3))
    sh.power("3V3", *u9.pin_pos(2))
    sh.power("PGND", *u9.pin_pos(1), ground=True)
    c56 = cap("C56", "10u/16V", 163.83, 88.9, fp=C_BULK)
    sh.power("5V0", *c56.pin_pos(1))
    sh.power("PGND", *c56.pin_pos(2), ground=True)
    c57 = cap("C57", "22u/10V", 194.31, 88.9, fp=C_BULK)
    sh.power("3V3", *c57.pin_pos(1))
    sh.power("PGND", *c57.pin_pos(2), ground=True)

    sh.text("AUX RAILS: VBUS 12-30V -> LMR36015 (60V, 400kHz, adj) -> 5V0 -> NCP1117 -> 3V3.\\n"
            "FB divider 100K/24.9K -> 5.016V (VREF=1.0V). NC pin ties to SW per datasheet.\\n"
            "Layout: CIN loop tight; BOOT cap adjacent; VCC LDO cap 1uF, no external loads.", 33.02, 40.64)
    return sh


def build_sensing():
    sh, res, cap, gl, ll = _sheet("sensing")
    INA240 = kg.get_symbol("Amplifier_Current", "INA240A3D")
    INA228 = kg.get_symbol("labbench", "INA228AIDGSR")
    NT = kg.get_symbol("Device", "NetTie_2")

    r30 = res("R30", "2m/1W Kelvin", 101.6, 55.88, rot=90)
    r30.footprint = "Resistor_SMD:R_2512_6332Metric"
    gl("VOUT_INT", r30, 1, shape="input")
    gl("VOUT_SW", r30, 2, shape="output")

    u4 = sh.add(kg.Placed(INA240, "U4", "INA240A3", 76.2, 101.6,
                          footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"))
    gl("VOUT_INT", u4, 8, shape="input")            # IN+ Kelvin to shunt
    gl("VOUT_SW", u4, 1, shape="input")             # IN-
    sh.power("5V0", *u4.pin_pos(6))
    for p in ("2", "4", "3", "7"):                  # GND x2 + REF1/REF2 -> unidirectional
        sh.power("AGND", *u4.pin_pos(p), ground=True)
    r31 = res("R31", "100", 104.14, 96.52, rot=90)
    ll("INA240_OUT", u4, 5)
    ll("INA240_OUT", r31, 1)
    gl("I_MEAS", r31, 2, shape="output")
    c31 = cap("C31", "1n", 118.11, 106.68)
    gl("I_MEAS", c31, 1)
    sh.power("AGND", *c31.pin_pos(2), ground=True)
    c33 = cap("C33", "100n", 55.88, 106.68)
    sh.power("5V0", *c33.pin_pos(1))
    sh.power("AGND", *c33.pin_pos(2), ground=True)

    u5 = sh.add(kg.Placed(INA228, "U5", "INA228", 76.2, 152.4,
                          footprint="Package_SO:VSSOP-10_3x3mm_P0.5mm"))
    gl("VOUT_INT", u5, 10, shape="input")           # IN+ same Kelvin pads
    gl("VOUT_SW", u5, 9, shape="input")             # IN-
    gl("VOUT", u5, 8, shape="input")                # VBUS: true terminal voltage
    sh.power("3V3", *u5.pin_pos(6))
    sh.power("AGND", *u5.pin_pos(7), ground=True)
    sh.power("AGND", *u5.pin_pos(1), ground=True)   # A1 -> addr 0x40
    sh.power("AGND", *u5.pin_pos(2), ground=True)   # A0
    gl("I2C_SDA", u5, 4)
    gl("I2C_SCL", u5, 5)
    gl("INA_ALERT", u5, 3, shape="output")
    c34 = cap("C34", "100n", 55.88, 157.48)
    sh.power("3V3", *c34.pin_pos(1))
    sh.power("AGND", *c34.pin_pos(2), ground=True)

    r32 = res("R32", "69.8K 0.1%", 165.1, 88.9)
    r33 = res("R33", "10.0K 0.1%", 165.1, 104.14)
    gl("VOUT", r32, 1, shape="input")
    gl("V_MEAS", r32, 2, shape="output")
    gl("V_MEAS", r33, 1)
    sh.power("AGND", *r33.pin_pos(2), ground=True)
    c32 = cap("C32", "1n", 180.34, 106.68)
    gl("V_MEAS", c32, 1)
    sh.power("AGND", *c32.pin_pos(2), ground=True)

    nt = sh.add(kg.Placed(NT, "NT1", "AGND-PGND tie", 165.1, 152.4, rot=90))
    sh.power("AGND", *nt.pin_pos(1), ground=True)
    sh.power("PGND", *nt.pin_pos(2), ground=True)

    sh.text("SENSING: 2m shunt (Kelvin) between VOUT_INT and disconnect. INA240A3 (x100,\\n"
            "0.2V/A, 1.6V @ 8A) feeds the CC loop; INA228 feeds telemetry. V divider /8 from\\n"
            "VOUT terminals. NT1 = the single AGND-PGND tie point: at the shunt ground pad.", 33.02, 40.64)
    return sh


def build_disconnect():
    sh, res, cap, gl, ll = _sheet("disconnect")
    LTC = kg.get_symbol("labbench", "LTC7004EMSE#TRPBF")
    CMP = kg.get_symbol("labbench", "TLV7011DBVR")
    QN = kg.get_symbol("Device", "Q_NMOS_GDS")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")

    q3 = sh.add(kg.Placed(QN, "Q3", "60V NFET", 96.52, 63.5, footprint="labbench:PowerFET_5x6"))
    q4 = sh.add(kg.Placed(QN, "Q4", "60V NFET", 134.62, 63.5, footprint="labbench:PowerFET_5x6"))
    gl("VOUT_SW", q3, 2, shape="input")             # D
    ll("DISC_SRC", q3, 3)                           # common sources
    ll("DISC_SRC", q4, 3)
    gl("VOUT", q4, 2, shape="output")               # D
    ll("DISC_GATE", q3, 1)
    ll("DISC_GATE", q4, 1)

    u6 = sh.add(kg.Placed(LTC, "U6", "LTC7004", 76.2, 127.0,
                          footprint="Package_SO:MSOP-10-1EP_3x3mm_P0.5mm_EP1.68x1.88mm_ThermalVias"))
    sh.power("5V0", *u6.pin_pos(1))                 # VCC
    sh.power("5V0", *u6.pin_pos(2))                 # VCCUV tied high
    sh.power("AGND", *u6.pin_pos(3), ground=True)
    sh.power("AGND", *u6.pin_pos(5), ground=True)   # OVLO unused
    sh.power("AGND", *u6.pin_pos(11), ground=True)  # EP
    sh.no_connect(u6.pin_pos(10))
    ll("DISC_GATE", u6, 6)                          # TGDN
    ll("DISC_GATE", u6, 7)                          # TGUP
    ll("DISC_SRC", u6, 8)                           # TS
    c41 = cap("C41", "100n", 113.03, 121.92, rot=90)
    ll("LTC_BST", u6, 9)
    ll("LTC_BST", c41, 1)
    ll("DISC_SRC", c41, 2)
    c42 = cap("C42", "1u", 55.88, 132.08)
    sh.power("5V0", *c42.pin_pos(1))
    sh.power("AGND", *c42.pin_pos(2), ground=True)

    # INP wired-AND: MCU requests, EN_KILL and OVP can veto
    r43 = res("R43", "10K", 41.91, 111.76, rot=90)
    gl("OUT_REQ", r43, 1, shape="input")
    ll("DISC_INP", r43, 2)
    ll("DISC_INP", u6, 4)
    r44 = res("R44", "47K", 55.88, 111.76)
    ll("DISC_INP", r44, 1)
    sh.power("AGND", *r44.pin_pos(2), ground=True)
    q7 = sh.add(kg.Placed(Q2N, "Q7", "2N7002", 33.02, 137.16, footprint=SOT23))
    gl("EN_KILL", q7, 1, shape="input")
    sh.power("AGND", *q7.pin_pos(2), ground=True)
    ll("DISC_INP", q7, 3)

    # OVP comparator: trips high above 22.25V -> Q9 pulls INP low
    u7 = sh.add(kg.Placed(CMP, "U7", "TLV7011", 165.1, 127.0,
                          footprint="Package_TO_SOT_SMD:SOT-23-5"))
    r45 = res("R45", "158K 1%", 146.05, 96.52)
    r46 = res("R46", "20K 1%", 146.05, 111.76)
    gl("VOUT_INT", r45, 1, shape="input")
    ll("OVP_DIV", r45, 2)
    ll("OVP_DIV", r46, 1)
    sh.power("AGND", *r46.pin_pos(2), ground=True)
    ll("OVP_DIV", u7, 3)                            # IN+
    c44 = cap("C44", "1n", 156.21, 111.76)
    ll("OVP_DIV", c44, 1)
    sh.power("AGND", *c44.pin_pos(2), ground=True)
    r47 = res("R47", "10K 1%", 190.5, 96.52)
    r48 = res("R48", "31.6K 1%", 190.5, 111.76)
    sh.power("3V3", *r47.pin_pos(1))
    ll("REF_2V5", r47, 2)
    ll("REF_2V5", r48, 1)
    sh.power("AGND", *r48.pin_pos(2), ground=True)
    ll("REF_2V5", u7, 4)                            # IN-
    sh.power("5V0", *u7.pin_pos(5))
    sh.power("AGND", *u7.pin_pos(2), ground=True)
    c43 = cap("C43", "100n", 177.8, 132.08)
    sh.power("5V0", *c43.pin_pos(1))
    sh.power("AGND", *c43.pin_pos(2), ground=True)
    q9 = sh.add(kg.Placed(Q2N, "Q9", "2N7002", 190.5, 142.24, footprint=SOT23))
    ll("OVP_TRIP", u7, 1)
    ll("OVP_TRIP", q9, 1)
    sh.power("AGND", *q9.pin_pos(2), ground=True)
    ll("DISC_INP", q9, 3)

    sh.text("OUTPUT DISCONNECT: back-to-back NFETs (blocks battery back-feed when off),\\n"
            "LTC7004 charge-pump gate driver. INP = OUT_REQ AND NOT(EN_KILL) AND NOT(OVP).\\n"
            "OVP: VOUT_INT/8.9 vs 2.5V ref -> trips at 22.25V, independent of firmware.", 33.02, 40.64)
    return sh


def build_power_stage():
    sh, res, cap, gl, ll = _sheet("power-stage")
    LM = kg.get_symbol("labbench", "LM5145RGYR")
    QN = kg.get_symbol("Device", "Q_NMOS_GDS")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")
    DS = kg.get_symbol("Diode", "BAT54W")
    L = kg.get_symbol("Device", "L")

    u3 = sh.add(kg.Placed(LM, "U3", "LM5145RGYR", 76.2, 106.68,
                          footprint="labbench:LM5145_RGY_VQFN-20"))
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
    q1 = sh.add(kg.Placed(QN, "Q1", "CSD18563Q5A", 154.94, 78.74, footprint="labbench:PowerFET_5x6"))
    q2 = sh.add(kg.Placed(QN, "Q2", "CSD18563Q5A", 154.94, 116.84, footprint="labbench:PowerFET_5x6"))
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

    l1 = sh.add(kg.Placed(L, "L1", "10u/12A", 180.34, 96.52, rot=90,
                          footprint="labbench:L_10uH_flatwire_13x13"))
    gl("SW", l1, 1)
    gl("VOUT_INT", l1, 2, shape="output")
    # input/output banks + preload + snubber (DNP)
    c20 = cap("C20", "4x 22u/50V X7R", 154.94, 146.05, fp=C_BULK)
    c21 = cap("C21", "220u/50V bulk", 167.64, 146.05, fp=C_BULK)
    for c in (c20, c21):
        gl("VBUS_F", c, 1, shape="input")
        sh.power("PGND", *c.pin_pos(2), ground=True)
    c22 = cap("C22", "2x 220u poly", 194.31, 146.05, fp=C_BULK)
    c23 = cap("C23", "4x 22u/25V", 207.01, 146.05, fp=C_BULK)
    r27 = res("R27", "2.2K 1W preload", 219.71, 146.05)
    for c in (c22, c23, r27):
        gl("VOUT_INT", c, 1, shape="input")
        sh.power("PGND", *c.pin_pos(2), ground=True)
    r17 = res("R17", "DNP snub", 232.41, 146.05)
    c17 = cap("C17", "DNP", 232.41, 160.02)
    gl("SW", r17, 1)
    ll("SNUB", r17, 2)
    ll("SNUB", c17, 1)
    sh.power("PGND", *c17.pin_pos(2), ground=True)

    sh.text("POWER STAGE: LM5145 sync buck, 350kHz (RT 28.7K), valley ILIM 11A (R28 365R\\n"
            "to SW, RDS(on) sensing). SYNCIN: MCU PS_FPWM (low=DEM battery-safe default).\\n"
            "EN chain: UVLO 10.5V divider; Q5 kills EN when EN_KILL = NOT(HW_EN) OR PS_OFF.\\n"
            "Type-III comp values are FRA starting points (docs/06 s.6).", 15.24, 33.02)
    return sh


def build_mcu_can():
    sh, res, cap, gl, ll = _sheet("mcu-can")
    MCU = kg.get_symbol("MCU_ST_STM32G4", "STM32G431CBTx")
    CAN = kg.get_symbol("labbench", "TCAN1042HGVDR")
    XTAL = kg.get_symbol("Device", "Crystal")
    LED = kg.get_symbol("Device", "LED")
    NTC = kg.get_symbol("Device", "Thermistor_NTC")
    C5 = kg.get_symbol("Connector_Generic", "Conn_01x05")
    C3 = kg.get_symbol("Connector_Generic", "Conn_01x03")

    u10 = sh.add(kg.Placed(MCU, "U10", "STM32G431CBT6", 88.9, 116.84,
                           footprint="Package_QFP:LQFP-48_7x7mm_P0.5mm"))
    # power
    for p in ("1", "20", "21", "24", "36", "48"):   # VBAT, VREF+, VDDA, VDD x3
        sh.power("3V3", *u10.pin_pos(p))
    for p in ("19", "23", "35", "47"):              # VSSA, VSS x3
        sh.power("AGND", *u10.pin_pos(p), ground=True)
    for i, x in enumerate((15.24, 27.94, 40.64, 53.34)):
        c = cap(f"C7{1 + i}", "100n", x, 190.5)
        sh.power("3V3", *c.pin_pos(1))
        sh.power("AGND", *c.pin_pos(2), ground=True)
    c64 = cap("C64", "4.7u", 66.04, 190.5)
    c65 = cap("C65", "1u VDDA", 78.74, 190.5)
    for c in (c64, c65):
        sh.power("3V3", *c.pin_pos(1))
        sh.power("AGND", *c.pin_pos(2), ground=True)
    # analog + housekeeping ins
    gl("V_MEAS", u10, 8, shape="input")             # PA0
    gl("I_MEAS", u10, 9, shape="input")             # PA1
    gl("VBUS_SNS", u10, 14, shape="input")          # PA6
    gl("NTC_FET", u10, 16, shape="input")           # PB0
    gl("NTC_IND", u10, 17, shape="input")           # PB1
    r60 = res("R60", "200K 1%", 190.5, 55.88)
    r61 = res("R61", "10K 1%", 190.5, 71.12)
    gl("VBUS_F", r60, 1, shape="input")
    gl("VBUS_SNS", r60, 2)
    gl("VBUS_SNS", r61, 1)
    sh.power("AGND", *r61.pin_pos(2), ground=True)
    c62 = cap("C62", "100n", 203.2, 73.66)
    gl("VBUS_SNS", c62, 1)
    sh.power("AGND", *c62.pin_pos(2), ground=True)
    for i, (net, x) in enumerate((("NTC_FET", 218.44), ("NTC_IND", 233.68))):
        rp = res(f"R6{7+i}", "10K 1%", x, 55.88)
        rt = sh.add(kg.Placed(NTC, f"RT{1+i}", "10K B3950", x, 71.12,
                              footprint="Resistor_SMD:R_0603_1608Metric"))
        sh.power("3V3", *rp.pin_pos(1))
        sh.label(net, rp.pin_pos(2), rot=rp.label_rot(2))
        sh.label(net, rt.pin_pos(1), rot=rt.label_rot(1))
        sh.power("AGND", *rt.pin_pos(2), ground=True)
    # DAC SPI + control GPIOs
    gl("DAC_NSYNC", u10, 12, shape="output")        # PA4
    gl("DAC_SCLK", u10, 13, shape="output")         # PA5
    gl("DAC_SDI", u10, 15, shape="output")          # PA7
    gl("PS_FPWM", u10, 29, shape="output")          # PB15
    gl("CAN_STB", u10, 32, shape="output")          # PA10
    gl("PS_PGOOD", u10, 39, shape="input")          # PA15
    gl("PS_OFF", u10, 40, shape="output")           # PB3
    gl("AUX_PG", u10, 42, shape="input")            # PB5
    gl("HW_EN", u10, 43, shape="input")             # PB6
    gl("INA_ALERT", u10, 44, shape="input")         # PB7
    gl("OUT_REQ", u10, 28, shape="output")          # PB14 (no reset pull - safe)
    gl("FAN_PWM", u10, 22, shape="output")          # PB10 (TIM2_CH3)
    sh.no_connect(u10.pin_pos(41))                  # PB4 spare (NJTRST pull-up at reset)
    sh.no_connect(u10.pin_pos(2))                   # PC13
    sh.no_connect(u10.pin_pos(3))
    sh.no_connect(u10.pin_pos(4))
    sh.no_connect(u10.pin_pos(46))                  # PB9 spare (PB8 sacrificed to BOOT0)
    # I2C2 on PA8/PA9 - PB8 is the BOOT0 strap on STM32G4, unusable for I2C pullups
    gl("I2C_SDA", u10, 30)                          # PA8  I2C2_SDA
    gl("I2C_SCL", u10, 31)                          # PA9  I2C2_SCL
    r62 = res("R62", "4.7K", 248.92, 55.88)
    r63 = res("R63", "4.7K", 261.62, 55.88)
    sh.power("3V3", *r62.pin_pos(1))
    sh.power("3V3", *r63.pin_pos(1))
    gl("I2C_SCL", r62, 2)
    gl("I2C_SDA", r63, 2)
    # slot straps
    gl("SLOT_ID0", u10, 25, shape="input")          # PB11
    gl("SLOT_ID1", u10, 26, shape="input")          # PB12
    gl("SLOT_ID2", u10, 27, shape="input")          # PB13
    # LED
    d7 = sh.add(kg.Placed(LED, "D7", "STATUS", 218.44, 96.52, rot=90,
                          footprint="LED_SMD:LED_0603_1608Metric"))
    r66 = res("R66", "1K", 233.68, 96.52, rot=90)
    ll("LED_A", d7, 2)
    ll("LED_A", r66, 1)
    sh.power("3V3", *r66.pin_pos(2))
    ll("LED_SINK", d7, 1)
    ll("LED_SINK", u10, 18)                         # PB2 sinks
    # BOOT0 strap (PB8, pin 45) + NRST + crystal
    r65 = res("R65", "10K", 27.94, 55.88)
    ll("BOOT0", r65, 1)
    sh.power("AGND", *r65.pin_pos(2), ground=True)
    ll("BOOT0", u10, 45)                            # PB8-BOOT0 held low: boot from flash
    y1 = sh.add(kg.Placed(XTAL, "Y1", "8MHz", 218.44, 127.0,
                          footprint="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm"))
    gl("OSC_IN", u10, 5, shape="input")             # PF0
    gl("OSC_OUT", u10, 6, shape="output")           # PF1
    gl("OSC_IN", y1, 1)
    gl("OSC_OUT", y1, 2)
    c66 = cap("C66", "10p", 210.82, 137.16)
    c67 = cap("C67", "10p", 226.06, 137.16)
    gl("OSC_IN", c66, 1)
    gl("OSC_OUT", c67, 1)
    sh.power("AGND", *c66.pin_pos(2), ground=True)
    sh.power("AGND", *c67.pin_pos(2), ground=True)
    c68 = cap("C68", "100n", 15.24, 71.12)
    gl("NRST", u10, 7, shape="input")               # PG10
    gl("NRST", c68, 1)
    sh.power("AGND", *c68.pin_pos(2), ground=True)
    # headers
    j2 = sh.add(kg.Placed(C5, "J2", "SWD", 259.08, 127.0,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical"))
    sh.power("3V3", *j2.pin_pos(1))
    gl("SWDIO", j2, 2)
    gl("SWCLK", j2, 3)
    gl("NRST", j2, 4)
    sh.power("AGND", *j2.pin_pos(5), ground=True)
    gl("SWDIO", u10, 37)                            # PA13
    gl("SWCLK", u10, 38)                            # PA14
    j3 = sh.add(kg.Placed(C3, "J3", "UART", 259.08, 154.94,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"))
    sh.power("AGND", *j3.pin_pos(1), ground=True)
    gl("UART_TX", j3, 2)
    gl("UART_RX", j3, 3)
    gl("UART_TX", u10, 10, shape="output")          # PA2
    gl("UART_RX", u10, 11, shape="input")           # PA3
    # CAN
    u11 = sh.add(kg.Placed(CAN, "U11", "TCAN1042HGV", 174.5, 165.1,
                           footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"))
    gl("CAN_TX", u10, 34, shape="output")           # PA12 FDCAN1_TX
    gl("CAN_RX", u10, 33, shape="input")            # PA11 FDCAN1_RX
    gl("CAN_TX", u11, 1, shape="input")             # TXD
    gl("CAN_RX", u11, 4, shape="output")            # RXD
    sh.power("5V0", *u11.pin_pos(3))
    sh.power("3V3", *u11.pin_pos(5))                # VIO
    sh.power("AGND", *u11.pin_pos(2), ground=True)
    gl("CAN_H", u11, 7)
    gl("CAN_L", u11, 6)
    gl("CAN_STB", u11, 8, shape="input")
    r64 = res("R64", "10K", 40.64, 55.88)
    gl("CAN_STB", r64, 1)
    sh.power("AGND", *r64.pin_pos(2), ground=True)
    c69 = cap("C69", "100n", 148.59, 170.18)
    sh.power("5V0", *c69.pin_pos(1))
    sh.power("AGND", *c69.pin_pos(2), ground=True)
    c70 = cap("C70", "100n", 148.59, 182.88)
    sh.power("3V3", *c70.pin_pos(1))
    sh.power("AGND", *c70.pin_pos(2), ground=True)

    sh.text("MCU: STM32G431CBT6. SPI1->DAC, I2C1->INA228, FDCAN1->TCAN1042 (VCC 5V bus\\n"
            "drive, VIO 3V3 logic). 8MHz crystal for CAN clock accuracy. OUT_REQ on PB14\\n"
            "(PB4 NJTRST reset pull-up would close the disconnect at boot). Slot straps\\n"
            "PB11-13 use internal pull-ups; backplane grounds them per slot.", 15.24, 33.02)
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


BUILDERS = {
    "control-core": build_control_core,
    "aux-rails": build_aux_rails,
    "sensing": build_sensing,
    "disconnect": build_disconnect,
    "power-stage": build_power_stage,
    "mcu-can": build_mcu_can,
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
    "~VOUT_INT": {"R1.1", "L1.2", "C22.1", "C23.1", "R27.1", "R30.1", "U4.8",
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
    "OSC_OUT":   {"U10.6", "Y1.2", "C67.1"},
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
    "~VBUS_F":   {"F1.2", "D5.1", "Q1.2", "C20.1", "C21.1", "R29.1", "R20.1",
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
                  "C68.2", "R64.2", "R65.2", "U10.19", "U10.23", "U10.35",
                  "U10.47", "U11.2", "C69.2", "C70.2", "J2.5", "J3.1", "NT1.1",
                  "U6.3", "U6.5", "U6.11", "U7.2"},
    "~PGND":     {"U3.12", "Q2.3", "C20.2", "C21.2", "C22.2", "C23.2", "R27.2",
                  "C17.2", "C19.2", "C28.2", "C29.2", "U8.1", "U8.6", "U8.11",
                  "C50.2", "C51.2", "C53.2", "C54.2", "C55.2", "U9.1", "C56.2",
                  "C57.2", "R51.2", "D5.2", "J1.2", "J4.2", "J5.7", "J5.8",
                  "Q8.2", "NT1.2"},
}

if __name__ == "__main__":
    main()
