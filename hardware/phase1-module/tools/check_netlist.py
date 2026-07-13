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
    nets = {}
    for part in re.split(r'\(net \(code "\d+"\) ', text)[1:]:
        name = re.match(r'\(name "([^"]+)"\)', part).group(1).split("/")[-1]
        nodes = {f"{r}.{p}" for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', part)}
        nets.setdefault(name, set()).update(nodes)
    return nets


def main():
    nets = parse_nets(sys.argv[1])
    fails = 0
    for name, want in EXPECTED_NETS.items():
        got = {n for n in nets.get(name, set()) if not n.startswith("#")}
        if got != want:
            print(f"FAIL net {name}:")
            if want - got:
                print(f"   missing: {sorted(want - got)}")
            if got - want:
                print(f"   extra:   {sorted(got - want)}")
            fails += 1
    # every expected pin must not have leaked into some other net
    owner = {}
    for name, got in nets.items():
        for node in got:
            owner.setdefault(node, set()).add(name)
    for name, want in EXPECTED_NETS.items():
        for node in want:
            others = owner.get(node, set()) - {name}
            if others:
                print(f"FAIL pin {node}: also in nets {sorted(others)} (expected only {name})")
                fails += 1
    print("check_netlist:", "all nets OK" if fails == 0 else f"{fails} failures")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
