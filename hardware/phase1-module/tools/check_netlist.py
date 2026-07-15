"""Assert generated-schematic connectivity against gen_phase1.EXPECTED_NETS.

Usage: python3 check_netlist.py <netlist.net>
The netlist comes from: kicad-cli sch export netlist -o out.net phase1-module.kicad_sch
Net names may carry sheet-path prefixes (local labels) — matched by last path
segment. Fails (exit 1) on: missing net, wrong pin membership, or any
expected pin appearing in an unexpected net.
"""
import re
import sys
from gen_phase1 import EXPECTED_NETS


def parse_nets(path):
    text = open(path).read()
    nets, raw_names = {}, {}
    for part in re.split(r'\(net \(code "\d+"\) ', text)[1:]:
        full = re.match(r'\(name "([^"]+)"\)', part).group(1)
        name = full.split("/")[-1]
        nodes = {f"{r}.{p}" for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', part)}
        nets.setdefault(name, set()).update(nodes)
        raw_names.setdefault(name, set()).add(full)
    return nets, raw_names


def main():
    text = open(sys.argv[1]).read()
    refs = re.findall(r'\(comp \(ref "([^"]+)"\)', text)
    nets, raw_names = parse_nets(sys.argv[1])
    fails = 0
    for r in sorted({x for x in refs if refs.count(x) > 1}):
        print(f"FAIL duplicate reference: {r} used {refs.count(r)} times")
        fails += 1
    # A base name appearing as several distinct netlist nets (e.g. global "X"
    # plus local "/sheet/X") means labels that LOOK connected but are not.
    for name, fulls in raw_names.items():
        if len(fulls) > 1 and name in {k.lstrip("~") for k in EXPECTED_NETS}:
            print(f"FAIL name collision: '{name}' is {len(fulls)} separate nets: {sorted(fulls)}")
            fails += 1
    for name, want in EXPECTED_NETS.items():
        subset = name.startswith("~")   # "~NET": net must contain these pins (extras allowed)
        key = name.lstrip("~")
        got = {n for n in nets.get(key, set()) if not n.startswith("#")}
        bad = (want - got) if subset else (got != want)
        if bad:
            print(f"FAIL net {key}:")
            if want - got:
                print(f"   missing: {sorted(want - got)}")
            if not subset and got - want:
                print(f"   extra:   {sorted(got - want)}")
            fails += 1
    # every expected pin must not have leaked into some other net
    owner = {}
    for name, got in nets.items():
        for node in got:
            owner.setdefault(node, set()).add(name)
    for name, want in EXPECTED_NETS.items():
        key = name.lstrip("~")
        for node in want:
            others = owner.get(node, set()) - {key}
            if others:
                print(f"FAIL pin {node}: also in nets {sorted(others)} (expected only {key})")
                fails += 1
    print("check_netlist:", "all nets OK" if fails == 0 else f"{fails} failures")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
