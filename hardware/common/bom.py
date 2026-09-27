#!/usr/bin/env python3
"""Write LCSC/MPN properties into the schematics and emit BOM CSVs.

    python3 common/bom.py            # from hardware/: annotate + BOMs, all boards
    python3 common/bom.py --check    # exit 1 if any schematic or CSV is stale

The schematics are hand-owned, so this is a surgical edit: it only inserts
(or updates) hidden "LCSC" / "MPN" / "Manufacturer" properties inside the
placed-symbol blocks and touches nothing else. Part numbers come from
lcsc_parts.py (transcribed from SOURCING.md). No kicad-cli needed.

Per board it writes <board>/bom/<board>-bom.csv (grouped, with prices and
notes) and <board>/bom/<board>-jlcpcb.csv (JLCPCB assembly upload format).
"""
import csv, glob, io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lcsc_parts import P1, P2, BP, MGR, lookup  # noqa: E402

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARDS = [P1, P2, BP, MGR]
FIELDS = [("LCSC", "lcsc"), ("MPN", "mpn"), ("Manufacturer", "mfr")]


def symbol_blocks(s):
    """(start, end) of every placed symbol - lib_symbols entries are skipped
    because they are `(symbol "Lib:Name"`, not `(symbol (lib_id`."""
    for m in re.finditer(r'\n  \(symbol \(lib_id "[^"]+"\)', s):
        i, depth = m.start() + 1, 0
        while True:
            c = s[i]
            if c == '"':
                i += 1
                while s[i] != '"':
                    i += 2 if s[i] == "\\" else 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        yield m.start() + 1, i + 1


def props(block):
    return dict(re.findall(r'\(property "([^"]+)" "((?:[^"\\]|\\.)*)"', block))


def prop_span(block, name):
    """(start, end) of `\n    (property "name" ...)`, or None. Works for both
    the one-line form the generators wrote and KiCad's own multi-line form."""
    m = re.search(r'\n    \(property "%s" ' % re.escape(name), block)
    if not m:
        return None
    i, depth = m.start() + 1, 0
    while True:
        c = block[i]
        if c == '"':
            i += 1
            while block[i] != '"':
                i += 2 if block[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return m.start(), i + 1
        i += 1


def set_prop(block, name, value):
    """Update property `name` in place, or add it hidden after Datasheet,
    in the same one-line / multi-line style as the Datasheet property.
    An empty value removes the property."""
    span = prop_span(block, name)
    if not value:
        return block if span is None else block[:span[0]] + block[span[1]:]
    ds = prop_span(block, "Datasheet")
    at = re.search(r'\(property "Footprint" "[^"]*" (\(at [^)]*\))', block)
    head = '\n    (property "%s" "%s" %s' % (name, value.replace('"', '\\"'),
                                          at.group(1))
    if "\n" in block[ds[0] + 1:ds[1]]:
        new = head + '\n      (effects (font (size 1.27 1.27)) hide)\n    )'
    else:
        new = head + ' (effects (font (size 1.27 1.27)) hide))'
    if span:
        return block[:span[0]] + new + block[span[1]:]
    return block[:ds[1]] + new + block[ds[1]:]


def process_board(board, write):
    parts = lookup(board)
    comps, seen, stale = {}, set(), []
    for path in sorted(glob.glob(os.path.join(HW, board, "*.kicad_sch"))):
        s = open(path).read()
        out, last = [], 0
        for a, b in symbol_blocks(s):
            blk = s[a:b]
            p = props(blk)
            ref = p["Reference"]
            if ref.startswith("#"):
                continue
            seen.add(ref)
            info = parts.get(ref, {})
            new = blk
            for prop, key in reversed(FIELDS):  # each lands after Datasheet
                new = set_prop(new, prop, info.get(key, ""))
            out += [s[last:a], new]
            last = b
            if ("(in_bom no)" in blk or "(dnp yes)" in blk
                    or '(lib_id "Device:NetTie' in blk):  # copper, not a part
                continue
            if p["Value"].startswith("DNP") and not info:
                info = dict(note="do not populate (value says DNP)")
            # multi-unit symbols (OPA2333 U2) appear once per unit
            comps.setdefault(ref, dict(value=p["Value"],
                                       footprint=p["Footprint"], **info))
        new_s = "".join(out) + s[last:]
        if new_s != s:
            stale.append(os.path.relpath(path, HW))
            if write:
                open(path, "w").write(new_s)
    missing = sorted(set(parts) - seen)
    assert not missing, f"{board}: lcsc_parts.py names unknown refs {missing}"
    return comps, stale


def refkey(ref):
    m = re.match(r"([A-Z]+)(\d+)", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def bom_csvs(board, comps):
    groups = {}
    for ref, c in comps.items():
        key = (c["value"], c["footprint"], c.get("lcsc", ""), c.get("mpn", ""))
        groups.setdefault(key, []).append(ref)
    rows = sorted(groups.items(),
                  key=lambda kv: refkey(sorted(kv[1], key=refkey)[0]))
    full, jlc = io.StringIO(), io.StringIO()
    fw, jw = csv.writer(full, lineterminator="\n"), csv.writer(jlc, lineterminator="\n")
    fw.writerow(["Item", "Qty", "References", "Value", "Footprint", "LCSC",
                 "MPN", "Manufacturer", "Unit USD", "Ext USD", "Note"])
    jw.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    total, assigned = 0.0, 0
    for n, ((value, fp, lcsc, mpn), refs) in enumerate(rows, 1):
        refs = sorted(refs, key=refkey)
        c = comps[refs[0]]
        price = c.get("price")
        ext = round(price * len(refs), 3) if price is not None else None
        if ext is not None:
            total += ext
        if lcsc:
            assigned += len(refs)
        fw.writerow([n, len(refs), " ".join(refs), value, fp, lcsc, mpn,
                     c.get("mfr", ""), "" if price is None else price,
                     "" if ext is None else ext, c.get("note", "")])
        if not value.startswith("DNP"):
            jw.writerow([value, ",".join(refs), fp.split(":")[-1], lcsc])
    fw.writerow(["", sum(len(r) for _, r in rows), "", "", "", "", "", "", "",
                 round(total, 2),
                 f"{assigned}/{len(comps)} placements have an LCSC number; "
                 "total covers those only (qty-1, SOURCING.md 2026-07-18)"])
    return full.getvalue(), jlc.getvalue(), assigned


def main():
    check = "--check" in sys.argv
    dirty = []
    for board in BOARDS:
        comps, stale = process_board(board, write=not check)
        dirty += stale
        full, jlc, assigned = bom_csvs(board, comps)
        for suffix, text in (("bom", full), ("jlcpcb", jlc)):
            path = os.path.join(HW, board, "bom", f"{board}-{suffix}.csv")
            old = open(path).read() if os.path.exists(path) else None
            if old != text:
                dirty.append(os.path.relpath(path, HW))
                if not check:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    open(path, "w").write(text)
        print(f"{board}: {len(comps)} components, {assigned} with LCSC")
    if dirty:
        print(("stale: " if check else "updated: ") + ", ".join(dirty))
    sys.exit(1 if check and dirty else 0)


if __name__ == "__main__":
    main()
