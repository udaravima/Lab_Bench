"""LCSC part assignments, transcribed from hardware/SOURCING.md (2026-07-18 pass).

Every row names the exact references it applies to on each board, so nothing
is matched by guesswork on the Value string. Only parts SOURCING.md verified
get an LCSC number; everything else (generic R/C, jellybeans, pin headers)
stays blank in the BOM until it is chosen at order time.

Section D was picked from the JLCPCB catalogue on 2026-09-27 (stock checked
that day), preferring Basic parts.

Row: (boards -> refs, LCSC, MPN, manufacturer, USD qty-1, note)
`boards` maps a board directory name to a list of references.
A note starting with "CHECK" is a mismatch a human must resolve before
ordering (footprint or variant differs from what SOURCING.md picked).
"""

P1, P2, BP, MGR = ("phase1-module", "phase2-module",
                   "phase3-backplane", "phase3-manager")

PARTS = [
    # ---- A. Semiconductors -------------------------------------------------
    ({P2: ["U3"]}, "C5219258", "LM5143QRHARQ1", "TI", 6.29,
     "symbol value says LM5143RHAR; this is the LM5143A-Q1 (TI ZHCSQC8, "
     "2022). Same 40-pin map and the same land: RHA0040N vs RHA0040P is "
     "6x6 body, 0.5 pitch, 0.25x0.6 pads at 5.8 span, EP 3.3 +-0.1 in both; "
     "the Q1 part only adds wettable flanks (checked 2026-10-06)"),
    ({P2: ["U12"]}, "C111822", "LM5069MM-2/NOPB", "TI", 1.17, ""),
    ({P2: ["Q1", "Q2", "Q3", "Q4", "Q10", "Q11", "Q12", "Q13"]},
     "C86513", "CSD18540Q5B", "TI", 1.43,
     "do not substitute clone power-stage FETs"),
    ({P2: ["Q14"]}, "C2687963", "CSD19536KTT", "TI", 4.94,
     "hot-swap pass FET, SOA-critical, thin stock - order early"),
    ({P1: ["U10"], P2: ["U10"]}, "C529355", "STM32G431CBT6", "ST", 2.85, ""),
    ({P1: ["U1"], P2: ["U1"]}, "C1880990", "DAC80502DRXR", "TI", 4.19,
     "value says DRXT; R/T differ only in reel size"),
    ({P1: ["U5"], P2: ["U5"], BP: ["U1"]}, "C5214669", "INA228AQDGSRQ1", "TI", 17.16,
     "automotive grade of INA228AIDGSR, same VSSOP-10 pinout and register "
     "map (no firmware change); the AIDGSR (C2887910) was still out of stock "
     "on 2026-09-28 - swap back if it returns, it is about a quarter of the price. "
     "Only 5 in stock on 2026-10-06: order early"),
    ({P1: ["U4"], P2: ["U4"]}, "C2060584", "INA240A3DR", "TI", 1.87, ""),
    ({P1: ["U2"], P2: ["U2"]}, "C19608", "OPA2333AIDGKR", "TI", 1.14, ""),
    ({P1: ["U11"], P2: ["U11"], MGR: ["U11"]},
     "C485806", "TCAN1042VDRQ1", "TI", 0.57,
     "symbol value says TCAN1042HGV; SOURCING picked the V (VIO) variant, "
     "same SOIC-8 pinout"),
    ({P1: ["U8"], P2: ["U8"], MGR: ["U8"]},
     "C1850345", "LMR36015ARNXR", "TI", 1.91,
     "symbol value says LMR36015AQRNXRQ1 (automotive); SOURCING picked the "
     "commercial ARNXR, same RNX package"),
    ({P1: ["U9"], P2: ["U9"], MGR: ["U9"]},
     "C26537", "NCP1117ST33T3G", "onsemi", 0.21, ""),
    ({P1: ["U6"], P2: ["U6"]}, "C690105", "LTC7004EMSE#PBF", "ADI", 11.62,
     "thin stock (25 on 2026-10-06) - order early (IMSE fallback)"),
    ({P1: ["U7"], P2: ["U7"]}, "C193688", "TLV7011DCKR", "TI", 0.27,
     "SC-70-5 (DCK)"),
    ({P2: ["D8"]}, "C41283", "TL431BIDBZR", "TI", 0.054, ""),
    ({P2: ["U13"]}, "C353035", "TS5A3166DBVR", "TI", 0.28, ""),
    ({MGR: ["U13"]}, "C130204", "TCA9535PWR", "TI", 0.44,
     "UMW clone acceptable here"),
    ({MGR: ["U10"]}, "C2913204", "ESP32-S3-WROOM-1-N8R2", "Espressif", 5.01, ""),
    ({MGR: ["U12"]}, "C150526", "TPD2E001DRLR", "TI", 0.16, ""),
    ({P1: ["U3"]}, "C485912", "LM5145RGYR", "TI", 1.55, ""),
    ({P1: ["Q1", "Q2", "Q3", "Q4"]}, "C179626", "NTMFS5C670NLT1G", "onsemi",
     0.49,
     "stands in for CSD18563Q5A (C77239, still out of stock 2026-10-06). "
     "60 V, 6.1 mOhm, Qg 20 nC vs 5.7 mOhm / 15 nC; same S-S-S-G / drain-tab "
     "pinout. Overlay on the TI Q5A land checked against case 488AA: "
     "terminals within 0.14 mm of the TI part's (E 6.15 vs 6.00, L 0.575 vs "
     "0.61, K 1.35 vs 1.10), 0.35 mm from the drain land edge vs 0.24 for "
     "the TI part. Q3/Q4 dissipate about 0.6 W each at 10 A"),

    # ---- B. Magnetics & power passives ------------------------------------
    ({P2: ["L1", "L3"]}, "C6238332", "MWSA1707S-6R8MT", "Sunlord", 1.72,
     "17 A Irms / 22 A Isat; L_1707_XAL1510 superset land (also takes the XAL1510 spares)"),
    ({P1: ["L1"]}, "C5240401", "MWSA1707S-100MT", "Sunlord", 1.68,
     "16.5 A Isat / 10.5 A Irms; L_1707_XAL1510 superset land"),
    ({P2: ["R36", "R37", "R42", "R57"]}, "C49837985", "", "", 0.025,
     "7.5 mOhm 1206 1 W 1 %, phase-shunt pairs"),
    ({P2: ["R30", "R34"]}, "C46634444", "", "", 0.058,
     "1.0 mOhm 2512 3 W 1 % output shunt; check TCR <= 75 ppm on datasheet"),
    ({P2: ["R70"]}, "C49837991", "", "", 0.044,
     "1.5 mOhm 2512 3 W 1 %, LM5069 R_SNS"),
    ({P1: ["R30"]}, "C2994640", "", "", 0.060,
     "2 mOhm 2512 3 W 1 %; check TCR on datasheet"),
    ({BP: ["RS1", "RS2"]}, "C466580", "BVS-M-R0005", "Isabellenhuette", 0.60,
     "2 in parallel = 0.25 mOhm; verify power rating on datasheet"),
    ({P2: ["C15", "C16", "C36", "C37"]}, "C454349", "EEHZA1V221P", "Panasonic", 1.42,
     "hybrid polymer D10x10.2 on the CP_Elec_10x10.5 land, 20 mOhm / 2.5 A "
     "at 100 kHz; LCSC stock was 1 on 2026-09-28 - if still short, SUNCON "
     "35HVH220M+P (C179812, D10x12.5, same land) is the stocked alternative"),
    ({P2: ["C14"]}, "C106666", "", "", 0.10, "470 uF 50 V THT radial D10"),
    ({P2: ["C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13",
           "C38", "C40", "C45", "C46", "C47", "C48"]},
     "C126612", "GCM32EC71H106KA03L", "Murata", 0.144, ""),
    ({P1: ["Y1"], P2: ["Y1"]}, "C403948", "TAXM8M4RFDCET2T", "Yajingxin",
     0.147, "8 MHz 3225, CL = 12 pF (load caps 18 p); replaces C400090, "
     "which is the CL = 10 pF version"),

    # ---- C. Connectors & electromechanical --------------------------------
    ({P2: ["J1", "J4"]}, "C98732", "XT60PW-M", "Amass", 0.54, ""),
    ({BP: ["J10", "J11", "J12", "J13", "J14", "J15", "J16", "J17"]},
     "C428722", "XT60PW-F", "Amass", 0.56, ""),
    # 2026-09-28: the board is routed to the USB4105 land, so order that part.
    # LCSC shows 0 stock but JLCPCB assembly holds 1.1k; -120 (C5184243, 4.7k,
    # longer shell stakes) is the backup. TYPE-C-31-M-12 needs a re-route.
    ({MGR: ["J3"]}, "C3020560", "USB4105-GF-A", "Global Connector Technology",
     1.30, "stocked at JLCPCB assembly, not LCSC retail; backup "
     "USB4105-GF-A-120 C5184243"),
    # C2831776 (the old "generic EC11") is a 100 uF/50 V electrolytic, and
    # the MLT-8530 is rated 2.5-4.5 V but hangs off 5V0 - replaced 2026-09-27.
    ({MGR: ["ENC1"]}, "C255515", "EC11E18244A5", "Alps Alpine", 2.40,
     "EC11E with push switch; EasyEDA land A/B/C + D/E switch + 2 lugs "
     "matches the EC11E-Switch footprint"),
    ({MGR: ["BZ1"]}, "C781886", "YX-SMD8530P", "Yuexin", 0.39,
     "5 V-rated (2-5 V) drop-in for the 3.6 V MLT-8530; vendor land "
     "is identical, pad 1 (+) in the same corner"),
    ({P2: ["F1"]}, "C3207132", "", "", 0.42,
     "ATO fuse HOLDER; the 35 A fuse itself is bought separately"),
    # F1's land is Fuse_Blade_Mini_directSolder: the fuse's own blades
    # solder in. C3207114 was a 6.35 mm cylindrical clip, not a holder.
    ({MGR: ["F1"]}, "C151091", "0297002.WXNV", "Littelfuse", 0.11,
     "2 A MINI blade fuse, soldered directly into the land (no holder)"),

    # ---- Deferred picks closed 2026-10-05 (JLCPCB stock checked that day) --
    # No 1210 33 uH is stocked above 0.5 A, so the manager's L2 land grew to
    # the 5x5 mm FNR5040S (board re-routed round it). Datasheet: 33 uH +-20 %,
    # DCR 0.244 ohm max, Isat 1.30 A min / 1.45 A typ, Irms 1.20 A min.
    # Phase-1 and phase-2 L2 had the same 1210 land and moved to the same
    # part on 2026-10-06 (ECO on both routed boards).
    ({MGR: ["L2"], P1: ["L2"], P2: ["L2"]}, "C167973", "FNR5040S330MT", "cjiang (Changjiang Microelectronics)",
     0.06, "5x5x4 mm shielded, KiCad L_Changjiang_FNR5040S land; Isat 1.30 A "
     "min covers the 33u/1.2A value. Any 5040-size 33 uH >=1.2 A part with "
     "the same 2.3 mm pad gap fits"),
    # C2 sits on CP_Elec_16x17.5 (17 x 17 mm platform); 16 x 16.5 cans share
    # that platform and terminal layout, so no board change.
    ({BP: ["C2"]}, "C462700", "UCX1H471MNS1MS", "Nichicon", 1.63,
     "SMD 16x16.5, 50 V, 70 mOhm, 1.0 A ripple at 100 kHz, 135 C rated; "
     "fits the 16x17.5 land. Fallback: Panasonic EEEFK1H471AM (C178551)"),

    # ---- D. Phase-1 passives & small parts (JLCPCB catalogue, 2026-09-27) --
    ({P1: ["C1"]}, "C57112", "0603B103K500NT", "FH", 0.0108,
     ""),
    ({P1: ["C2"]}, "C21122", "CL10B223KB8NNNC", "Samsung Electro-Mechanics", 0.0083,
     ""),
    ({P1: ["C3", "C5", "C27", "C28", "C33", "C34", "C41", "C43", "C52", "C62", "C68", "C69", "C70", "C71", "C72", "C73", "C74"]}, "C14663", "CC0603KRX7R9BB104", "YAGEO", 0.0122,
     ""),
    ({P1: ["C4"]}, "C513735", "CC0603KRX7R9BB154", "YAGEO", 0.013,
     "50 V part (no Basic 150 nF)"),
    ({P1: ["C18"]}, "C1622", "CL10B473KB8NNNC", "Samsung Electro-Mechanics", 0.0073,
     ""),
    ({P1: ["C19"]}, "C1644", "CL10C150JB8NNNC", "Samsung Electro-Mechanics", 0.0113,
     "C0G"),
    ({P1: ["C24"]}, "C1322360", "0603B822K500NT", "FH", 0.0053,
     ""),
    ({P1: ["C25"]}, "C1643", "0603CG121J500NT", "FH", 0.0132,
     "C0G"),
    ({P1: ["C26"]}, "C1613", "CL10B332KB8NNNC", "Samsung Electro-Mechanics", 0.0083,
     ""),
    ({P1: ["C29"]}, "C23630", "CL10A225KO8NNNC", "Samsung Electro-Mechanics", 0.0181,
     "16 V X5R on the 7.5 V VCC rail"),
    ({P1: ["C31", "C32", "C44"]}, "C1588", "CL10B102KB8NNNC", "Samsung Electro-Mechanics", 0.0089,
     ""),
    ({P1: ["C42", "C53", "C65"]}, "C15849", "CL10A105KB8NNNC", "Samsung Electro-Mechanics", 0.0752,
     ""),
    ({P1: ["C64"]}, "C19666", "CL10A475KO8NNNC", "Samsung Electro-Mechanics", 0.0294,
     ""),
    ({P1: ["C66", "C67"]}, "C1647", "CL10C180JB8NNNC", "Samsung Electro-Mechanics", 0.0157,
     "C0G"),
    ({P1: ["C20", "C75", "C76", "C77"]}, "C77102", "GRM32ER71H106KA12L", "Murata Electronics", 0.3274,
     "10 uF 50 V X7R: no 22 uF 50 V 1210 is stocked, so the design value is "
     "now 10u (phase-2 uses 10 uF too). 4 x ~4.5 uF at 30 V bias gives about "
     "0.3 Vpp input ripple at 8 A, D = 0.5, 350 kHz; ~1 A RMS each; C21 is the bulk"),
    ({P1: ["C21"]}, "C2887271", "RVT220UF50V67RV0021", "KNSCHA", 0.1412,
     "SMD D10x10.2 aluminium, fits CP_Elec_10x10.5"),
    ({P1: ["C22", "C78"]}, "C46550471", "MA35V220M8X12", "jieerrui", 0.2872,
     "35 V polymer SMD D8x11.5, 16 mOhm; fits CP_Elec_8x11.9"),
    ({P1: ["C23", "C79", "C80", "C81", "C54", "C55", "C57"]}, "C5341638", "CC1210KKX7R8BB226", "YAGEO", 0.596,
     "22 uF 25 V X7R 1210; the 5V0/3V3 positions (16 V/10 V in the value) get the same part"),
    ({P1: ["C50", "C51"]}, "C596318", "CC1210KKX7R9BB475", "YAGEO", 0.3807,
     ""),
    ({P1: ["C56"]}, "C77102", "GRM32ER71H106KA12L", "Murata Electronics", 0.3274,
     "10 uF 50 V X7R, same part as C20 (value says 16 V)"),
    ({P1: ["D1", "D2", "D3", "D4"]}, "C77328", "BAT54W", "Jiangsu Changjing Electronics Technology Co., Ltd.", 0.0238,
     "SOT-323 single, pin 1 A / pin 3 K / pin 2 NC - check the rotation in the JLCPCB preview"),
    ({P1: ["D5"]}, "C224019", "SMBJ33A", "Littelfuse", 0.122,
     ""),
    ({P1: ["D6"]}, "C2128", "1N4148WS", "Jiangsu Changjing Electronics Technology Co., Ltd.", 0.0158,
     "1N4148WS is the SOD-323 version (1N4148W is SOD-123)"),
    ({P1: ["D7"]}, "C2286", "KT-0603R", "Hubei KENTO Elec", 0.0075,
     "red 0603 LED (Basic)"),
    ({P1: ["Q5", "Q6", "Q7", "Q8", "Q9"]}, "C8545", "2N7002", "Jiangsu Changjing Electronics Technology Co., Ltd.", 0.0178,
     ""),
    ({P1: ["R1"]}, "C861257", "RT0603BRD0725K5L", "YAGEO", 0.0353,
     "0.1 % 25 ppm thin film"),
    ({P1: ["R2"]}, "C110776", "RT0603BRD071KL", "YAGEO", 0.0327,
     "0.1 % 25 ppm thin film"),
    ({P1: ["R3", "R6"]}, "C95204", "RT0603BRD0710KL", "YAGEO", 0.0327,
     "0.1 % 25 ppm thin film"),
    ({P1: ["R32"]}, "C861526", "RT0603BRD0769K8L", "YAGEO", 0.0575,
     "0.1 % 25 ppm thin film"),
    ({P1: ["R33"]}, "C95204", "RT0603BRD0710KL", "YAGEO", 0.0327,
     "0.1 % 25 ppm thin film"),
    ({P1: ["R4"]}, "C4216", "0603WAF3302T5E", "UNI-ROYAL", 0.0022,
     ""),
    ({P1: ["R5", "R8"]}, "C23018", "0603WAF3901T5E", "UNI-ROYAL", 0.0027,
     ""),
    ({P1: ["R7"]}, "C22809", "0603WAF1502T5E", "UNI-ROYAL", 0.0029,
     ""),
    ({P1: ["R16", "R18", "R19", "R22", "R23", "R52", "R20", "R50"]}, "C25803", "0603WAF1003T5E", "UNI-ROYAL", 0.0031,
     ""),
    ({P1: ["R21"]}, "C22797", "0603WAF1302T5E", "UNI-ROYAL", 0.0029,
     ""),
    ({P1: ["R24"]}, "C25981", "0603WAF8201T5E", "UNI-ROYAL", 0.0035,
     ""),
    ({P1: ["R25", "R31", "R66"]}, "C21190", "0603WAF1001T5E", "UNI-ROYAL", 0.0026,
     ""),
    ({P1: ["R26"]}, "C22928", "0603WAF2872T5E", "UNI-ROYAL", 0.0016,
     ""),
    ({P1: ["R27"]}, "C421608", "25121WF2201T4E", "UNI-ROYAL", 0.0541,
     "1 W 2512"),
    ({P1: ["R28"]}, "C227839", "AC0603FR-07365RL", "YAGEO", 0.005,
     ""),
    ({P1: ["R29"]}, "C23164", "0603WAF470KT5E", "UNI-ROYAL", 0.0026,
     ""),
    ({P1: ["R43", "R64", "R65", "R47", "R61", "R67", "R68"]}, "C25804", "0603WAF1002T5E", "UNI-ROYAL", 0.0018,
     ""),
    ({P1: ["R44"]}, "C25819", "0603WAF4702T5E", "UNI-ROYAL", 0.0037,
     ""),
    ({P1: ["R45"]}, "C22883", "0603WAF1583T5E", "UNI-ROYAL", 0.0013,
     ""),
    ({P1: ["R46"]}, "C4184", "0603WAF2002T5E", "UNI-ROYAL", 0.0023,
     ""),
    ({P1: ["R48"]}, "C25967", "0603WAF3162T5E", "UNI-ROYAL", 0.0022,
     ""),
    ({P1: ["R51"]}, "C25962", "0603WAF2492T5E", "UNI-ROYAL", 0.0016,
     ""),
    ({P1: ["R60"]}, "C25811", "0603WAF2003T5E", "UNI-ROYAL", 0.0023,
     ""),
    ({P1: ["R62", "R63"]}, "C23162", "0603WAF4701T5E", "UNI-ROYAL", 0.0028,
     ""),
    ({P1: ["RT1", "RT2"]}, "C2892547", "KNTC0603/10KF3950", "KUU", 0.0298,
     "10k 1 % NTC sold as 3950; the catalogue also lists 3987 K (likely B25/85) - match the firmware B constant"),
]

