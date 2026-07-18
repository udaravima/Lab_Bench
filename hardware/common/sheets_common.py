"""Sheet builders shared by gen_phase1.py and gen_phase2.py.

docs/05 asks for the verified control core to be reused as-is between the
150 W and 600 W modules; these builders are that reuse, extracted verbatim
from the netlist-verified Phase-1 generator. Everything phase-specific is a
parameter (component values, extra parts, sheet notes) — reference
designators and topology are identical in both phases so the sheets stay
diff-able against each other.

Callers create the kicad_gen.Sheet (they own project name + sheet path) and
pass it in. Each builder's `p` dict documents its parameters with the
Phase-1 values as defaults.
"""
import kicad_gen as kg

R_FP = "Resistor_SMD:R_0603_1608Metric"      # 0603: hand-assembled boards
C_FP = "Capacitor_SMD:C_0603_1608Metric"
C_BULK = "Capacitor_SMD:C_1210_3225Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"


def helpers(sh):
    """The res/cap/gl/ll helper quartet used by every sheet builder."""
    def res(ref, val, x, y, rot=0):
        return sh.add(kg.Placed(kg.get_symbol("Device", "R"), ref, val, x, y, rot, footprint=R_FP))

    def cap(ref, val, x, y, rot=0, fp=C_FP):
        return sh.add(kg.Placed(kg.get_symbol("Device", "C"), ref, val, x, y, rot, footprint=fp))

    def gl(net, part, pin, shape="passive"):
        sh.glabel(net, part.pin_pos(pin), rot=part.label_rot(pin), shape=shape)

    def ll(net, part, pin):
        sh.label(net, part.pin_pos(pin), rot=part.label_rot(pin))

    return res, cap, gl, ll


def build_control_core(sh, p):
    """DAC + dual error amps + diode-OR + base divider.

    p: r_top   base-divider top ("25.5K 0.1%" p1 / "46.4K 0.1%" p2)
       r_inj   injection resistors ("3.9K" p1 / "5.6K" p2)
       note    sheet text line for the ceiling math
    """
    res, cap, gl, ll = helpers(sh)
    DAC = kg.get_symbol("Analog_DAC", "DAC80502")
    OPA = kg.get_symbol("Amplifier_Operational", "OPA2333xxDGK")
    DSCH = kg.get_symbol("Diode", "BAT54W")

    # ---- DAC80502: 16-bit dual reference source (V_REF / I_REF) ----
    u1 = sh.add(kg.Placed(DAC, "U1", "DAC80502DRXT", 50.8, 101.6,
                          footprint="labbench:DAC80502_DRX_WSON-10"))
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
                           footprint="Package_SO:VSSOP-8_3.0x3.0mm_P0.65mm"))
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
    r_iv = res("R5", p["r_inj"], 182.88, 76.2, rot=90)
    sh.wire(d_v.pin_pos(3), r_iv.pin_pos(1))                # cathode -> R_inj
    sh.label("EAV_INJ", (168.91, 76.2), rot=90)
    gl("FB", r_iv, 2, shape="output")

    # ---- CC error amplifier (U2B): mirror of the CV loop ----
    u2b = sh.add(kg.Placed(OPA, "U2", "OPA2333", 137.16, 127.0, unit=2,
                           footprint="Package_SO:VSSOP-8_3.0x3.0mm_P0.65mm"))
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
    r_ii = res("R8", p["r_inj"], 182.88, 127.0, rot=90)
    sh.wire(d_i.pin_pos(3), r_ii.pin_pos(1))                # cathode -> R_inj
    sh.label("EAI_INJ", (168.91, 127.0), rot=90)
    gl("FB", r_ii, 2, shape="output")

    # ---- op-amp power unit (U2C) + decoupling ----
    u2c = sh.add(kg.Placed(OPA, "U2", "OPA2333", 50.8, 154.94, unit=3,
                           footprint="Package_SO:VSSOP-8_3.0x3.0mm_P0.65mm"))
    sh.power("5V0", *u2c.pin_pos(8))
    sh.power("AGND", *u2c.pin_pos(4), ground=True)
    c_op = cap("C5", "100n", 71.12, 154.94)
    sh.power("5V0", *c_op.pin_pos(1))
    sh.power("AGND", *c_op.pin_pos(2), ground=True)

    # ---- base divider: fixed hardware output ceiling ----
    r_top = res("R1", p["r_top"], 218.44, 88.9)
    r_bot = res("R2", "1.0K 0.1%", 218.44, 106.68)
    gl("VOUT_INT", r_top, 1, shape="input")
    gl("FB", r_top, 2, shape="output")
    gl("FB", r_bot, 1, shape="output")
    sh.power("AGND", *r_bot.pin_pos(2), ground=True)

    # ---- power flags ----
    for i, net in enumerate(("3V3", "5V0", "AGND")):
        f = sh.pwr_flag(33.02 + 25.4 * i, 172.72)
        sh.power(net, *f.pin_pos(1), ground=(net == "AGND"))

    sh.text(p["note"], 33.02, 40.64)
    sh.text("DAC80502DRXT (WSON-10): SPI2C->AGND = SPI mode; RSTSEL->AGND = zero-code POR\\n"
            "(both verified vs datasheet). DAC runs on 3V3 = STM32 IO rail (IOVDD<=VDD rule).\\n"
            "EAs: OPA2333 (RRIO; OPA2189 rejected - input CM stops 2.5V below V+).",
            33.02, 190.5)
    return sh


