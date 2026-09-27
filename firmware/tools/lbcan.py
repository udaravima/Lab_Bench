#!/usr/bin/env python3
"""lbcan.py - bench helper for the Lab_Bench CAN protocol (docs/03).

Builds `cansend` frames so nobody hand-encodes little-endian hex, and decodes
`candump` output into readable lines or CSV. Standard library only; mirrors
firmware/common/labbench_can.h.

  lbcan.py enc setvi 5 1            -> 100#404B4C0040420F00   (5 V, 1 A)
  lbcan.py enc output on            -> 101#01
  lbcan.py enc limits 150 85 hold   -> 102#F049020052030100
  lbcan.py enc cal vset gain 65700  -> 103#0001A4000100
  lbcan.py enc heartbeat            -> 021#00000000
  lbcan.py --slot 2 enc ident       -> 124#

  cansend can0 $(lbcan.py enc setvi 5 1)
  candump -L can0 | lbcan.py dec           # readable, live
  candump -L can0 | lbcan.py dec --csv > run.csv

`dec` accepts `candump -L` / `-l` log lines ("(ts) can0 302#...") and the
default candump layout ("can0  302   [8]  00 01 ...").
"""
import argparse
import re
import struct
import sys
import time

CMD_BASE, STATUS_BASE, FAULT_BASE, HELLO_BASE = 0x100, 0x300, 0x010, 0x7E0
GLOBAL_OFF, GLOBAL_STATE = 0x020, 0x021

OUT_MODES = {"off": 0, "on": 1, "dem": 2, "droop": 3, "dem-droop": 4}
POLICIES = {"off": 0, "hold": 1}
CAL_ITEMS = {"vset": 0, "iset": 1, "vmeas": 2, "imeas": 3}
CAL_POINTS = {"offset": 0, "gain": 1}
RESETS = {"reboot": 0xA5, "clear": 0x5A}

STATES = {0: "SAFE", 1: "ACTIVE", 2: "FAULT"}
FAULT_BITS = {0x01: "OCP_BACKUP", 0x02: "OVP_HW", 0x04: "OTP", 0x08: "SENSE",
              0x10: "REVCUR"}
WARN_BITS = {0x01: "ENV_CLAMP", 0x02: "DERATE", 0x04: "COMMS_LOST"}
MODE_BITS = {0x01: "OUT_ON", 0x02: "DEM", 0x04: "DROOP", 0x08: "CC"}


def frame(can_id, payload=b""):
    return "%03X#%s" % (can_id, payload.hex().upper())


def encode(slot, args):
    cmd = lambda c: CMD_BASE + slot * 0x10 + c
    kind = args[0]
    if kind == "setvi":        # volts, amps
        v, i = float(args[1]), float(args[2])
        return frame(cmd(0), struct.pack("<ii", round(v * 1e6), round(i * 1e6)))
    if kind == "output":
        return frame(cmd(1), bytes([OUT_MODES[args[1]]]))
    if kind == "limits":       # watts, derate degC, policy
        p, t, pol = float(args[1]), float(args[2]), POLICIES[args[3]]
        return frame(cmd(2), struct.pack("<ihBB", round(p * 1e3), round(t * 10), pol, 0))
    if kind == "cal":          # item, point, raw int32 value
        it, pt, val = CAL_ITEMS[args[1]], CAL_POINTS[args[2]], int(args[3])
        return frame(cmd(3), struct.pack("<BBi", it, pt, val))
    if kind == "ident":
        return frame(cmd(4))
    if kind == "reset":
        return frame(cmd(5), bytes([RESETS[args[1]]]))
    if kind == "heartbeat":
        return frame(GLOBAL_STATE, struct.pack("<HBB", 0, 0, 0))
    if kind == "global-off":
        return frame(GLOBAL_OFF)
    raise SystemExit("unknown frame kind: %s" % kind)


def bits(v, names):
    return "|".join(n for b, n in names.items() if v & b) or "-"