# Parts with no LCSC number yet that are worth saying why in the BOM.
NOTES = [
    ({P1: ["J1", "J4"]},
     "through-hole, hand-solder; SOURCING lists 2EDG 5.08 plugs C3697 for "
     "P1 bench IO, but this footprint is a 5.0 mm Phoenix PT - pick the "
     "matching header"),
    ({P1: ["F1"]}, "through-hole, hand-solder; the land is KiCad's "
     "direct-solder mini blade pattern, so a 10 A mini blade (ATM) fuse "
     "solders straight in with no holder (C3207114 does not fit it)"),
    ({P1: ["J2", "J3", "J5", "J6"]}, "through-hole pin header: hand-solder "
     "(or pay for JLCPCB THT assembly)"),
    ({MGR: ["J6"]}, "ILI9341+XPT2046 2.8in module plugs here - AliExpress, "
     "confirm 3V3-VCC jumper"),
]


def lookup(board):
    """ref -> dict(lcsc, mpn, mfr, price, note) for one board."""
    out = {}
    for boards, lcsc, mpn, mfr, price, note in PARTS:
        for ref in boards.get(board, []):
            assert ref not in out, f"{board} {ref} assigned twice"
            out[ref] = dict(lcsc=lcsc, mpn=mpn, mfr=mfr, price=price, note=note)
    for boards, note in NOTES:
        for ref in boards.get(board, []):
            assert ref not in out, f"{board} {ref} has a part and a note"
            out[ref] = dict(lcsc="", mpn="", mfr="", price=None, note=note)
    return out