def build_sensing(sh, p):
    """Output shunt(s) + INA240 + INA228 + measurement divider + NT1 tie.

    p: shunts   list of (ref, value) 2512 shunts in parallel
                ([("R30","2m/1W Kelvin")] p1 / [("R30","1m0 3W"),("R34","1m0 3W")] p2)
       div_top  measurement divider top ("69.8K 0.1%" p1 / "110K 0.1%" p2)
       droop    None (p1) or dict(r_droop=..) -> draws R35 + TMUX1101 switch (p2)
       note     sheet text
    """
    res, cap, gl, ll = helpers(sh)
    INA240 = kg.get_symbol("Amplifier_Current", "INA240A3D")
    INA228 = kg.get_symbol("labbench", "INA228AIDGSR")
    NT = kg.get_symbol("Device", "NetTie_2")

    for i, (ref, val) in enumerate(p["shunts"]):
        r30 = res(ref, val, 101.6 + 12.7 * i, 55.88, rot=90)
        r30.footprint = "Resistor_SMD:R_2512_6332Metric"
        gl("VOUT_INT", r30, 1, shape="input")
        gl("VOUT_SW", r30, 2, shape="output")

    u4 = sh.add(kg.Placed(INA240, "U4", "INA240A3", 76.2, 101.6,
                          footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"))
    gl("VOUT_INT", u4, 8, shape="input")            # IN+ Kelvin to shunt
    gl("VOUT_SW", u4, 1, shape="input")             # IN-
    sh.power("5V0", *u4.pin_pos(6))
    for pin in ("2", "4", "3", "7"):                # GND x2 + REF1/REF2 -> unidirectional
        sh.power("AGND", *u4.pin_pos(pin), ground=True)
    r31 = res("R31", "1K", 104.14, 96.52, rot=90)
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

    r32 = res("R32", p["div_top"], 165.1, 88.9)
    r33 = res("R33", "10.0K 0.1%", 165.1, 104.14)
    gl("VOUT", r32, 1, shape="input")
    gl("V_MEAS", r32, 2, shape="output")
    gl("V_MEAS", r33, 1)
    sh.power("AGND", *r33.pin_pos(2), ground=True)
    c32 = cap("C32", "1n", 180.34, 106.68)
    gl("V_MEAS", c32, 1)
    sh.power("AGND", *c32.pin_pos(2), ground=True)

    nt = sh.add(kg.Placed(NT, "NT1", "AGND-PGND tie", 165.1, 152.4, rot=90,
                          footprint="NetTie:NetTie-2_SMD_Pad0.5mm"))
    sh.power("AGND", *nt.pin_pos(1), ground=True)
    sh.power("PGND", *nt.pin_pos(2), ground=True)

    if p.get("droop"):
        # ~20 mV/A droop: attenuated I_MEAS summed into the V_MEAS node
        # through an analog switch (docs/08 s.7). Switch open = no droop and
        # no divider loading; closed = droop + a fixed +3.4% gain shift the
        # firmware corrects (x0.9668 on V_ref in droop modes).
        # TS5A3166 DBV = SOT-23-5: 1=NO, 2=COM, 3=GND, 4=IN, 5=V+
        # (ts5a3166.pdf Pin Functions; VIH <= 2.4 V at V+ 5 V so 3.3 V GPIO
        # drives IN). Swapped from TMUX1101 2026-07-18 - not stocked on
        # LCSC; pin POSITIONS are identical so only the symbol changed.
        MUX = kg.get_symbol("Analog_Switch", "TS5A3166DBVR")
        r35 = res("R35", p["droop"]["r_droop"], 203.2, 152.4, rot=90)
        gl("I_MEAS", r35, 1, shape="input")
        ll("DROOP_R", r35, 2)
        u13 = sh.add(kg.Placed(MUX, "U13", "TS5A3166", 226.06, 152.4,
                               footprint="Package_TO_SOT_SMD:SOT-23-5"))
        ll("DROOP_R", u13, 1)                       # NO
        gl("V_MEAS", u13, 2, shape="output")        # COM
        sh.power("5V0", *u13.pin_pos(5))            # V+
        sh.power("AGND", *u13.pin_pos(3), ground=True)
        gl("DROOP_EN", u13, 4, shape="input")       # IN
        r38 = res("R38", "100K", 226.06, 172.72, rot=90)
        gl("DROOP_EN", r38, 1)                      # default open (SEL low)
        sh.power("AGND", *r38.pin_pos(2), ground=True)
        c39 = cap("C39", "100n", 245.11, 152.4)
        sh.power("5V0", *c39.pin_pos(1))
        sh.power("AGND", *c39.pin_pos(2), ground=True)

    sh.text(p["note"], 33.02, 40.64)
    return sh


def build_disconnect(sh, p):
    """Back-to-back NFET output disconnect + LTC7004 + hardware OVP.

    p: extra_fets  [] (p1) or [("Q10", pos_pair), ("Q11", ...)] handled as
                   refs list for parallel devices ( [] p1 / ["Q10","Q11"] p2 )
       fet_val     FET value string
       ovp_top     OVP divider top ("158K 1%" p1 / "215K 0.1%" p2)
       ovp_bot     OVP divider bottom ("20K 1%" p1 / "20K 0.1%" p2)
       ref_tl431   False (p1: 3V3 divider ref) / True (p2: TL431 2.495V ref)
       note        sheet text
    """
    res, cap, gl, ll = helpers(sh)
    LTC = kg.get_symbol("labbench", "LTC7004EMSE#TRPBF")
    CMP = kg.get_symbol("labbench", "TLV7011DBVR")
    QN = kg.get_symbol("Device", "Q_NMOS_GDS")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")

    fets = [("Q3", 96.52), ("Q4", 134.62)]
    if p["extra_fets"]:
        fets += [(p["extra_fets"][0], 96.52), (p["extra_fets"][1], 134.62)]
    for i, (ref, x) in enumerate(fets):
        y = 63.5 if i < 2 else 40.64
        q = sh.add(kg.Placed(QN, ref, p["fet_val"], x, y, footprint="labbench:PowerFET_SON5x6_GDS"))
        if x == 96.52:
            gl("VOUT_SW", q, 2, shape="input")      # D (bus side pair)
        else:
            gl("VOUT", q, 2, shape="output")        # D (terminal side pair)
        ll("DISC_SRC", q, 3)                        # common sources
        ll("DISC_GATE", q, 1)

    u6 = sh.add(kg.Placed(LTC, "U6", "LTC7004", 76.2, 127.0,
                          footprint="Package_SO:MSOP-10-1EP_3x3mm_P0.5mm_EP1.68x1.88mm"))
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

    # OVP comparator: trips above the fixed threshold -> Q9 pulls INP low
    # DCK (SC-70-5) since 2026-07-18: same pinout as DBV per tlv7022.pdf
    # ("DBV and DCK Package" share one diagram); SOT-23-5 stock on LCSC is
    # nearly gone while DCKR has depth (hardware/SOURCING.md).
    u7 = sh.add(kg.Placed(CMP, "U7", "TLV7011DCK", 165.1, 127.0,
                          footprint="Package_TO_SOT_SMD:SOT-353_SC-70-5"))
    r45 = res("R45", p["ovp_top"], 146.05, 96.52)
    r46 = res("R46", p["ovp_bot"], 146.05, 111.76)
    gl("VOUT_INT", r45, 1, shape="input")
    ll("OVP_DIV", r45, 2)
    ll("OVP_DIV", r46, 1)
    sh.power("AGND", *r46.pin_pos(2), ground=True)
    ll("OVP_DIV", u7, 3)                            # IN+
    c44 = cap("C44", "1n", 156.21, 111.76)
    ll("OVP_DIV", c44, 1)
    sh.power("AGND", *c44.pin_pos(2), ground=True)
    if p["ref_tl431"]:
        # TL431B: 2.495V +/-0.5% - the 3V3-LDO-derived divider is not
        # accurate enough for the 28.4 < 29.4 < 30V OVP squeeze (docs/08 s.8).
        # TL431 DBZ = SOT-23: 1=CATHODE, 2=REF, 3=ANODE (tl431.pdf Table 5-1;
        # beware: the TL432 DBZ swaps pins 1 and 2!)
        TL = kg.get_symbol("Reference_Voltage", "TL431DBZ")
        r47 = res("R47", "10K 1%", 190.5, 96.52)
        sh.power("5V0", *r47.pin_pos(1))
        ll("REF_2V5", r47, 2)
        tl = sh.add(kg.Placed(TL, "D8", "TL431B 2.495V", 190.5, 111.76,
                              footprint="Package_TO_SOT_SMD:SOT-23"))
        ll("REF_2V5", tl, 1)                        # cathode (self-biased ref)
        ll("REF_2V5", tl, 2)                        # REF tied to cathode
        sh.power("AGND", *tl.pin_pos(3), ground=True)
    else:
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
    q9 = sh.add(kg.Placed(Q2N, "Q9", "2N7002", 205.74, 142.24, footprint=SOT23))
    ll("OVP_TRIP", u7, 1)
    ll("OVP_TRIP", q9, 1)
    sh.power("AGND", *q9.pin_pos(2), ground=True)
    ll("DISC_INP", q9, 3)

    sh.text(p["note"], 33.02, 33.02)
    return sh


def build_aux_rails(sh, p):
    """LMR36015 5V buck + 3V3 LDO.

    p: vin_net  input net ("VBUS_F" p1 / "VBUS_P" p2 - post hot-swap)
       en_pgd   False (p1: EN tied to VIN) / True (p2: EN <- HS_PGD so the
                aux buck stays off while the LM5069 is still in inrush)
       note     sheet text
    """
    res, cap, gl, ll = helpers(sh)
    U8 = kg.get_symbol("labbench", "LMR36015AQRNXRQ1")
    U9 = kg.get_symbol("Regulator_Linear", "NCP1117-3.3_SOT223")
    L = kg.get_symbol("Device", "L")
    vin = p["vin_net"]

    u8 = sh.add(kg.Placed(U8, "U8", "LMR36015AQRNXRQ1", 76.2, 78.74,
                          footprint="labbench:LMR36015_RNX_VQFN-HR-12"))
    for pin in ("2", "10"):                          # VIN x2
        gl(vin, u8, pin, shape="input")
    if p["en_pgd"]:
        gl("HS_PGD", u8, 9, shape="input")           # EN gated by LM5069 PGD
    else:
        gl(vin, u8, "9", shape="input")              # EN tied to VIN (ds: allowed)
    for pin in ("1", "11", "6"):                     # PGND x2 + AGND (ds: tie to system gnd)
        sh.power("PGND", *u8.pin_pos(pin), ground=True)
    c50 = cap("C50", "4.7u/50V", 38.1, 83.82, fp=C_BULK)
    c51 = cap("C51", "4.7u/50V", 48.26, 83.82, fp=C_BULK)
    for c in (c50, c51):
        gl(vin, c, 1, shape="input")
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

    sh.text(p["note"], 33.02, 40.64)
    return sh


def build_mcu_can(sh, p):
    """STM32G431 + CAN + crystal + headers + NTCs.

    p: vbus_net  bus-sense divider source ("VBUS_F" p1 / "VBUS_P" p2)
       pb4       "nc" (p1) or "DROOP_EN" (p2)
       note      sheet text
    """
    res, cap, gl, ll = helpers(sh)
    MCU = kg.get_symbol("MCU_ST_STM32G4", "STM32G431CBTx")
    CAN = kg.get_symbol("labbench", "TCAN1042HGVDR")
    XTAL = kg.get_symbol("Device", "Crystal_GND24")
    LED = kg.get_symbol("Device", "LED")
    NTC = kg.get_symbol("Device", "Thermistor_NTC")
    C5 = kg.get_symbol("Connector_Generic", "Conn_01x05")
    C3 = kg.get_symbol("Connector_Generic", "Conn_01x03")

    u10 = sh.add(kg.Placed(MCU, "U10", "STM32G431CBT6", 88.9, 116.84,
                           footprint="Package_QFP:LQFP-48_7x7mm_P0.5mm"))
    # power
    for pin in ("1", "20", "21", "24", "36", "48"):  # VBAT, VREF+, VDDA, VDD x3
        sh.power("3V3", *u10.pin_pos(pin))
    for pin in ("19", "23", "35", "47"):             # VSSA, VSS x3
        sh.power("AGND", *u10.pin_pos(pin), ground=True)
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
    gl(p["vbus_net"], r60, 1, shape="input")
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
    if p["pb4"] == "nc":
        sh.no_connect(u10.pin_pos(41))              # PB4 spare (NJTRST pull-up at reset)
    else:
        gl(p["pb4"], u10, 41, shape="output")       # PB4 (NJTRST boot pull-up is benign:
                                                    # module boots in SAFE, output off)
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
    gl("OSC_OUT", y1, 3)                            # GND24: 1/3 crystal, 2/4 shield
    sh.power("AGND", *y1.pin_pos(2), ground=True)
    sh.power("AGND", *y1.pin_pos(4), ground=True)
    # 18p for CL=12pF crystals (the cheap China-market 3225 parts; the
    # HANDOVER-blessed alternative to hunting CL=8pF). 2*(12-3) = 18.
    c66 = cap("C66", "18p", 210.82, 137.16)
    c67 = cap("C67", "18p", 226.06, 137.16)
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

    sh.text(p["note"], 15.24, 33.02)
    return sh
