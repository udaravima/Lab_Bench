"""Generate the phase2-module KiCad project (600 W LM5143 module, docs/08).

Reuses the netlist-verified Phase-1 control core, sensing, disconnect,
aux-rails and mcu-can sheets from hardware/common/sheets_common.py with
Phase-2 parameters; draws the LM5069 hot-swap front end and the LM5143
two-phase power stage locally. EXPECTED_NETS at the bottom is the single
source of truth checked by check_netlist.py.

Run:  python3 gen_phase2.py   (from tools/, writes into the parent dir)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
import kicad_gen as kg          # noqa: E402  (shared, hardware/common)
import sheets_common as sc      # noqa: E402

LIB = os.path.join(HERE, "..", "..", "phase1-module", "lib")   # shared project lib
kg.add_lib_dir(LIB)

PROJECT = "phase2-module"
OUT = os.path.join(HERE, "..")

ROOT_UUID = "f47c11d2-88b1-4e02-9d3a-7f10a2c50001"
SHEETS = [  # name, fixed sheet-element uuid, page
    ("hot-swap",     "f47c11d2-88b1-4e02-9d3a-7f10a2c50010", "2"),
    ("power-stage",  "f47c11d2-88b1-4e02-9d3a-7f10a2c50011", "3"),
    ("control-core", "f47c11d2-88b1-4e02-9d3a-7f10a2c50012", "4"),
    ("sensing",      "f47c11d2-88b1-4e02-9d3a-7f10a2c50013", "5"),
    ("disconnect",   "f47c11d2-88b1-4e02-9d3a-7f10a2c50014", "6"),
    ("aux-rails",    "f47c11d2-88b1-4e02-9d3a-7f10a2c50015", "7"),
    ("mcu-can",      "f47c11d2-88b1-4e02-9d3a-7f10a2c50016", "8"),
    ("io",           "f47c11d2-88b1-4e02-9d3a-7f10a2c50017", "9"),
]

SOT23 = sc.SOT23
C_BULK = sc.C_BULK
FET_FP = "labbench:PowerFET_SON5x6_GDS"


def _sheet(name):
    path = f"/{ROOT_UUID}/{dict((n, u) for n, u, _ in SHEETS)[name]}"
    sh = kg.Sheet(PROJECT, path)
    return (sh,) + sc.helpers(sh)


def build_hot_swap():
    """LM5069-2 hot-swap front end (docs/08 s.3). 35 A fuse -> 1.5 mOhm sense
    -> CSD19536KTT (D2PAK) -> VBUS_P (the protected rail everything runs from)."""
    sh, res, cap, gl, ll = _sheet("hot-swap")
    HS = kg.get_symbol("labbench", "LM5069MM-2")
    QN = kg.get_symbol("Device", "Q_NMOS_GDS")
    FUSE = kg.get_symbol("Device", "Fuse")
    TVS = kg.get_symbol("Device", "D_TVS")

    f1 = sh.add(kg.Placed(FUSE, "F1", "35A blade", 43.18, 76.2, rot=90,
                          footprint="Fuse:Fuse_Blade_ATO_directSolder"))
    gl("VBUS", f1, 1, shape="input")
    ll("VBUS_FUSED", f1, 2)
    d5 = sh.add(kg.Placed(TVS, "D5", "SMBJ33A", 55.88, 96.52,
                          footprint="Diode_SMD:D_SMB"))
    ll("VBUS_FUSED", d5, 1)
    sh.power("PGND", *d5.pin_pos(2), ground=True)
    c91 = cap("C91", "100n", 43.18, 96.52)
    ll("VBUS_FUSED", c91, 1)
    sh.power("PGND", *c91.pin_pos(2), ground=True)

    r70 = res("R70", "1m5 3W Kelvin", 78.74, 76.2, rot=90)
    r70.footprint = "Resistor_SMD:R_2512_6332Metric"
    ll("VBUS_FUSED", r70, 1)
    ll("HS_SENSE", r70, 2)
    q14 = sh.add(kg.Placed(QN, "Q14", "CSD19536KTT", 116.84, 76.2,
                           footprint="Package_TO_SOT_SMD:TO-263-2"))
    ll("HS_SENSE", q14, 2)                          # D
    gl("VBUS_P", q14, 3, shape="output")            # S -> protected rail
    ll("HS_GATE", q14, 1)

    u12 = sh.add(kg.Placed(HS, "U12", "LM5069MM-2", 76.2, 137.16,
                           footprint="Package_SO:VSSOP-10_3x3mm_P0.5mm"))
    ll("VBUS_FUSED", u12, 2)                        # VIN
    ll("HS_SENSE", u12, 1)                          # SENSE
    ll("HS_GATE", u12, 10)                          # GATE
    gl("VBUS_P", u12, 9, shape="input")             # OUT (VDS/PGD sense)
    sh.power("PGND", *u12.pin_pos(5), ground=True)
    # UVLO 10.50/9.50 V, OVLO 33.1/31.8 V (Eq.21-23, 21 uA hysteresis)
    r71 = res("R71", "47.5K 1%", 33.02, 121.92)
    r72 = res("R72", "12.1K 1%", 33.02, 137.16)
    r73 = res("R73", "4.87K 1%", 33.02, 152.4)
    ll("VBUS_FUSED", r71, 1)
    ll("HS_UV", r71, 2)
    ll("HS_UV", r72, 1)
    ll("HS_UV", u12, 3)
    ll("HS_OV", r72, 2)
    ll("HS_OV", r73, 1)
    ll("HS_OV", u12, 4)
    sh.power("PGND", *r73.pin_pos(2), ground=True)
    # power limit 100 W (RPWR 15.0K, Eq.9/10); fault timer 4.7 ms / insertion
    # 73 ms (CT 100 nF)
    r74 = res("R74", "15.0K 1%", 55.88, 165.1)
    ll("HS_PWR", u12, 7)
    ll("HS_PWR", r74, 1)
    sh.power("PGND", *r74.pin_pos(2), ground=True)
    c90 = cap("C90", "100n", 71.12, 165.1)
    ll("HS_TIMER", u12, 6)
    ll("HS_TIMER", c90, 1)
    sh.power("PGND", *c90.pin_pos(2), ground=True)
    # PGD gates the aux buck: the load stays off while the FET is in its
    # linear inrush region (TI rule; docs/08 s.3). 5V0/3V3 then sequence the
    # LM5143 EN pull-up for free.
    r75 = res("R75", "100K", 152.4, 101.6, rot=90)
    gl("VBUS_P", r75, 1, shape="input")
    gl("HS_PGD", u12, 8, shape="output")
    gl("HS_PGD", r75, 2)

    fl = sh.pwr_flag(154.94, 165.1)                 # VBUS_FUSED is local to this sheet
    sh.label("VBUS_FUSED", fl.pin_pos(1))

    sh.text("HOT-SWAP FRONT END: 35A ATO fuse -> R70 1.5m (I_CL 36.7A typ / 32.3A min vs\\n"
            "26.6A max input) -> CSD19536KTT D2PAK (SOA-verified: 30V/3.35A/4.7ms hot-short\\n"
            "with 34% margin, docs/08 s.3). UVLO 10.5/9.5V; OVLO 33.1/31.8V auto-recover.\\n"
            "P_LIM 100W (R74), CT 100n: t_flt 4.7ms, insertion 73ms. PGD gates aux-buck EN:\\n"
            "load off until the pass FET is fully enhanced. LM5069-2 = auto-retry 0.5% duty.",
            27.94, 40.64)
    return sh


def build_power_stage():
    """LM5143 single-output interleaved two-phase buck (docs/08 s.2/s.9)."""
    sh, res, cap, gl, ll = _sheet("power-stage")
    LM = kg.get_symbol("labbench", "LM5143RHAR")
    QN = kg.get_symbol("Device", "Q_NMOS_GDS")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")
    DS = kg.get_symbol("Diode", "BAT54W")
    L = kg.get_symbol("Device", "L")
    CPOL = kg.get_symbol("Device", "C_Polarized")

    u3 = sh.add(kg.Placed(LM, "U3", "LM5143RHAR", 66.04, 106.68,
                          footprint="labbench:LM5143_RHA0040P"))

    # -- enable chain: 5V0 pull-up (sequenced by hot-swap PGD via the aux
    #    rail) + kill FET; EN_KILL = NOT(HW_EN) OR PS_OFF as in Phase 1
    r20 = res("R20", "100K", 27.94, 55.88)
    sh.power("5V0", *r20.pin_pos(1))
    ll("PS_EN", r20, 2)
    ll("PS_EN", u3, 31)                             # EN1
    ll("PS_EN", u3, 40)                             # EN2 (tied: single output)
    q5 = sh.add(kg.Placed(Q2N, "Q5", "2N7002", 15.24, 68.58, footprint=SOT23))
    ll("PS_EN", q5, 3)
    sh.power("AGND", *q5.pin_pos(2), ground=True)
    gl("EN_KILL", q5, 1, shape="input")
    q6 = sh.add(kg.Placed(Q2N, "Q6", "2N7002", 15.24, 96.52, footprint=SOT23))
    gl("HW_EN", q6, 1, shape="input")
    sh.power("AGND", *q6.pin_pos(2), ground=True)
    ll("KILL_HW", q6, 3)
    r22 = res("R22", "100K", 30.48, 83.82)
    sh.power("5V0", *r22.pin_pos(1))
    ll("KILL_HW", r22, 2)
    d4 = sh.add(kg.Placed(DS, "D4", "BAT54W", 43.18, 96.52,
                          footprint="Package_TO_SOT_SMD:SOT-323_SC-70"))
    ll("KILL_HW", d4, 1)
    gl("EN_KILL", d4, 3, shape="output")
    sh.no_connect(d4.pin_pos(2))
    d3 = sh.add(kg.Placed(DS, "D3", "BAT54W", 43.18, 111.76,
                          footprint="Package_TO_SOT_SMD:SOT-323_SC-70"))
    gl("PS_OFF", d3, 1, shape="input")
    gl("EN_KILL", d3, 3, shape="output")
    sh.no_connect(d3.pin_pos(2))
    r23 = res("R23", "100K", 30.48, 137.16)
    gl("EN_KILL", r23, 1)
    sh.power("AGND", *r23.pin_pos(2), ground=True)
    r19 = res("R19", "100K", 15.24, 158.75)
    gl("HW_EN", r19, 1, shape="input")
    sh.power("AGND", *r19.pin_pos(2), ground=True)

    # -- housekeeping: interleaved-mode straps + RT/SS/RES/DITH/VDDA/VCC/VCCX
    ll("PS_VDDA", u3, 36)                           # VDDA out
    ll("PS_VDDA", u3, 34)                           # MODE = VDDA: interleaved
    sh.power("AGND", *u3.pin_pos(3), ground=True)   # FB2 = AGND: interleaved
    ll("PS_COMP", u3, 29)                           # COMP1 = COMP2 (single EA)
    ll("PS_COMP", u3, 2)
    ll("PS_SS", u3, 30)                             # SS1 = SS2
    ll("PS_SS", u3, 1)
    sh.power("AGND", *u3.pin_pos(35), ground=True)  # AGND
    sh.power("AGND", *u3.pin_pos(41), ground=True)  # EP (star at NT1 on PCB)
    sh.power("PGND", *u3.pin_pos(17), ground=True)  # PGND1
    sh.power("PGND", *u3.pin_pos(14), ground=True)  # PGND2
    sh.no_connect(u3.pin_pos(39))                   # SYNCOUT unused
    sh.no_connect(u3.pin_pos(7))                    # PG2 meaningless (FB2=AGND)

    c21 = cap("C21", "1u", 147.32, 190.5)
    ll("PS_VDDA", c21, 1)
    sh.power("AGND", *c21.pin_pos(2), ground=True)
    r26 = res("R26", "63.4K 1%", 83.82, 190.5)      # RT: 22/0.347 (ds eq.1) = 347kHz
    ll("PS_RT", u3, 37)
    ll("PS_RT", r26, 1)
    sh.power("AGND", *r26.pin_pos(2), ground=True)
    c18 = cap("C18", "47n", 96.52, 190.5)           # SS: 21uA -> ~1.4ms (fw V_ref ramp is the real soft-start)
    ll("PS_SS", c18, 1)
    sh.power("AGND", *c18.pin_pos(2), ground=True)
    c19 = cap("C19", "470n", 109.22, 190.5)         # RES: hiccup enabled
    ll("PS_RES", u3, 32)
    ll("PS_RES", c19, 1)
    sh.power("AGND", *c19.pin_pos(2), ground=True)
    c20 = cap("C20", "47n", 121.92, 190.5)          # DITH +/-5% spread spectrum
    ll("PS_DITH", u3, 38)
    ll("PS_DITH", c20, 1)
    sh.power("AGND", *c20.pin_pos(2), ground=True)
    r39 = res("R39", "DNP 0R", 134.62, 190.5)       # fit to strap DITH->VDDA (disable)
    ll("PS_DITH", r39, 1)
    ll("PS_VDDA", r39, 2)
    r16 = res("R16", "100K", 198.12, 190.5)         # DEMB pulldown: DEM = battery-safe default
    gl("PS_FPWM", u3, 33, shape="input")            # DEMB: VIH 2V -> 3.3V GPIO ok
    gl("PS_FPWM", r16, 1)
    sh.power("AGND", *r16.pin_pos(2), ground=True)
    r18 = res("R18", "100K", 210.82, 190.5)
    gl("PS_PGOOD", u3, 24, shape="output")          # PG1
    gl("PS_PGOOD", r18, 2)
    sh.power("3V3", *r18.pin_pos(1))
    # VIN RC filter + VCC (pins 15+16 tied) + VCCX from the 5V aux rail
    r29 = res("R29", "4.7", 96.52, 55.88, rot=90)
    gl("VBUS_P", r29, 1, shape="input")
    ll("PS_VIN", r29, 2)
    ll("PS_VIN", u3, 25)
    c28 = cap("C28", "100n", 109.22, 60.96)
    ll("PS_VIN", c28, 1)
    sh.power("PGND", *c28.pin_pos(2), ground=True)
    c22 = cap("C22", "2.2u", 160.02, 190.5)
    c23 = cap("C23", "2.2u", 172.72, 190.5)
    ll("PS_VCC", u3, 15)
    ll("PS_VCC", u3, 16)
    ll("PS_VCC", c22, 1)
    ll("PS_VCC", c23, 1)
    sh.power("PGND", *c22.pin_pos(2), ground=True)
    sh.power("PGND", *c23.pin_pos(2), ground=True)
    sh.power("5V0", *u3.pin_pos(6))                 # VCCX <- 5V0 (>4.3V: internal reg off,
    c30 = cap("C30", "1u", 185.42, 190.5)           # ~0.8W moved out of the VQFN)
    sh.power("5V0", *c30.pin_pos(1))
    sh.power("PGND", *c30.pin_pos(2), ground=True)

    # -- compensation on COMP (gm EA, Type-II to AGND): R 2.2K + 27n, HF 2.2n
    r24 = res("R24", "2.2K", 33.02, 190.5, rot=90)
    c24 = cap("C24", "27n", 48.26, 190.5, rot=90)
    c25 = cap("C25", "2.2n", 63.5, 190.5, rot=90)
    ll("PS_COMP", r24, 1)
    ll("COMP_Z", r24, 2)
    ll("COMP_Z", c24, 1)
    sh.power("AGND", *c24.pin_pos(2), ground=True)
    ll("PS_COMP", c25, 1)
    sh.power("AGND", *c25.pin_pos(2), ground=True)
    gl("FB", u3, 28, shape="input")                 # FB1 <- base divider + injection

    # -- two half bridges, 180 deg interleaved
    q1 = sh.add(kg.Placed(QN, "Q1", "CSD18540Q5B", 127.0, 76.2, footprint=FET_FP))
    q2 = sh.add(kg.Placed(QN, "Q2", "CSD18540Q5B", 127.0, 114.3, footprint=FET_FP))
    q12 = sh.add(kg.Placed(QN, "Q12", "CSD18540Q5B", 165.1, 76.2, footprint=FET_FP))
    q13 = sh.add(kg.Placed(QN, "Q13", "CSD18540Q5B", 165.1, 114.3, footprint=FET_FP))
    for qh, ql, sw in ((q1, q2, "SW1"), (q12, q13, "SW2")):
        gl("VBUS_P", qh, 2, shape="input")
        gl(sw, qh, 3)
        gl(sw, ql, 2)
        sh.power("PGND", *ql.pin_pos(3), ground=True)
    ll("G_HS_A", q1, 1)
    ll("G_LS_A", q2, 1)
    ll("G_HS_B", q12, 1)
    ll("G_LS_B", q13, 1)
    # gate drives: HO/HOL (turn-on/turn-off) tied at the gate; split-R slew
    # tuning is a layout/bench option
    ll("G_HS_A", u3, 22)
    ll("G_HS_A", u3, 23)
    ll("G_LS_A", u3, 18)
    ll("G_LS_A", u3, 19)
    ll("G_HS_B", u3, 9)
    ll("G_HS_B", u3, 8)
    ll("G_LS_B", u3, 13)
    ll("G_LS_B", u3, 12)
    gl("SW1", u3, 21)
    gl("SW2", u3, 10)
    c27 = cap("C27", "100n", 144.78, 55.88, rot=90)
    ll("BST_A", u3, 20)
    ll("BST_A", c27, 1)
    gl("SW1", c27, 2)
    c35 = cap("C35", "100n", 182.88, 55.88, rot=90)
    ll("BST_B", u3, 11)
    ll("BST_B", c35, 1)
    gl("SW2", c35, 2)

    # -- inductors + per-phase shunts (CS Kelvin to inductor side, VOUT to
    #    output side; 73mV/3.5m: peak limit 20.9A typ, 18.9A min > 16.6A max
    #    normal peak, 23.4A max << 36A Isat)
    l1 = sh.add(kg.Placed(L, "L1", "6.8u MWSA1707S/XAL1510", 190.5, 71.12, rot=90,
                          footprint="Inductor_SMD:L_Coilcraft_XAL1510-682"))
    l3 = sh.add(kg.Placed(L, "L3", "6.8u MWSA1707S/XAL1510", 190.5, 109.22, rot=90,
                          footprint="Inductor_SMD:L_Coilcraft_XAL1510-682"))
    gl("SW1", l1, 1)
    ll("PH_CS_A", l1, 2)
    gl("SW2", l3, 1)
    ll("PH_CS_B", l3, 2)
    # 3.75 mOhm per phase as 2x 7m5 1206 1W in parallel (sourcing pass
    # 2026-07-18): pulls the worst-corner peak limit to 21.9 A, inside the
    # Sunlord MWSA1707S-6R8MT's 22 A Isat while keeping 6% no-false-trip
    # margin; also fine with the XAL1510 (36 A). Each 1206 carries I/2.
    r36 = res("R36", "7m5 1W", 215.9, 71.12, rot=90)
    r42 = res("R42", "7m5 1W", 222.25, 71.12, rot=90)
    r37 = res("R37", "7m5 1W", 215.9, 109.22, rot=90)
    r57 = res("R57", "7m5 1W", 222.25, 109.22, rot=90)
    for r in (r36, r42, r37, r57):
        r.footprint = "Resistor_SMD:R_1206_3216Metric"
    for r in (r36, r42):
        ll("PH_CS_A", r, 1)
        gl("VOUT_INT", r, 2, shape="output")
    for r in (r37, r57):
        ll("PH_CS_B", r, 1)
        gl("VOUT_INT", r, 2, shape="output")
    ll("PH_CS_A", u3, 27)                           # CS1
    ll("PH_CS_B", u3, 4)                            # CS2
    gl("VOUT_INT", u3, 26)                          # VOUT1
    gl("VOUT_INT", u3, 5)                           # VOUT2

    # -- input bank (8x 10u X7S + 470u bulk = the LM5069's 550uF COUT budget)
    cin = [cap(f"C{6+i}", "10u/50V X7S", 15.24 + 10.16 * i, 170.18, fp=C_BULK)
           for i in range(8)]
    c14 = sh.add(kg.Placed(CPOL, "C14", "470u/50V", 99.06, 170.18,
                           footprint="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"))
    for c in cin + [c14]:
        gl("VBUS_P", c, 1, shape="input")
        sh.power("PGND", *c.pin_pos(2), ground=True)
    # -- output bank: 4x 220u/35V hybrid polymer + 6x 22u MLCC + preload
    cpoly = [sh.add(kg.Placed(CPOL, r, "220u/35V hybrid", x, 152.4,
                              footprint="Capacitor_SMD:CP_Elec_10x10.5"))
             for r, x in (("C15", 124.46), ("C16", 134.62), ("C36", 144.78), ("C37", 154.94))]
    cout = [cap(r, "10u/50V X7S", x, 152.4, fp=C_BULK)
            for r, x in (("C38", 167.64), ("C40", 177.8), ("C45", 187.96),
                         ("C46", 198.12), ("C47", 208.28), ("C48", 218.44))]
    r27 = res("R27", "4.7K 0.5W preload", 231.14, 152.4)
    r27.footprint = "Resistor_SMD:R_2512_6332Metric"
    for c in cpoly + cout + [r27]:
        gl("VOUT_INT", c, 1, shape="input")
        sh.power("PGND", *c.pin_pos(2), ground=True)
    # -- SW snubbers (DNP, bench-derived)
    r40 = res("R40", "DNP snub", 234.95, 96.52)
    c49 = cap("C49", "DNP", 234.95, 110.49)
    gl("SW1", r40, 1)
    ll("SNUB_A", r40, 2)
    ll("SNUB_A", c49, 1)
    sh.power("PGND", *c49.pin_pos(2), ground=True)
    r41 = res("R41", "DNP snub", 254.0, 96.52)
    c58 = cap("C58", "DNP", 254.0, 110.49)
    gl("SW2", r41, 1)
    ll("SNUB_B", r41, 2)
    ll("SNUB_B", c58, 1)
    sh.power("PGND", *c58.pin_pos(2), ground=True)

    sh.text("POWER STAGE: LM5143 two-phase interleaved (MODE=VDDA, FB2=AGND, COMP1=COMP2,\\n"
            "SS1=SS2), 347kHz/phase (RT 63.4K), peak-current-mode, 3.75m sense (2x 7m5 1206:\\n"
            "worst-corner peak 21.9A fits the 22A-Isat Sunlord AND the 36A XAL1510).\\n"
            "L = 6.8uH NOT 4.7uH: internal slope comp (~100mV/us) needs it for subharmonic\\n"
            "stability at D->0.93 (docs/08 s.2). VCCX <- 5V0. DEMB low = DEM (battery-safe).\\n"
            "EN: 5V0 pull-up (rail itself is PGD-sequenced) AND NOT(EN_KILL).", 15.24, 27.94)
    return sh


def build_io():
    """Slot connector (docs/01 s.3 signal set; physical family deferred to the
    batch PCB pass), output terminals, fan."""
    sh, res, cap, gl, ll = _sheet("io")
    C2 = kg.get_symbol("Connector_Generic", "Conn_01x02")
    C4 = kg.get_symbol("Connector_Generic", "Conn_01x04")
    C8 = kg.get_symbol("Connector_Generic", "Conn_01x08")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")
    DF = kg.get_symbol("Diode", "1N4148W")

    # XT60PW-M (sourcing pass 2026-07-18): 1=+, 2=-. Power-first mating
    # comes from connector height stagger vs the signal row; land pattern
    # from the Amass drawing at the footprint pass (placeholder fp here).
    j1 = sh.add(kg.Placed(C2, "J1", "XT60PW-M SLOT PWR", 38.1, 78.74,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"))
    gl("VBUS", j1, 1, shape="input")
    sh.power("PGND", *j1.pin_pos(2), ground=True)

    j4 = sh.add(kg.Placed(C2, "J4", "XT60PW-M OUTPUT", 38.1, 116.84,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"))
    gl("VOUT", j4, 1, shape="input")
    sh.power("PGND", *j4.pin_pos(2), ground=True)

    j5 = sh.add(kg.Placed(C8, "J5", "SLOT SIGNALS", 38.1, 165.1,
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

    for i, (net, kind) in enumerate((("PGND", "gnd"), ("VBUS", "g"),
                                     ("VBUS_P", "g"), ("VOUT", "g"))):
        fl = sh.pwr_flag(175.26 + 15.24 * i, 63.5)
        if kind == "gnd":
            sh.power(net, *fl.pin_pos(1), ground=True)
        else:
            sh.glabel(net, fl.pin_pos(1))

    sh.text("IO: slot connector split into power blades (>=30A, first-mate/last-break) +\\n"
            "signal row (CAN, HW_EN, slot straps, PRESENT->PGND). Physical connector family\\n"
            "chosen at the batch PCB pass with the backplane (docs/08 s.12) - generic\\n"
            "headers stand in so the netlist is final. Fan: 5V, low-side PWM switch.", 15.24, 33.02)
    return sh


# ---- shared sheets (hardware/common/sheets_common.py) with Phase-2 values --

def _shared(name, builder, params):
    def build():
        path = f"/{ROOT_UUID}/{dict((n, u) for n, u, _ in SHEETS)[name]}"
        return builder(kg.Sheet(PROJECT, path), params)
    return build


P2_CONTROL_CORE = {
    "r_top": "46.4K 0.1%",    # ceiling 0.6V x 47.4 = 28.44V (LM5143 FB = 0.6V)
    "r_inj": "5.6K",          # authority 0.705mA vs 0.613mA needed (15% margin)
    "note": "CONTROL CORE - dual error amps + diode-OR minimum selector into LM5143 FB1 node.\\n"
            "Whichever amp demands the LOWER output wins -> automatic CV/CC crossover.\\n"
            "LM5143 FB = 0.6V (NOT 0.8V like the LM5145): ceiling 28.44V, R_inj 5.6K (docs/08 s.5).",
}
P2_SENSING = {
    "shunts": [("R30", "1m0 3W Kelvin"), ("R34", "1m0 3W Kelvin")],
    "div_top": "110K 0.1%",
    "droop": {"r_droop": "267K 1%"},
    "note": "SENSING: 2x 1m0 2512 in parallel = 0.5m shunt (sourcing-friendly; cal absorbs\\n"
            "the split). INA240A3 x100 -> 0.05V/A, 1.5V @ 30A (A4 would exceed the DAC's\\n"
            "2.5V ceiling - docs/08 s.4). V divider /12 (110K/10K). Droop: 267K + TMUX1101\\n"
            "into the V_MEAS node, ~20mV/A; fw applies x0.9668 to V_ref in droop modes.",
}
P2_DISCONNECT = {
    "extra_fets": ["Q10", "Q11"],
    "fet_val": "CSD18540Q5B",
    "ovp_top": "215K 0.1%",
    "ovp_bot": "20.0K 0.1%",
    "ref_tl431": True,
    "note": "OUTPUT DISCONNECT: back-to-back NFETs, 2 parallel per direction (30A: ~2.3W\\n"
            "spread over 4 packages). LTC7004 charge-pump driver, static switching only.\\n"
            "OVP: VOUT_INT x 20/235 vs TL431B 2.495V -> trips 29.35V. The squeeze is real:\\n"
            "ceiling 28.4 < trip 29.4 < bus 30V, hence 0.1% divider + 0.5% reference\\n"
            "(a 3V3-LDO-derived reference would wander past the bus voltage; docs/08 s.8).",
}
P2_AUX_RAILS = {
    "vin_net": "VBUS_P",
    "en_pgd": True,
    "note": "AUX RAILS: VBUS_P (post hot-swap) -> LMR36015 -> 5V0 -> NCP1117 -> 3V3.\\n"
            "EN <- LM5069 PGD: the aux buck (and so everything downstream, including the\\n"
            "LM5143 EN pull-up) waits until the hot-swap FET is fully enhanced.\\n"
            "5V0 also feeds LM5143 VCCX (gate drive ~28mA, docs/08 s.2).",
}
P2_MCU_CAN = {
    "vbus_net": "VBUS_P",
    "pb4": "DROOP_EN",
    "note": "MCU: STM32G431CBT6, Phase-1 pin map + PB4 = DROOP_EN (NJTRST boot pull-up is\\n"
            "benign: SAFE state, output off). Shunt-region temperature = INA228 die temp\\n"
            "register - no third NTC pin needed. OUT_REQ stays on PB14; I2C on PA8/PA9\\n"
            "(PB8 = BOOT0). Hot-swap health is inferred from AUX_PG (PGD gates the aux rail).",
}

BUILDERS = {
    "hot-swap": build_hot_swap,
    "power-stage": build_power_stage,
    "control-core": _shared("control-core", sc.build_control_core, P2_CONTROL_CORE),
    "sensing": _shared("sensing", sc.build_sensing, P2_SENSING),
    "disconnect": _shared("disconnect", sc.build_disconnect, P2_DISCONNECT),
    "aux-rails": _shared("aux-rails", sc.build_aux_rails, P2_AUX_RAILS),
    "mcu-can": _shared("mcu-can", sc.build_mcu_can, P2_MCU_CAN),
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
    sh.text("Lab_Bench phase-2 module - 600W two-phase CV/CC module (docs/08).\\n"
            "Generated schematic; run tools/gen_phase2.py, never hand-edit.\\n"
            "Control core / sensing / disconnect / aux / MCU sheets are the verified\\n"
            "Phase-1 blocks (hardware/common/sheets_common.py) with Phase-2 values.", 38.1, 139.7)
    return sh


def main():
    root = build_root()
    open(os.path.join(OUT, f"{PROJECT}.kicad_sch"), "w").write(root.emit())
    for name, _, _ in SHEETS:
        sheet = BUILDERS[name]()
        open(os.path.join(OUT, f"{name}.kicad_sch"), "w").write(sheet.emit())
    pro = os.path.join(OUT, f"{PROJECT}.kicad_pro")
    if not os.path.exists(pro):
        open(pro, "w").write('{\n  "meta": { "filename": "%s.kicad_pro", "version": 1 },\n'
                             '  "schematic": { "legacy_lib_dir": "", "legacy_lib_list": [] }\n}\n' % PROJECT)
    # project lib tables point at the shared library in phase1-module/lib
    open(os.path.join(OUT, "sym-lib-table"), "w").write(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "labbench")(type "KiCad")(uri "${KIPRJMOD}/../phase1-module/lib/labbench.kicad_sym")'
        '(options "")(descr "Lab_Bench project symbols (shared)"))\n)\n')
    open(os.path.join(OUT, "fp-lib-table"), "w").write(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "labbench")(type "KiCad")(uri "${KIPRJMOD}/../phase1-module/lib/labbench.pretty")'
        '(options "")(descr "project footprints (shared)"))\n)\n')
    print("generated:", PROJECT)


# Single source of truth for connectivity, asserted by check_netlist.py.
# net name -> set of "REF.PIN"; "~" prefix = superset (extras allowed).
EXPECTED_NETS = {
    # -- control core (shared sheet; identical members to Phase 1)
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
    "FB":        {"R5.2", "R8.2", "R1.2", "R2.1", "U3.28"},
    "V_MEAS":    {"U2.3", "R32.2", "R33.1", "C32.1", "U10.8", "U13.2"},
    "I_MEAS":    {"U2.5", "R31.2", "C31.1", "U10.9", "R35.1"},
    "~VOUT_INT": {"R36.2", "R42.2", "R37.2", "R57.2", "U3.26", "U3.5",
                  "C15.1", "C16.1", "C36.1", "C37.1", "C38.1", "C40.1",
                  "C45.1", "C46.1", "C47.1", "C48.1", "R27.1",
                  "R1.1", "R30.1", "R34.1", "U4.8", "U5.10", "R45.1"},
    "VOUT_SW":   {"R30.2", "R34.2", "U4.1", "U5.9", "Q3.2", "Q10.2"},
    "~VOUT":     {"Q4.2", "Q11.2", "U5.8", "R32.1", "J4.1"},
    # -- droop hardware
    "DROOP_R":   {"R35.2", "U13.1"},
    "DROOP_EN":  {"U13.4", "R38.1", "U10.41"},
    # -- hot-swap front end
    "VBUS":       {"J1.1", "F1.1"},
    "VBUS_FUSED": {"F1.2", "D5.1", "C91.1", "R70.1", "U12.2", "R71.1"},
    "HS_SENSE":   {"R70.2", "U12.1", "Q14.2"},
    "HS_GATE":    {"U12.10", "Q14.1"},
    "HS_UV":      {"R71.2", "R72.1", "U12.3"},
    "HS_OV":      {"R72.2", "R73.1", "U12.4"},
    "HS_TIMER":   {"U12.6", "C90.1"},
    "HS_PWR":     {"U12.7", "R74.1"},
    "HS_PGD":     {"U12.8", "R75.2", "U8.9"},
    # -- power stage
    "PS_EN":     {"R20.2", "Q5.3", "U3.31", "U3.40"},
    "KILL_HW":   {"Q6.3", "R22.2", "D4.1"},
    "EN_KILL":   {"D4.3", "D3.3", "R23.1", "Q5.1", "Q7.1"},
    "PS_OFF":    {"D3.1", "U10.40"},
    "HW_EN":     {"Q6.1", "R19.1", "J5.3", "U10.43"},
    "PS_RT":     {"U3.37", "R26.1"},
    "PS_SS":     {"U3.30", "U3.1", "C18.1"},
    "PS_COMP":   {"U3.29", "U3.2", "R24.1", "C25.1"},
    "COMP_Z":    {"R24.2", "C24.1"},
    "PS_RES":    {"U3.32", "C19.1"},
    "PS_DITH":   {"U3.38", "C20.1", "R39.1"},
    "PS_VDDA":   {"U3.36", "U3.34", "C21.1", "R39.2"},
    "PS_FPWM":   {"U3.33", "R16.1", "U10.29"},
    "PS_PGOOD":  {"U3.24", "R18.2", "U10.39"},
    "PS_VIN":    {"R29.2", "U3.25", "C28.1"},
    "PS_VCC":    {"U3.15", "U3.16", "C22.1", "C23.1"},
    "G_HS_A":    {"U3.22", "U3.23", "Q1.1"},
    "G_LS_A":    {"U3.18", "U3.19", "Q2.1"},
    "~SW1":      {"U3.21", "Q1.3", "Q2.2", "L1.1", "C27.2", "R40.1"},
    "BST_A":     {"U3.20", "C27.1"},
    "G_HS_B":    {"U3.9", "U3.8", "Q12.1"},
    "G_LS_B":    {"U3.13", "U3.12", "Q13.1"},
    "~SW2":      {"U3.10", "Q12.3", "Q13.2", "L3.1", "C35.2", "R41.1"},
    "BST_B":     {"U3.11", "C35.1"},
    "PH_CS_A":   {"L1.2", "R36.1", "R42.1", "U3.27"},
    "PH_CS_B":   {"L3.2", "R37.1", "R57.1", "U3.4"},
    "SNUB_A":    {"R40.2", "C49.1"},
    "SNUB_B":    {"R41.2", "C58.1"},
    # -- sensing
    "INA240_OUT": {"U4.5", "R31.1"},
    "I2C_SCL":   {"U5.5", "R62.2", "U10.31"},
    "I2C_SDA":   {"U5.4", "R63.2", "U10.30"},
    "INA_ALERT": {"U5.3", "U10.44"},
    # -- disconnect
    "DISC_GATE": {"Q3.1", "Q4.1", "Q10.1", "Q11.1", "U6.6", "U6.7"},
    "DISC_SRC":  {"Q3.3", "Q4.3", "Q10.3", "Q11.3", "U6.8", "C41.2"},
    "LTC_BST":   {"U6.9", "C41.1"},
    "DISC_INP":  {"R43.2", "U6.4", "R44.1", "Q7.3", "Q9.3"},
    "OUT_REQ":   {"R43.1", "U10.28"},
    "OVP_DIV":   {"R45.2", "R46.1", "C44.1", "U7.3"},
    "REF_2V5":   {"R47.2", "D8.1", "D8.2", "U7.4"},
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
    "FAN_PWM":   {"U10.22", "Q8.1"},
    "FAN_NEG":   {"J6.2", "Q8.3", "D6.2"},
    # -- power rails (superset: must contain at least these)
    "~VBUS_P":   {"Q14.3", "U12.9", "R75.1", "R29.1",
                  "Q1.2", "Q12.2",
                  "C6.1", "C7.1", "C8.1", "C9.1", "C10.1", "C11.1", "C12.1",
                  "C13.1", "C14.1",
                  "U8.2", "U8.10", "C50.1", "C51.1", "R60.1"},
    "~3V3":      {"U1.1", "C3.1", "U9.2", "C57.1", "R18.1", "R52.1",
                  "R62.1", "R63.1", "R66.2", "R67.1", "R68.1", "U10.1", "U10.20",
                  "U10.21", "U10.24", "U10.36", "U10.48", "U11.5", "C70.1", "J2.1"},
    "~5V0":      {"U2.8", "C5.1", "L2.2", "C54.1", "C55.1", "U9.3", "C56.1",
                  "R20.1", "R22.1", "R50.1", "U6.1", "U6.2", "C42.1", "U7.5",
                  "C43.1", "R47.1", "U11.3", "C69.1", "J6.1", "D6.1", "U4.6",
                  "C33.1", "U13.5", "C39.1", "U3.6", "C30.1"},
    "~AGND":     {"U1.3", "U1.4", "U1.5", "C3.2", "C4.2", "C5.2", "U2.4", "R2.2",
                  "U4.2", "U4.3", "U4.4", "U4.7", "C31.2", "C32.2", "C33.2",
                  "C34.2", "R33.2", "U5.1", "U5.2", "U5.7", "R46.2", "D8.3",
                  "C44.2", "R44.2", "Q7.2", "Q9.2", "R23.2", "R16.2", "R19.2",
                  "R26.2", "C18.2", "C19.2", "C20.2", "C21.2", "C24.2", "C25.2",
                  "U3.3", "U3.35", "U3.41", "Q5.2", "Q6.2",
                  "R38.2", "U13.3", "C39.2",
                  "R61.2", "C62.2", "RT1.2", "RT2.2", "C66.2", "C67.2",
                  "C68.2", "R64.2", "R65.2", "Y1.2", "Y1.4", "U10.19", "U10.23",
                  "U10.35", "U10.47", "U11.2", "C69.2", "C70.2", "J2.5", "J3.1",
                  "NT1.1", "U6.3", "U6.5", "U6.11", "U7.2"},
    "~PGND":     {"U3.17", "U3.14", "Q2.3", "Q13.3", "C22.2", "C23.2", "C28.2",
                  "C30.2", "C49.2", "C58.2",
                  "C6.2", "C7.2", "C8.2", "C9.2", "C10.2", "C11.2", "C12.2",
                  "C13.2", "C14.2",
                  "C15.2", "C16.2", "C36.2", "C37.2", "C38.2", "C40.2",
                  "C45.2", "C46.2", "C47.2", "C48.2", "R27.2",
                  "U12.5", "R73.2", "R74.2", "C90.2", "C91.2", "D5.2",
                  "U8.1", "U8.6", "U8.11", "C50.2", "C51.2", "C53.2", "C54.2",
                  "C55.2", "U9.1", "C56.2", "C57.2", "R51.2",
                  "J1.2", "J4.2", "J5.7", "J5.8", "Q8.2", "NT1.2"},
}

if __name__ == "__main__":
    main()
