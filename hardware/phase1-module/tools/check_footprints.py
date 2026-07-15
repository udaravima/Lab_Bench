"""Assert footprint integrity of the exported netlist.

For every component in the netlist:
  1. it has a non-empty footprint of the form "lib:name",
  2. the .kicad_mod file resolves (labbench.pretty or the system library),
  3. every pin that appears on a net has a same-numbered pad in the footprint,
  4. polarized/multi-pin sanity: pad count >= number of distinct netlist pins.

Usage: python3 check_footprints.py <netlist.net>
Run after check_netlist.py; exit 1 on any failure.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FPDIRS = [os.path.join(HERE, "..", "lib"), "/usr/share/kicad/footprints"]


def footprint_pads(lib, name):
    for d in FPDIRS:
        path = os.path.join(d, f"{lib}.pretty", f"{name}.kicad_mod")
        if os.path.exists(path):
            text = open(path).read()
            return set(re.findall(r'\(pad "([^"]+)"', text)) | \
                   set(re.findall(r'\(pad ([^\s"()]+) ', text))
    return None


def main():
    text = open(sys.argv[1]).read()
    comps = {}   # ref -> footprint
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\(value "[^"]*"\)\s*\(footprint "([^"]*)"\)', text):
        comps[m.group(1)] = m.group(2)
    allrefs = set(re.findall(r'\(comp \(ref "([^"]+)"\)', text))
    used_pins = {}   # ref -> set of pin numbers on nets
    for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', text):
        used_pins.setdefault(ref, set()).add(pin)

    fails = 0
    for ref in sorted(allrefs):
        if ref.startswith("#"):
            continue
        fp = comps.get(ref, "")
        if not fp or ":" not in fp:
            print(f"FAIL {ref}: missing/odd footprint '{fp}'")
            fails += 1
            continue
        lib, name = fp.split(":", 1)
        pads = footprint_pads(lib, name)
        if pads is None:
            print(f"FAIL {ref}: footprint {fp} not found in lib dirs")
            fails += 1
            continue
        missing = used_pins.get(ref, set()) - pads
        if missing:
            print(f"FAIL {ref}: netlist pins {sorted(missing)} have no pad in {fp} "
                  f"(pads: {sorted(pads)})")
            fails += 1
    print("check_footprints:", "all footprints OK" if fails == 0 else f"{fails} failures",
          f"({len([r for r in allrefs if not r.startswith('#')])} components)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
