"""Generate the phase3-manager KiCad project (docs/09 s.3).

ESP32-S3-WROOM-1-N8R2 manager: CAN, USB-C (data only), ILI9341 display
header, EC11 encoder, TCA9535 (8 PRESENT + 8 keys), buzzer, E-stop
kill/sense. Power = vetted LMR36015 -> 5V0 -> NCP1117 -> 3V3 chain.
Single ground domain (PGND, shared with the backplane).

Stock symbols used were pin-verified against local datasheets:
RF_Module:ESP32-S3-WROOM-1 (41/41 pins vs esp32-s3-wroom-1.pdf 3.1),
Interface_Expansion:TCA9535PWR (vs tca9535.pdf Table 5-1);
labbench:TPD2E001DRL is synthesized from tpd2e001.pdf.

Run:  python3 gen_manager.py   (from tools/, writes into the parent dir)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
import kicad_gen as kg          # noqa: E402

LIB = os.path.join(HERE, "..", "..", "phase1-module", "lib")   # shared project lib
kg.add_lib_dir(LIB)

PROJECT = "phase3-manager"
OUT = os.path.join(HERE, "..")
ROOT_UUID = "b52e91a7-1c44-4a30-b6f2-91c4e8d50001"
SHEETS = [
    ("power-can", "b52e91a7-1c44-4a30-b6f2-91c4e8d50010", "2"),
    ("mcu",       "b52e91a7-1c44-4a30-b6f2-91c4e8d50011", "3"),
    ("ui",        "b52e91a7-1c44-4a30-b6f2-91c4e8d50012", "4"),
]

R_FP = "Resistor_SMD:R_0603_1608Metric"
C_FP = "Capacitor_SMD:C_0603_1608Metric"
C_BULK = "Capacitor_SMD:C_1210_3225Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
BTN_FP = "Button_Switch_SMD:SW_SPST_TL3342"


def _sheet(name):
    path = f"/{ROOT_UUID}/{dict((n, u) for n, u, _ in SHEETS)[name]}"
    sh = kg.Sheet(PROJECT, path)

    def res(ref, val, x, y, rot=0, fp=R_FP):
        return sh.add(kg.Placed(kg.get_symbol("Device", "R"), ref, val, x, y, rot, footprint=fp))

    def cap(ref, val, x, y, rot=0, fp=C_FP):
        return sh.add(kg.Placed(kg.get_symbol("Device", "C"), ref, val, x, y, rot, footprint=fp))

    def gl(net, part, pin, shape="passive"):
        sh.glabel(net, part.pin_pos(pin), rot=part.label_rot(pin), shape=shape)

    def ll(net, part, pin):
        sh.label(net, part.pin_pos(pin), rot=part.label_rot(pin))

    return sh, res, cap, gl, ll


def build_power_can():
    sh, res, cap, gl, ll = _sheet("power-can")
    C20P = kg.get_symbol("Connector_Generic", "Conn_01x20")
    FUSE = kg.get_symbol("Device", "Fuse")
    TVS = kg.get_symbol("Device", "D_TVS")
    U8S = kg.get_symbol("labbench", "LMR36015AQRNXRQ1")
    U9S = kg.get_symbol("Regulator_Linear", "NCP1117-3.3_SOT223")
    L = kg.get_symbol("Device", "L")
    CAN = kg.get_symbol("labbench", "TCAN1042HGVDR")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")

    # ---- backplane connector (pinout mirrors gen_backplane J1) ------------
    j1 = sh.add(kg.Placed(C20P, "J1", "BACKPLANE", 33.02, 111.76,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x20_P2.54mm_Vertical"))
    ll("VBUS", j1, 1)
    ll("VBUS", j1, 2)
    for p in ("3", "4", "5", "6"):
        sh.power("PGND", *j1.pin_pos(p), ground=True)
    gl("CAN_H", j1, 7)
    gl("CAN_L", j1, 8)
    gl("HW_EN", j1, 9)
    sh.power("3V3", *j1.pin_pos(10))                # manager SOURCES this rail
    gl("I2C_SDA", j1, 11)
    gl("I2C_SCL", j1, 12)
    # manager owns the bus pull-ups (docs/09 s.3) - the backplane INA228 and
    # the TCA9535 both hang off this pair
    r62 = res("R62", "4.7K", 55.88, 137.16)
    r63 = res("R63", "4.7K", 68.58, 137.16)
    sh.power("3V3", *r62.pin_pos(1))
    sh.power("3V3", *r63.pin_pos(1))
    gl("I2C_SCL", r62, 2)
    gl("I2C_SDA", r63, 2)
    for n in range(8):
        gl(f"PRESENT{n}", j1, str(13 + n), shape="input")

    # ---- input protection + aux rails (vetted Phase-1 chain, single GND) --
    f1 = sh.add(kg.Placed(FUSE, "F1", "2A mini blade", 63.5, 55.88, rot=90,
                          footprint="Fuse:Fuse_Blade_Mini_directSolder"))
    ll("VBUS", f1, 1)
    ll("VBUS_F", f1, 2)
    d5 = sh.add(kg.Placed(TVS, "D5", "SMBJ33A", 78.74, 68.58,
                          footprint="Diode_SMD:D_SMB"))
    ll("VBUS_F", d5, 1)
    sh.power("PGND", *d5.pin_pos(2), ground=True)

    u8 = sh.add(kg.Placed(U8S, "U8", "LMR36015AQRNXRQ1", 116.84, 78.74,
                          footprint="labbench:LMR36015_RNX_VQFN-HR-12"))
    for p in ("2", "10", "9"):                      # VIN x2 + EN tied to VIN
        ll("VBUS_F", u8, p)
    for p in ("1", "11", "6"):
        sh.power("PGND", *u8.pin_pos(p), ground=True)
    c50 = cap("C50", "4.7u/50V", 88.9, 83.82, fp=C_BULK)
    c51 = cap("C51", "4.7u/50V", 99.06, 83.82, fp=C_BULK)
    for c in (c50, c51):
        ll("VBUS_F", c, 1)
        sh.power("PGND", *c.pin_pos(2), ground=True)
    ll("SW_AUX", u8, 12)
    sh.no_connect(u8.pin_pos(3))
    c52 = cap("C52", "100n", 139.7, 63.5, rot=90)
    ll("AUX_BOOT", c52, 1)
    ll("SW_AUX", c52, 2)
    ll("AUX_BOOT", u8, 4)
    c53 = cap("C53", "1u", 96.52, 99.06)
    ll("AUX_VCC", u8, 5)
    ll("AUX_VCC", c53, 1)
    sh.power("PGND", *c53.pin_pos(2), ground=True)
    l2 = sh.add(kg.Placed(L, "L2", "33u/1.2A", 153.67, 91.44, rot=90,
                          footprint="Inductor_SMD:L_1210_3225Metric"))
    ll("SW_AUX", l2, 1)
    sh.power("5V0", *l2.pin_pos(2))
    r50 = res("R50", "100K 1%", 167.64, 88.9)
    r51 = res("R51", "24.9K 1%", 167.64, 104.14)
    sh.power("5V0", *r50.pin_pos(1))
    ll("AUX_FB", r50, 2)
    ll("AUX_FB", r51, 1)
    ll("AUX_FB", u8, 7)
    sh.power("PGND", *r51.pin_pos(2), ground=True)
    for i in range(2):
        c = cap(f"C5{4+i}", "22u/16V", 181.61 + 10.16 * i, 88.9, fp=C_BULK)
        sh.power("5V0", *c.pin_pos(1))
        sh.power("PGND", *c.pin_pos(2), ground=True)
    r52 = res("R52", "100K", 137.16, 99.06)
    gl("AUX_PG", u8, 8, shape="output")
    gl("AUX_PG", r52, 2)
    sh.power("3V3", *r52.pin_pos(1))

    u9 = sh.add(kg.Placed(U9S, "U9", "NCP1117-3.3", 218.44, 78.74,
                          footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2"))
    sh.power("5V0", *u9.pin_pos(3))
    sh.power("3V3", *u9.pin_pos(2))
    sh.power("PGND", *u9.pin_pos(1), ground=True)
    c56 = cap("C56", "10u/16V", 204.47, 88.9, fp=C_BULK)
    sh.power("5V0", *c56.pin_pos(1))
    sh.power("PGND", *c56.pin_pos(2), ground=True)
    c57 = cap("C57", "22u/10V", 234.95, 88.9, fp=C_BULK)
    sh.power("3V3", *c57.pin_pos(1))
    sh.power("PGND", *c57.pin_pos(2), ground=True)

    # ---- CAN transceiver (stub on the backplane bus, no termination) ------
    u11 = sh.add(kg.Placed(CAN, "U11", "TCAN1042HGV", 116.84, 152.4,
                           footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"))
    gl("CAN_TX", u11, 1, shape="input")
    gl("CAN_RX", u11, 4, shape="output")
    sh.power("5V0", *u11.pin_pos(3))
    sh.power("3V3", *u11.pin_pos(5))                # VIO
    sh.power("PGND", *u11.pin_pos(2), ground=True)
    gl("CAN_H", u11, 7)
    gl("CAN_L", u11, 6)
    gl("CAN_STB", u11, 8, shape="input")
    r64 = res("R64", "10K", 88.9, 157.48)
    gl("CAN_STB", r64, 1)
    sh.power("PGND", *r64.pin_pos(2), ground=True)
    c69 = cap("C69", "100n", 96.52, 170.18)
    sh.power("5V0", *c69.pin_pos(1))
    sh.power("PGND", *c69.pin_pos(2), ground=True)
    c70 = cap("C70", "100n", 109.22, 170.18)
    sh.power("3V3", *c70.pin_pos(1))
    sh.power("PGND", *c70.pin_pos(2), ground=True)

    # ---- E-stop assert (open-drain onto HW_EN); sense is on the mcu sheet -
    q8 = sh.add(kg.Placed(Q2N, "Q8", "2N7002", 165.1, 152.4, footprint=SOT23))
    gl("HW_KILL", q8, 1, shape="input")
    sh.power("PGND", *q8.pin_pos(2), ground=True)
    gl("HW_EN", q8, 3)
    r71 = res("R71", "100K", 180.34, 165.1)
    gl("HW_KILL", r71, 1)
    sh.power("PGND", *r71.pin_pos(2), ground=True)

    fl = sh.pwr_flag(226.06, 152.4)
    sh.power("PGND", *fl.pin_pos(1), ground=True)
    fl = sh.pwr_flag(241.3, 152.4)
    sh.label("VBUS", fl.pin_pos(1))
    fl = sh.pwr_flag(256.54, 152.4)
    sh.label("VBUS_F", fl.pin_pos(1))

    sh.text("POWER + CAN (docs/09 s.3): bus tap through 2A mini fuse -> LMR36015 -> 5V0 ->\\n"
            "NCP1117 -> 3V3 (vetted Phase-1 chain, single ground). 3V3 feeds the backplane\\n"
            "E-stop pull-up via J1.10: unplugged manager = all modules SAFE. Q8 = manager\\n"
            "E-stop assert (open-drain); no CAN termination here (backplane owns both ends).",
            25.4, 33.02)
    return sh


def build_mcu():
    sh, res, cap, gl, ll = _sheet("mcu")
    ESP = kg.get_symbol("RF_Module", "ESP32-S3-WROOM-1")
    USBC = kg.get_symbol("Connector", "USB_C_Receptacle")
    ESD = kg.get_symbol("labbench", "TPD2E001DRL")
    SW = kg.get_symbol("Switch", "SW_Push")
    C3P = kg.get_symbol("Connector_Generic", "Conn_01x03")

    u10 = sh.add(kg.Placed(ESP, "U10", "ESP32-S3-WROOM-1-N8R2", 88.9, 111.76,
                           footprint="RF_Module:ESP32-S3-WROOM-1"))
    # power + EP
    for p in ("1", "40", "41"):
        sh.power("PGND", *u10.pin_pos(p), ground=True)
    sh.power("3V3", *u10.pin_pos(2))
    c64 = cap("C64", "10u", 33.02, 172.72, fp=C_BULK)
    c65 = cap("C65", "100n", 45.72, 172.72)
    for c in (c64, c65):
        sh.power("3V3", *c.pin_pos(1))
        sh.power("PGND", *c.pin_pos(2), ground=True)
    # EN reset circuit (Espressif guideline: 10k pull-up + 1u + button)
    r65 = res("R65", "10K", 27.94, 55.88)
    sh.power("3V3", *r65.pin_pos(1))
    ll("ESP_EN", r65, 2)
    ll("ESP_EN", u10, 3)
    c68 = cap("C68", "1u", 40.64, 60.96)
    ll("ESP_EN", c68, 1)
    sh.power("PGND", *c68.pin_pos(2), ground=True)
    sw1 = sh.add(kg.Placed(SW, "SW1", "RESET", 53.34, 55.88, footprint=BTN_FP))
    ll("ESP_EN", sw1, 1)
    sh.power("PGND", *sw1.pin_pos(2), ground=True)
    # IO0 boot strap + button
    r66 = res("R66", "10K", 66.04, 55.88)
    sh.power("3V3", *r66.pin_pos(1))
    ll("BOOT0", r66, 2)
    ll("BOOT0", u10, 27)
    sw2 = sh.add(kg.Placed(SW, "SW2", "BOOT", 78.74, 55.88, footprint=BTN_FP))
    ll("BOOT0", sw2, 1)
    sh.power("PGND", *sw2.pin_pos(2), ground=True)
    # function pins (module pin numbers per verified table, docs/09 s.3)
    gl("CAN_TX", u10, 4, shape="output")            # IO4
    gl("CAN_RX", u10, 5, shape="input")             # IO5
    gl("CAN_STB", u10, 6, shape="output")           # IO6
    gl("EXP_INT", u10, 7, shape="input")            # IO7
    gl("LCD_RST", u10, 8, shape="output")           # IO15
    gl("LCD_BL", u10, 9, shape="output")            # IO16
    gl("TOUCH_CS", u10, 10, shape="output")         # IO17
    gl("TOUCH_IRQ", u10, 11, shape="input")         # IO18
    gl("I2C_SDA", u10, 12)                          # IO8
    gl("USB_DN", u10, 13)                           # IO19
    gl("USB_DP", u10, 14)                           # IO20
    gl("I2C_SCL", u10, 17)                          # IO9
    gl("LCD_CS", u10, 18, shape="output")           # IO10
    gl("LCD_MOSI", u10, 19, shape="output")         # IO11
    gl("LCD_SCK", u10, 20, shape="output")          # IO12
    gl("LCD_MISO", u10, 21, shape="input")          # IO13
    gl("LCD_DC", u10, 22, shape="output")           # IO14
    gl("HW_KILL", u10, 23, shape="output")          # IO21
    gl("ENC_A", u10, 28, shape="input")             # IO35
    gl("ENC_B", u10, 29, shape="input")             # IO36
    gl("ENC_SW", u10, 30, shape="input")            # IO37
    gl("HW_EN", u10, 31, shape="input")             # IO38 sense (3.3V domain)
    gl("LED_STAT", u10, 32, shape="output")         # IO39
    gl("LED_CAN", u10, 33, shape="output")          # IO40
    gl("BUZZ", u10, 34, shape="output")             # IO41
    gl("AUX_PG", u10, 35, shape="input")            # IO42
    gl("UART_RX", u10, 36, shape="input")           # RXD0
    gl("UART_TX", u10, 37, shape="output")          # TXD0
    # straps + spares left alone (docs/09: no repurposing in v1)
    for p in ("15", "16", "24", "25", "26", "38", "39"):
        sh.no_connect(u10.pin_pos(p))

    # ---- USB-C, data only (docs/09: no VBUS power path by design) ---------
    j3 = sh.add(kg.Placed(USBC, "J3", "USB-C", 190.5, 96.52,
                          footprint="Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal"))
    for p in ("A1", "B1", "A12", "B12", "S1"):
        sh.power("PGND", *j3.pin_pos(p), ground=True)
    for p in ("A4", "B4", "A9", "B9"):
        ll("USB_VBUS", j3, p)                       # test point only
    r67 = res("R67", "5.1K", 215.9, 60.96)
    r68 = res("R68", "5.1K", 228.6, 60.96)
    ll("USB_CC1", j3, "A5")
    ll("USB_CC1", r67, 1)
    sh.power("PGND", *r67.pin_pos(2), ground=True)
    ll("USB_CC2", j3, "B5")
    ll("USB_CC2", r68, 1)
    sh.power("PGND", *r68.pin_pos(2), ground=True)
    for p in ("A6", "B6"):
        gl("USB_DP", j3, p)
    for p in ("A7", "B7"):
        gl("USB_DN", j3, p)
    for p in ("A2", "A3", "A10", "A11", "B2", "B3", "B10", "B11", "A8", "B8"):
        sh.no_connect(j3.pin_pos(p))                # SS + SBU absent on 16P fp
    u12 = sh.add(kg.Placed(ESD, "U12", "TPD2E001", 190.5, 152.4,
                           footprint="Package_TO_SOT_SMD:Texas_R-PDSO-N5_DRL-5"))
    gl("USB_DP", u12, 3)                            # IO1
    gl("USB_DN", u12, 5)                            # IO2
    sh.power("3V3", *u12.pin_pos(1))
    sh.power("PGND", *u12.pin_pos(4), ground=True)
    sh.no_connect(u12.pin_pos(2))
    c66 = cap("C66", "100n", 209.55, 152.4)
    sh.power("3V3", *c66.pin_pos(1))
    sh.power("PGND", *c66.pin_pos(2), ground=True)

    # ---- UART bring-up header (same 3-pin as the modules) -----------------
    j4 = sh.add(kg.Placed(C3P, "J4", "UART", 254.0, 111.76,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"))
    sh.power("PGND", *j4.pin_pos(1), ground=True)
    gl("UART_TX", j4, 2)
    gl("UART_RX", j4, 3)

    sh.text("MCU (docs/09 s.3): ESP32-S3-WROOM-1-N8R2 (quad PSRAM keeps IO35-37). Straps\\n"
            "IO3/IO45/IO46 untouched; IO0 boot + EN reset buttons per Espressif guideline.\\n"
            "USB-C: data only via TPD2E001 clamp; VBUS lands on a test-point net; CC 5.1K\\n"
            "pulldowns advertise UFP. SuperSpeed pins have no pads on the 16P receptacle.",
            25.4, 27.94)
    return sh


def build_ui():
    sh, res, cap, gl, ll = _sheet("ui")
    EXP = kg.get_symbol("Interface_Expansion", "TCA9535PWR")
    ENC = kg.get_symbol("Device", "RotaryEncoder_Switch")
    Q2N = kg.get_symbol("Transistor_FET", "2N7002")
    QP = kg.get_symbol("Device", "Q_PMOS_GSD")
    LED = kg.get_symbol("Device", "LED")
    BUZ = kg.get_symbol("Device", "Buzzer")
    DF = kg.get_symbol("Diode", "1N4148W")
    C9P = kg.get_symbol("Connector_Generic", "Conn_01x09")
    C14P = kg.get_symbol("Connector_Generic", "Conn_01x14")

    # ---- TCA9535: port0 = PRESENT, port1 = keys ---------------------------
    u13 = sh.add(kg.Placed(EXP, "U13", "TCA9535PWR", 63.5, 96.52,
                           footprint="Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm"))
    sh.power("3V3", *u13.pin_pos(24))
    sh.power("PGND", *u13.pin_pos(12), ground=True)
    for p in ("21", "2", "3"):                      # A0/A1/A2 -> 0x20
        sh.power("PGND", *u13.pin_pos(p), ground=True)
    gl("I2C_SCL", u13, 22)
    gl("I2C_SDA", u13, 23)
    gl("EXP_INT", u13, 1, shape="output")
    r72 = res("R72", "10K", 33.02, 55.88)
    sh.power("3V3", *r72.pin_pos(1))
    gl("EXP_INT", r72, 2)
    c73 = cap("C73", "100n", 33.02, 111.76)
    sh.power("3V3", *c73.pin_pos(1))
    sh.power("PGND", *c73.pin_pos(2), ground=True)
    for n in range(8):                              # PRESENT0-7 -> P00-P07
        gl(f"PRESENT{n}", u13, str(4 + n), shape="input")
        rp = res(f"R8{n}", "10K", 99.06 + 10.16 * n, 40.64)
        sh.power("3V3", *rp.pin_pos(1))
        sh.glabel(f"PRESENT{n}", rp.pin_pos(2), rot=rp.label_rot(2))
    for n in range(8):                              # KEY0-7 -> P10-P17
        gl(f"KEY{n}", u13, str(13 + n))
        rk = res(f"R9{n}", "10K", 99.06 + 10.16 * n, 60.96)
        sh.power("3V3", *rk.pin_pos(1))
        sh.glabel(f"KEY{n}", rk.pin_pos(2), rot=rk.label_rot(2))
    j5 = sh.add(kg.Placed(C9P, "J5", "PANEL KEYS", 33.02, 152.4,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical"))
    for n in range(8):
        gl(f"KEY{n}", j5, str(1 + n))
    sh.power("PGND", *j5.pin_pos(9), ground=True)

    # ---- display module header (generic ILI9341+XPT2046 pinout) -----------
    j6 = sh.add(kg.Placed(C14P, "J6", "ILI9341 LCD MODULE", 218.44, 96.52,
                          footprint="Connector_PinHeader_2.54mm:PinHeader_1x14_P2.54mm_Vertical"))
    sh.power("3V3", *j6.pin_pos(1))                 # VCC (module regulator bypassed)
    sh.power("PGND", *j6.pin_pos(2), ground=True)
    gl("LCD_CS", j6, 3)
    gl("LCD_RST", j6, 4)
    gl("LCD_DC", j6, 5)
    gl("LCD_MOSI", j6, 6)
    gl("LCD_SCK", j6, 7)
    ll("LCD_LED", j6, 8)
    gl("LCD_MISO", j6, 9)
    gl("LCD_SCK", j6, 10)                           # T_CLK shares SPI
    gl("TOUCH_CS", j6, 11)
    gl("LCD_MOSI", j6, 12)                          # T_DIN
    gl("LCD_MISO", j6, 13)                          # T_DO
    gl("TOUCH_IRQ", j6, 14)
    # backlight high-side switch: GPIO -> 2N7002 -> P-FET from 3V3
    q10 = sh.add(kg.Placed(Q2N, "Q10", "2N7002", 172.72, 137.16, footprint=SOT23))
    gl("LCD_BL", q10, 1, shape="input")
    sh.power("PGND", *q10.pin_pos(2), ground=True)
    ll("BL_G", q10, 3)
    r73 = res("R73", "100K", 172.72, 116.84, rot=90)
    sh.power("3V3", *r73.pin_pos(2))
    ll("BL_G", r73, 1)
    q11 = sh.add(kg.Placed(QP, "Q11", "AO3401A-class PMOS", 190.5, 121.92, footprint=SOT23))
    ll("BL_G", q11, 1)                              # G
    sh.power("3V3", *q11.pin_pos(2))                # S
    ll("LCD_LED", q11, 3)                           # D

    # ---- encoder with RC conditioning (bench values) ----------------------
    enc = sh.add(kg.Placed(ENC, "ENC1", "EC11", 63.5, 172.72,
                           footprint="Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm"))
    sh.power("PGND", *enc.pin_pos("C"), ground=True)
    sh.power("PGND", *enc.pin_pos("S2"), ground=True)
    for chan, pin in (("A", "A"), ("B", "B")):
        rp = res(f"R7{5 if chan == 'A' else 6}", "10K", 88.9 + (0 if chan == "A" else 25.4), 152.4)
        rs = res(f"R7{7 if chan == 'A' else 8}", "10K", 88.9 + (0 if chan == "A" else 25.4), 172.72, rot=90)
        cf = cap(f"C7{4 if chan == 'A' else 5}", "100n", 101.6 + (0 if chan == "A" else 25.4), 186.69)
        sh.power("3V3", *rp.pin_pos(1))
        sh.label(f"ENC_{chan}_RAW", rp.pin_pos(2), rot=rp.label_rot(2))
        sh.label(f"ENC_{chan}_RAW", enc.pin_pos(pin), rot=enc.label_rot(pin))
        sh.label(f"ENC_{chan}_RAW", rs.pin_pos(1), rot=rs.label_rot(1))
        sh.glabel(f"ENC_{chan}", rs.pin_pos(2), rot=rs.label_rot(2))
        sh.glabel(f"ENC_{chan}", cf.pin_pos(1), rot=cf.label_rot(1))
        sh.power("PGND", *cf.pin_pos(2), ground=True)
    r79 = res("R79", "10K", 139.7, 152.4)
    c76 = cap("C76", "100n", 152.4, 186.69)
    sh.power("3V3", *r79.pin_pos(1))
    gl("ENC_SW", r79, 2)
    gl("ENC_SW", enc, "S1")
    gl("ENC_SW", c76, 1)
    sh.power("PGND", *c76.pin_pos(2), ground=True)

    # ---- status LEDs + buzzer ---------------------------------------------
    for i, net in enumerate(("LED_STAT", "LED_CAN")):
        d = sh.add(kg.Placed(LED, f"D{7+i}", net, 218.44 + 12.7 * i, 152.4, rot=90,
                             footprint="LED_SMD:LED_0603_1608Metric"))
        r = res(f"R{69+i}", "1K", 218.44 + 12.7 * i, 137.16, rot=90)
        sh.power("3V3", *r.pin_pos(2))
        sh.label(f"{net}_A", r.pin_pos(1), rot=r.label_rot(1))
        sh.label(f"{net}_A", d.pin_pos(2), rot=d.label_rot(2))
        sh.glabel(net, d.pin_pos(1), rot=d.label_rot(1))   # GPIO sinks
    bz = sh.add(kg.Placed(BUZ, "BZ1", "MLT-8530", 254.0, 137.16,
                          footprint="labbench:MLT-8530"))
    sh.power("5V0", *bz.pin_pos(1))
    ll("BUZZ_N", bz, 2)
    d9 = sh.add(kg.Placed(DF, "D9", "1N4148W", 266.7, 137.16, rot=90,
                          footprint="Diode_SMD:D_SOD-323"))
    sh.power("5V0", *d9.pin_pos(1))                 # K to rail (flyback)
    ll("BUZZ_N", d9, 2)
    q9 = sh.add(kg.Placed(Q2N, "Q9", "2N7002", 254.0, 165.1, footprint=SOT23))
    gl("BUZZ", q9, 1, shape="input")
    sh.power("PGND", *q9.pin_pos(2), ground=True)
    ll("BUZZ_N", q9, 3)
    r98 = res("R98", "100K", 241.3, 177.8)
    gl("BUZZ", r98, 1)
    sh.power("PGND", *r98.pin_pos(2), ground=True)

    sh.text("UI (docs/09 s.3): TCA9535 (0x20) - port0 PRESENT, port1 panel keys, 16x 10K\\n"
            "pull-ups (part has none). Display: generic ILI9341+XPT2046 14-pin module on\\n"
            "3V3 VCC; backlight switched HIGH-side (50-120mA, beyond a GPIO). EC11 with RC\\n"
            "conditioning (bench). LEDs sink like the module board; buzzer low-side + flyback.",
            25.4, 27.94)
    return sh


BUILDERS = {"power-can": build_power_can, "mcu": build_mcu, "ui": build_ui}


def build_root():
    sh = kg.Sheet(PROJECT, "/")
    sh.uuid = ROOT_UUID
    x = 38.1
    for name, su, page in SHEETS:
        sh.items.append(f"""  (sheet (at {x} 38.1) (size 38.1 15.24) (fields_autoplaced)
    (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0))
    (uuid {su})
    (property "Sheetname" "{name}" (at {x} 37.3 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
    (property "Sheetfile" "{name}.kicad_sch" (at {x} 53.94 0) (effects (font (size 1.27 1.27)) (justify left top)))
    (instances (project "{PROJECT}" (path "/{ROOT_UUID}" (page "{page}"))))
  )""")
        x += 50.8
    sh.text("Lab_Bench phase-3 manager - ESP32-S3 rack controller (docs/09).\\n"
            "Generated schematic; run tools/gen_manager.py, never hand-edit.", 38.1, 88.9)
    return sh


def main():
    root = build_root()
    open(os.path.join(OUT, f"{PROJECT}.kicad_sch"), "w").write(root.emit())
    for name, _, _ in SHEETS:
        open(os.path.join(OUT, f"{name}.kicad_sch"), "w").write(BUILDERS[name]().emit())
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


EXPECTED_NETS = {
    # -- power-can
    "VBUS":      {"J1.1", "J1.2", "F1.1"},
    "VBUS_F":    {"F1.2", "D5.1", "U8.2", "U8.10", "U8.9", "C50.1", "C51.1"},
    "SW_AUX":    {"U8.12", "L2.1", "C52.2"},
    "AUX_BOOT":  {"U8.4", "C52.1"},
    "AUX_VCC":   {"U8.5", "C53.1"},
    "AUX_FB":    {"U8.7", "R50.2", "R51.1"},
    "AUX_PG":    {"U8.8", "R52.2", "U10.35"},
    "CAN_TX":    {"U10.4", "U11.1"},
    "CAN_RX":    {"U10.5", "U11.4"},
    "CAN_STB":   {"U10.6", "U11.8", "R64.1"},
    "CAN_H":     {"U11.7", "J1.7"},
    "CAN_L":     {"U11.6", "J1.8"},
    "HW_EN":     {"J1.9", "Q8.3", "U10.31"},
    "HW_KILL":   {"U10.23", "Q8.1", "R71.1"},
    "I2C_SDA":   {"J1.11", "U10.12", "U13.23", "R63.2"},
    "I2C_SCL":   {"J1.12", "U10.17", "U13.22", "R62.2"},
    # -- mcu
    "ESP_EN":    {"U10.3", "R65.2", "C68.1", "SW1.1"},
    "BOOT0":     {"U10.27", "R66.2", "SW2.1"},
    "UART_TX":   {"U10.37", "J4.2"},
    "UART_RX":   {"U10.36", "J4.3"},
    "USB_DP":    {"U10.14", "J3.A6", "J3.B6", "U12.3"},
    "USB_DN":    {"U10.13", "J3.A7", "J3.B7", "U12.5"},
    "USB_VBUS":  {"J3.A4", "J3.B4", "J3.A9", "J3.B9"},
    "USB_CC1":   {"J3.A5", "R67.1"},
    "USB_CC2":   {"J3.B5", "R68.1"},
    "EXP_INT":   {"U13.1", "R72.2", "U10.7"},
    # -- ui: expander ports
    **{f"PRESENT{n}": {"J1." + str(13 + n), f"U13.{4 + n}", f"R8{n}.2"} for n in range(8)},
    **{f"KEY{n}": {f"U13.{13 + n}", f"R9{n}.2", f"J5.{1 + n}"} for n in range(8)},
    # -- ui: display / backlight / encoder / indicators
    "LCD_CS":    {"U10.18", "J6.3"},
    "LCD_RST":   {"U10.8", "J6.4"},
    "LCD_DC":    {"U10.22", "J6.5"},
    "LCD_MOSI":  {"U10.19", "J6.6", "J6.12"},
    "LCD_SCK":   {"U10.20", "J6.7", "J6.10"},
    "LCD_MISO":  {"U10.21", "J6.9", "J6.13"},
    "TOUCH_CS":  {"U10.10", "J6.11"},
    "TOUCH_IRQ": {"U10.11", "J6.14"},
    "LCD_BL":    {"U10.9", "Q10.1"},
    "BL_G":      {"Q10.3", "R73.1", "Q11.1"},
    "LCD_LED":   {"Q11.3", "J6.8"},
    "ENC_A_RAW": {"ENC1.A", "R75.2", "R77.1"},
    "ENC_B_RAW": {"ENC1.B", "R76.2", "R78.1"},
    "ENC_A":     {"R77.2", "C74.1", "U10.28"},
    "ENC_B":     {"R78.2", "C75.1", "U10.29"},
    "ENC_SW":    {"ENC1.S1", "R79.2", "C76.1", "U10.30"},
    "LED_STAT_A": {"R69.1", "D7.2"},
    "LED_STAT":  {"D7.1", "U10.32"},
    "LED_CAN_A": {"R70.1", "D8.2"},
    "LED_CAN":   {"D8.1", "U10.33"},
    "BUZZ":      {"U10.34", "Q9.1", "R98.1"},
    "BUZZ_N":    {"BZ1.2", "D9.2", "Q9.3"},
    # -- rails (superset)
    "~3V3":      {"J1.10", "R52.1", "R62.1", "R63.1", "U9.2", "C57.1", "U11.5", "C70.1",
                  "U10.2", "C64.1", "C65.1", "R65.1", "R66.1", "U12.1", "C66.1",
                  "U13.24", "C73.1", "R72.1", "J6.1", "R73.2", "Q11.2",
                  "R75.1", "R76.1", "R79.1", "R69.2", "R70.2",
                  *{f"R8{n}.1" for n in range(8)}, *{f"R9{n}.1" for n in range(8)}},
    "~5V0":      {"L2.2", "C54.1", "C55.1", "U9.3", "C56.1", "R50.1",
                  "U11.3", "C69.1", "BZ1.1", "D9.1"},
    "~PGND":     {"J1.3", "J1.4", "J1.5", "J1.6", "D5.2", "U8.1", "U8.6", "U8.11",
                  "C50.2", "C51.2", "C53.2", "C54.2", "C55.2", "R51.2", "U9.1",
                  "C56.2", "C57.2", "U11.2", "C69.2", "C70.2", "R64.2", "Q8.2",
                  "R71.2", "U10.1", "U10.40", "U10.41", "C64.2", "C65.2", "C68.2",
                  "SW1.2", "SW2.2", "J3.A1", "J3.B1", "J3.A12", "J3.B12", "J3.S1",
                  "R67.2", "R68.2", "U12.4", "C66.2", "J4.1",
                  "U13.12", "U13.21", "U13.2", "U13.3", "C73.2", "J5.9",
                  "Q10.2", "ENC1.C", "ENC1.S2", "C74.2", "C75.2", "C76.2",
                  "Q9.2", "R98.2"},
}

if __name__ == "__main__":
    main()
