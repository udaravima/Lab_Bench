"""LCSC part assignments, transcribed from hardware/SOURCING.md (2026-07-18 pass).

Every row names the exact references it applies to on each board, so nothing
is matched by guesswork on the Value string. Only parts SOURCING.md verified
get an LCSC number; everything else (generic R/C, jellybeans, pin headers)
stays blank in the BOM until it is chosen at order time.

Row: (boards -> refs, LCSC, MPN, manufacturer, USD qty-1, note)
`boards` maps a board directory name to a list of references.
A note starting with "CHECK" is a mismatch a human must resolve before
ordering (footprint or variant differs from what SOURCING.md picked).
"""

P1, P2, BP, MGR = ("phase1-module", "phase2-module",
                   "phase3-backplane", "phase3-manager")

PARTS = [
    # ---- A. Semiconductors -------------------------------------------------
    ({P2: ["U3"]}, "C5219258", "LM5143QRHARQ1", "TI", 2.93,
     "CHECK: symbol value says LM5143RHAR; SOURCING picked the cheaper Q1 "
     "variant (same VQFN-40) - confirm RHA0040P land vs the Q1 addendum"),
    ({P2: ["U12"]}, "C111822", "LM5069MM-2/NOPB", "TI", 1.17, ""),
    ({P2: ["Q1", "Q2", "Q3", "Q4", "Q10", "Q11", "Q12", "Q13"]},
     "C86513", "CSD18540Q5B", "TI", 1.43,
     "do not substitute clone power-stage FETs"),
    ({P2: ["Q14"]}, "C2687963", "CSD19536KTT", "TI", 4.94,
     "hot-swap pass FET, SOA-critical, thin stock - order early"),
    ({P1: ["U10"], P2: ["U10"]}, "C529355", "STM32G431CBT6", "ST", 2.85, ""),
    ({P1: ["U1"], P2: ["U1"]}, "C1880990", "DAC80502DRXR", "TI", 4.19,
     "value says DRXT; R/T differ only in reel size"),
    ({P1: ["U5"], P2: ["U5"], BP: ["U1"]},
     "C2887910", "INA228AIDGSR", "TI", 3.83, ""),
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
    ({P1: ["U6"], P2: ["U6"]}, "C690105", "LTC7004EMSE#PBF", "ADI", 5.77,
     "thinnest stock in the BOM - order early (IMSE fallback)"),
    ({P1: ["U7"], P2: ["U7"]}, "C193688", "TLV7011DCKR", "TI", 0.27,
     "SC-70-5 (DCK)"),
    ({P2: ["D8"]}, "C41283", "TL431BIDBZR", "TI", 0.054, ""),
    ({P2: ["U13"]}, "C353035", "TS5A3166DBVR", "TI", 0.28, ""),
    ({MGR: ["U13"]}, "C130204", "TCA9535PWR", "TI", 0.44,
     "UMW clone acceptable here"),
    ({MGR: ["U10"]}, "C2913204", "ESP32-S3-WROOM-1-N8R2", "Espressif", 5.01, ""),
    ({MGR: ["U12"]}, "C150526", "TPD2E001DRLR", "TI", 0.16, ""),
    ({P1: ["U3"]}, "C485912", "LM5145RGYR", "TI", 1.55, ""),
    ({P1: ["Q1", "Q2"]}, "C77239", "CSD18563Q5A", "TI", 0.85, ""),

    # ---- B. Magnetics & power passives ------------------------------------
    ({P2: ["L1", "L3"]}, "C6238332", "MWSA1707S-6R8MT", "Sunlord", 1.72,
     "17 A Irms / 22 A Isat; placeholder footprint until the land pass"),
    ({P1: ["L1"]}, "C5240401", "MWSA1707S-100MT", "Sunlord", 1.68,
     "16.5 A Isat / 10.5 A Irms; placeholder footprint until the land pass"),
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
    ({P2: ["C15", "C16", "C36", "C37"]}, "C2923769", "", "Lelon", 0.28,
     "CHECK: SOURCING part is Lelon SVZ D8x11.5 polymer, symbol says "
     "'hybrid' on a CP_Elec_10x10.5 footprint - pick footprint or part; "
     "verify ESR <= 25 mOhm"),
    ({P2: ["C14"]}, "C106666", "", "", 0.10, "470 uF 50 V THT radial D10"),
    ({P2: ["C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13",
           "C38", "C40", "C45", "C46", "C47", "C48"]},
     "C126612", "GCM32EC71H106KA03L", "Murata", 0.144, ""),
    ({P1: ["Y1"], P2: ["Y1"]}, "C400090", "", "", 0.105,
     "8 MHz 3225, CL = 12 pF (load caps 18 p)"),

    # ---- C. Connectors & electromechanical --------------------------------
    ({P2: ["J1", "J4"]}, "C98732", "XT60PW-M", "Amass", 0.54, ""),
    ({BP: ["J10", "J11", "J12", "J13", "J14", "J15", "J16", "J17"]},
     "C428722", "XT60PW-F", "Amass", 0.56, ""),
    ({MGR: ["J3"]}, "C165948", "TYPE-C-31-M-12", "Korean Hroparts", 0.16,
     "CHECK: footprint is GCT USB4105 - swap to the TYPE-C-31-M-12 land "
     "before ordering, or order a USB4105"),
    ({MGR: ["ENC1"]}, "C2831776", "", "", 0.036, "generic EC11"),
    ({MGR: ["BZ1"]}, "C94599", "MLT-8530", "", 0.18,
     "verify 5 V drive on datasheet"),
    ({P2: ["F1"]}, "C3207132", "", "", 0.42,
     "ATO fuse HOLDER; the 35 A fuse itself is bought separately"),
    ({MGR: ["F1"]}, "C3207114", "", "", 0.64,
     "mini blade fuse HOLDER; the 2 A fuse itself is bought separately"),
]

# Parts with no LCSC number yet that are worth saying why in the BOM.
NOTES = [
    ({P1: ["J1", "J4"]},
     "SOURCING lists 2EDG 5.08 plugs C3697 for P1 bench IO, but this "
     "footprint is a 5.0 mm Phoenix PT - pick the matching header"),
    ({P1: ["F1"]}, "mini blade holder; likely C3207114 as on the manager, "
     "not confirmed for 10 A"),
    ({BP: ["C2"]}, "SOURCING's 470 uF part C106666 is THT D10; this board "
     "uses a 16x17.5 SMD footprint - choose an SMD part"),
    ({P1: ["C21", "C22", "C78"]}, "not in SOURCING - choose at order time"),
    ({P1: ["Q3", "Q4"]}, "60 V NFET not chosen in SOURCING"),
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
