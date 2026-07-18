"""Generate the phase3-backplane KiCad project (docs/09 s.2).

Near-passive: 8 slot connector pairs, bus-entry shunt + INA228, fail-safe
E-stop pull-up chain, CAN end terminations, hardwired slot-ID straps
(firmware convention: grounded strap sets a bit, all-open = slot 0 —
board.h SLOT_ID_IN), PRESENT lines routed raw to the manager connector.

Run:  python3 gen_backplane.py   (from tools/, writes into the parent dir)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
import kicad_gen as kg          # noqa: E402

LIB = os.path.join(HERE, "..", "..", "phase1-module", "lib")   # shared project lib
kg.add_lib_dir(LIB)

PROJECT = "phase3-backplane"
OUT = os.path.join(HERE, "..")
ROOT_UUID = "a91b33c4-5d20-4f7e-8c11-30b7d2e50001"

R_FP = "Resistor_SMD:R_0603_1608Metric"
C_FP = "Capacitor_SMD:C_0603_1608Metric"
N_SLOTS = 8


def build():
    sh = kg.Sheet(PROJECT, "/")
    sh.uuid = ROOT_UUID

    def res(ref, val, x, y, rot=0, fp=R_FP):
        return sh.add(kg.Placed(kg.get_symbol("Device", "R"), ref, val, x, y, rot, footprint=fp))

    def cap(ref, val, x, y, rot=0, fp=C_FP):
        return sh.add(kg.Placed(kg.get_symbol("Device", "C"), ref, val, x, y, rot, footprint=fp))

    def gl(net, part, pin, shape="passive"):
        sh.glabel(net, part.pin_pos(pin), rot=part.label_rot(pin), shape=shape)

    def ll(net, part, pin):
        sh.label(net, part.pin_pos(pin), rot=part.label_rot(pin))

    C1P = kg.get_symbol("Connector_Generic", "Conn_01x01")
    C2P = kg.get_symbol("Connector_Generic", "Conn_01x02")
    C4P = kg.get_symbol("Connector_Generic", "Conn_01x04")
    C8P = kg.get_symbol("Connector_Generic", "Conn_01x08")
    C20P = kg.get_symbol("Connector_Generic", "Conn_01x20")
    TVS = kg.get_symbol("Device", "D_TVS")
    CPOL = kg.get_symbol("Device", "C_Polarized")
    INA = kg.get_symbol("labbench", "INA228AIDGSR")

    # ---- power entry: lugs -> bus shunt -> distribution -------------------
    lug1 = sh.add(kg.Placed(C1P, "J30", "VBUS+ LUG M6", 25.4, 40.64,
                            footprint="MountingHole:MountingHole_6.4mm_M6_Pad_TopBottom"))
    lug2 = sh.add(kg.Placed(C1P, "J31", "RETURN LUG M6", 25.4, 55.88,
                            footprint="MountingHole:MountingHole_6.4mm_M6_Pad_TopBottom"))
    ll("VBUS_IN", lug1, 1)
    sh.power("PGND", *lug2.pin_pos(1), ground=True)
    # 2x BVS-M-R0005 (0.5 mOhm 3920) in parallel = 0.25 mOhm (sourcing
    # pass 2026-07-18, $1.21 total); 3920 land pattern at the footprint
    # pass (2512 placeholder). Verify the BVS power rating at order.
    rs1 = res("RS1", "0m5 3920", 45.72, 40.64, rot=90)
    rs2 = res("RS2", "0m5 3920", 58.42, 40.64, rot=90)
    for r in (rs1, rs2):
        r.footprint = "labbench:R3920_BVS"
        ll("VBUS_IN", r, 1)
        gl("VBUS", r, 2, shape="output")
    d5 = sh.add(kg.Placed(TVS, "D5", "SMBJ33A", 66.04, 55.88,
                          footprint="Diode_SMD:D_SMB"))
    gl("VBUS", d5, 1, shape="input")
    sh.power("PGND", *d5.pin_pos(2), ground=True)
    c2 = sh.add(kg.Placed(CPOL, "C2", "470u/50V", 78.74, 55.88,
                          footprint="Capacitor_SMD:CP_Elec_16x17.5"))
    c3 = cap("C3", "100n", 91.44, 55.88)
    for c in (c2, c3):
        gl("VBUS", c, 1, shape="input")
        sh.power("PGND", *c.pin_pos(2), ground=True)

    # ---- bus-entry meter: INA228 across the shunt, high-side --------------
    u1 = sh.add(kg.Placed(INA, "U1", "INA228", 66.04, 96.52,
                          footprint="Package_SO:VSSOP-10_3x3mm_P0.5mm"))
    ll("VBUS_IN", u1, 10)                           # IN+ (supply side, Kelvin)
    gl("VBUS", u1, 9, shape="input")                # IN-
    gl("VBUS", u1, 8, shape="input")                # VBUS sense (85V rated)
    sh.power("3V3", *u1.pin_pos(6))                 # VS from the manager
    sh.power("PGND", *u1.pin_pos(7), ground=True)
    sh.power("PGND", *u1.pin_pos(1), ground=True)   # A1 -> addr 0x40
    sh.power("PGND", *u1.pin_pos(2), ground=True)   # A0
    gl("I2C_SDA", u1, 4)
    gl("I2C_SCL", u1, 5)
    sh.no_connect(u1.pin_pos(3))                    # ALERT unused
    c1 = cap("C1", "100n", 45.72, 101.6)
    sh.power("3V3", *c1.pin_pos(1))
    sh.power("PGND", *c1.pin_pos(2), ground=True)

    # ---- E-stop chain: 3V3 -> NC switch loop -> 1k -> HW_EN ----------------
    j2 = sh.add(kg.Placed(C2P, "J2", "E-STOP NC (jumper if absent)", 25.4, 137.16,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"))
    sh.power("3V3", *j2.pin_pos(1))
    ll("ESTOP_RET", j2, 2)
    r1 = res("R1", "1K", 45.72, 137.16, rot=90)
    ll("ESTOP_RET", r1, 1)
    gl("HW_EN", r1, 2, shape="output")

    # ---- CAN terminations at both physical ends ---------------------------
    r2 = res("R2", "120R slot0-end", 66.04, 137.16)
    r3 = res("R3", "120R slot7-end", 66.04, 152.4)
    for r in (r2, r3):
        gl("CAN_H", r, 1)
        gl("CAN_L", r, 2)

    # ---- manager connector ------------------------------------------------
    j1 = sh.add(kg.Placed(C20P, "J1", "MANAGER", 116.84, 111.76,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x20_P2.54mm_Vertical"))
    gl("VBUS", j1, 1, shape="output")
    gl("VBUS", j1, 2, shape="output")
    for p in ("3", "4", "5", "6"):
        sh.power("PGND", *j1.pin_pos(p), ground=True)
    gl("CAN_H", j1, 7)
    gl("CAN_L", j1, 8)
    gl("HW_EN", j1, 9)
    sh.power("3V3", *j1.pin_pos(10))                # manager sources this rail
    gl("I2C_SDA", j1, 11)
    gl("I2C_SCL", j1, 12)
    for n in range(N_SLOTS):
        gl(f"PRESENT{n}", j1, str(13 + n), shape="output")

    # ---- 8 slot connector pairs -------------------------------------------
    # Power 1x04 (2x VBUS blades + 2x PGND) and signal 1x08 mirroring the
    # module io sheet: CAN_H, CAN_L, HW_EN, SLOT_ID0..2, PRESENT, GND.
    # Slot-ID straps are hardwired copper per the FIRMWARE convention
    # (board.h SLOT_ID_IN inverts): grounded pin = bit set, open = bit clear
    # -> slot 0 all-open ... slot 7 all-grounded. Open bits get explicit
    # no-connects; the netlist checker asserts the exact pattern.
    for n in range(N_SLOTS):
        x = 172.72 + (n % 4) * 30.48
        y = 40.64 + (n // 4) * 76.2
        jp = sh.add(kg.Placed(C2P, f"J1{n}", f"SLOT{n} XT60PW-F", x, y,
                              footprint="labbench:XT60PW-F"))
        gl("VBUS", jp, 1, shape="output")
        sh.power("PGND", *jp.pin_pos(2), ground=True)
        js = sh.add(kg.Placed(C8P, f"J2{n}", f"SLOT{n} SIG", x, y + 27.94,
                              footprint="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical"))
        gl("CAN_H", js, 1)
        gl("CAN_L", js, 2)
        gl("HW_EN", js, 3)
        for b in range(3):
            if (n >> b) & 1:
                sh.power("PGND", *js.pin_pos(str(4 + b)), ground=True)
            else:
                sh.no_connect(js.pin_pos(str(4 + b)))
        gl(f"PRESENT{n}", js, 7)
        sh.power("PGND", *js.pin_pos(8), ground=True)

    fl = sh.pwr_flag(45.72, 172.72)
    sh.power("PGND", *fl.pin_pos(1), ground=True)
    fl = sh.pwr_flag(60.96, 172.72)
    sh.glabel("VBUS", fl.pin_pos(1))
    fl = sh.pwr_flag(76.2, 172.72)
    sh.label("VBUS_IN", fl.pin_pos(1))
    fl = sh.pwr_flag(91.44, 172.72)
    sh.power("3V3", *fl.pin_pos(1))

    sh.text("BACKPLANE (docs/09 s.2): near-passive. Bus entry: lugs -> 250uOhm bar shunt\\n"
            "(placeholder fp; real bar at the PCB pass) -> INA228 high-side meter (0x40 on\\n"
            "the manager-local I2C; pull-ups live on the manager). E-stop: 3V3 THROUGH the\\n"
            "NC panel switch -> 1K -> HW_EN; broken wire / unplugged manager = all SAFE.\\n"
            "CAN: 120R at both physical ends; manager is a stub. Slot straps: grounded pin\\n"
            "= bit set (fw board.h SLOT_ID_IN inverts) -> slot 0 = all open.", 25.4, 190.5)
    return sh


def main():
    sh = build()
    open(os.path.join(OUT, f"{PROJECT}.kicad_sch"), "w").write(sh.emit(paper="A3"))
    pro = os.path.join(OUT, f"{PROJECT}.kicad_pro")
    if not os.path.exists(pro):
        open(pro, "w").write('{\n  "meta": { "filename": "%s.kicad_pro", "version": 1 },\n'
                             '  "schematic": { "legacy_lib_dir": "", "legacy_lib_list": [] }\n}\n' % PROJECT)
    open(os.path.join(OUT, "sym-lib-table"), "w").write(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "labbench")(type "KiCad")(uri "${KIPRJMOD}/../phase1-module/lib/labbench.kicad_sym")'
        '(options "")(descr "Lab_Bench project symbols (shared)"))\n)\n')
    open(os.path.join(OUT, "fp-lib-table"), "w").write(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "labbench")(type "KiCad")(uri "${KIPRJMOD}/../phase1-module/lib/labbench.pretty")'
        '(options "")(descr "project footprints (shared)"))\n)\n')
    print("generated:", PROJECT)


def _slot_nets():
    nets = {}
    for n in range(N_SLOTS):
        nets[f"PRESENT{n}"] = {f"J2{n}.7", "J1." + str(13 + n)}
    return nets


EXPECTED_NETS = {
    # All nets EXACT (no "~" supersets): on a near-passive board the full
    # membership is enumerable, and exactness means a slot-ID strap pin
    # grounded in error cannot hide as an allowed extra in PGND.
    "VBUS_IN":   {"J30.1", "RS1.1", "RS2.1", "U1.10"},
    "VBUS":      {"RS1.2", "RS2.2", "U1.9", "U1.8", "D5.1", "C2.1", "C3.1",
                  "J1.1", "J1.2", *{f"J1{n}.1" for n in range(N_SLOTS)}},
    "ESTOP_RET": {"J2.2", "R1.1"},
    "HW_EN":     {"R1.2", "J1.9", *{f"J2{n}.3" for n in range(N_SLOTS)}},
    "CAN_H":     {"R2.1", "R3.1", "J1.7", *{f"J2{n}.1" for n in range(N_SLOTS)}},
    "CAN_L":     {"R2.2", "R3.2", "J1.8", *{f"J2{n}.2" for n in range(N_SLOTS)}},
    "I2C_SDA":   {"U1.4", "J1.11"},
    "I2C_SCL":   {"U1.5", "J1.12"},
    **_slot_nets(),
    "3V3":       {"U1.6", "C1.1", "J1.10", "J2.1"},
    "PGND":      {"J31.1", "D5.2", "C2.2", "C3.2", "C1.2", "U1.7", "U1.1", "U1.2",
                  "J1.3", "J1.4", "J1.5", "J1.6",
                  *{f"J1{n}.2" for n in range(N_SLOTS)},
                  *{f"J2{n}.8" for n in range(N_SLOTS)},
                  *{f"J2{n}.{4 + b}" for n in range(N_SLOTS) for b in range(3) if (n >> b) & 1}},
}

if __name__ == "__main__":
    main()
