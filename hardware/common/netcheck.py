"""Shared netlist/footprint assertion logic (see phase*/tools/check_*.py).

run_netcheck(netlist_path, expected): assert exact/superset ("~" prefix) net
membership, duplicate refs, split-net name collisions, and pin leaks.
run_fpcheck(netlist_path, fpdirs): every component resolves a footprint and
every netted pin has a matching pad.
Both print a summary line and return the failure count.
"""
import os
import re


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


def run_netcheck(path, expected):
    text = open(path).read()
    refs = re.findall(r'\(comp \(ref "([^"]+)"\)', text)
    nets, raw_names = parse_nets(path)
    fails = 0
    for r in sorted({x for x in refs if refs.count(x) > 1}):
        print(f"FAIL duplicate reference: {r} used {refs.count(r)} times")
        fails += 1
    # A base name appearing as several distinct netlist nets (e.g. global "X"
    # plus local "/sheet/X") means labels that LOOK connected but are not.
    for name, fulls in raw_names.items():
        if len(fulls) > 1 and name in {k.lstrip("~") for k in expected}:
            print(f"FAIL name collision: '{name}' is {len(fulls)} separate nets: {sorted(fulls)}")
            fails += 1
    for name, want in expected.items():
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
    for name, want in expected.items():
        key = name.lstrip("~")
        for node in want:
            others = owner.get(node, set()) - {key}
            if others:
                print(f"FAIL pin {node}: also in nets {sorted(others)} (expected only {key})")
                fails += 1
    print("check_netlist:", "all nets OK" if fails == 0 else f"{fails} failures")
    return fails


def _footprint_pads(fpdirs, lib, name):
    for d in fpdirs:
        path = os.path.join(d, f"{lib}.pretty", f"{name}.kicad_mod")
        if os.path.exists(path):
            text = open(path).read()
            return set(re.findall(r'\(pad "([^"]+)"', text)) | \
                   set(re.findall(r'\(pad ([^\s"()]+) ', text))
    return None


def run_fpcheck(path, fpdirs):
    text = open(path).read()
    comps = {}
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\(value "[^"]*"\)\s*\(footprint "([^"]*)"\)', text):
        comps[m.group(1)] = m.group(2)
    allrefs = set(re.findall(r'\(comp \(ref "([^"]+)"\)', text))
    # Only pins on REAL nets need pads. KiCad exports deliberately-open pins
    # as single-node "unconnected-(...)" nets; a pin with no connection needs
    # no pad (e.g. the 24-pin USB-C symbol on a 16-pad USB2.0 receptacle).
    used_pins = {}
    for part in re.split(r'\(net \(code "\d+"\) ', text)[1:]:
        name = re.match(r'\(name "([^"]+)"\)', part).group(1)
        if name.startswith("unconnected-"):
            continue
        for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', part):
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
        pads = _footprint_pads(fpdirs, lib, name)
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
    return fails