def decode(can_id, d):
    """Return (name, dict of fields) for one frame."""
    if FAULT_BASE <= can_id < FAULT_BASE + 8:
        return "FAULT", {"slot": can_id - FAULT_BASE, "fault": bits(d[0], FAULT_BITS),
                         "warn": bits(d[1], WARN_BITS), "state": STATES.get(d[2], d[2])}
    if HELLO_BASE <= can_id < HELLO_BASE + 8:
        return "HELLO", {"slot": can_id - HELLO_BASE, "proto": d[0],
                         "fw": "%d.%d" % (d[1], d[2])}
    if can_id == GLOBAL_OFF:
        return "GLOBAL_OFF", {}
    if can_id == GLOBAL_STATE:
        return "GLOBAL_STATE", {}
    if CMD_BASE <= can_id < CMD_BASE + 0x80:
        return "CMD", {"slot": (can_id - CMD_BASE) >> 4, "cmd": can_id & 0xF,
                       "data": d.hex().upper()}
    if STATUS_BASE <= can_id < STATUS_BASE + 0x80:
        slot, typ = (can_id - STATUS_BASE) >> 4, can_id & 0xF
        if typ == 0 and len(d) >= 8:
            v, i = struct.unpack("<ii", d[:8])
            return "TELEM_VI", {"slot": slot, "V": "%.6f" % (v / 1e6), "A": "%.6f" % (i / 1e6)}
        if typ == 1 and len(d) >= 8:
            tf, ti, vb, p = struct.unpack("<hhHH", d[:8])
            return "TELEM_AUX", {"slot": slot, "T_fet_C": tf / 10, "T_ind_C": ti / 10,
                                 "Vbus": "%.2f" % (vb / 100), "P_W": "%.1f" % (p / 10)}
        if typ == 2 and len(d) >= 8:
            st, fa, wa, mo, vs, is_ = struct.unpack("<BBBBhh", d[:8])
            return "STATUS", {"slot": slot, "state": STATES.get(st, st),
                              "fault": bits(fa, FAULT_BITS), "warn": bits(wa, WARN_BITS),
                              "mode": bits(mo, MODE_BITS), "Vset": vs / 100, "Iset": is_ / 100}
        if typ == 3 and len(d) >= 8:
            q, e = struct.unpack("<ii", d[:8])
            return "ENERGY", {"slot": slot, "Ah": q / 1e5, "Wh": e / 1e5}
    return "UNKNOWN", {"id": "%03X" % can_id, "data": d.hex().upper()}


LOG_RE = re.compile(r"^\((\d+\.\d+)\)\s+\S+\s+([0-9A-Fa-f]{3,8})#([0-9A-Fa-f]*)")
STD_RE = re.compile(r"^\s*(?:\((\d+\.\d+)\)\s+)?\S+\s+([0-9A-Fa-f]{3,8})\s+\[\d\]\s*((?:[0-9A-Fa-f]{2}\s*)*)")


def parse_line(line):
    m = LOG_RE.match(line) or STD_RE.match(line)
    if not m:
        return None
    ts = float(m.group(1)) if m.group(1) else time.time()
    return ts, int(m.group(2), 16), bytes.fromhex(m.group(3).replace(" ", ""))


def run_decode(stream, csv, only):
    if csv:
        print("time,frame,slot,field,value")
    for line in stream:
        p = parse_line(line)
        if not p:
            continue
        ts, can_id, data = p
        name, fields = decode(can_id, data)
        if only and name not in only:
            continue
        if csv:
            slot = fields.pop("slot", "")
            for k, v in fields.items():
                print("%.3f,%s,%s,%s,%s" % (ts, name, slot, k, v))
        else:
            print("%.3f %-12s %s" % (ts, name, " ".join("%s=%s" % kv for kv in fields.items())))
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slot", type=int, default=0, help="module slot 0-7 (default 0)")
    sub = ap.add_subparsers(dest="verb", required=True)
    e = sub.add_parser("enc", help="print a cansend frame")
    e.add_argument("args", nargs="+")
    d = sub.add_parser("dec", help="decode candump output from stdin")
    d.add_argument("--csv", action="store_true", help="long-format CSV")
    d.add_argument("--only", nargs="*", default=None, help="frame names to keep, e.g. TELEM_VI STATUS")
    a = ap.parse_args()
    if a.verb == "enc":
        print(encode(a.slot, a.args))
    else:
        run_decode(sys.stdin, a.csv, set(a.only) if a.only else None)


if __name__ == "__main__":
    main()
