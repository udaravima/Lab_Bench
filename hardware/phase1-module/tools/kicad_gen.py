"""Minimal KiCad 7 schematic generator.

Extracts symbol definitions from the system libraries (flattening `extends`
derivations), places symbols/labels/power ports, and emits .kicad_sch files
in the v7 (20230121) format. Connectivity is made exclusively with labels
placed exactly on pin connection points, so the result is mechanically
verifiable via `kicad-cli sch export netlist` (see check_netlist.py).
"""
import re
import uuid as uuidlib

SYMDIR = "/usr/share/kicad/symbols"
LOCAL_LIBDIR = __import__("os").path.join(
    __import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "lib")
FONT = "(effects (font (size 1.27 1.27)))"


def _uuid():
    return str(uuidlib.uuid4())


def _find_block(text, header):
    """Return the s-expr block starting with `header`, paren-matched,
    ignoring parens inside quoted strings."""
    start = text.find(header)
    if start < 0:
        return None
    depth, i, in_str = 0, start, False
    while True:
        ch = text[i]
        if in_str:
            if ch == '\\':
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1


class Symbol:
    """A library symbol: raw definition text + pin geometry per unit."""

    def __init__(self, lib, name, block=None):
        self.lib, self.name = lib, name
        libtext = ""
        if block is None:
            import os
            for d in (LOCAL_LIBDIR, SYMDIR):
                path = os.path.join(d, f"{lib}.kicad_sym")
                if os.path.exists(path):
                    libtext = open(path).read()
                    block = _find_block(libtext, f'(symbol "{name}"')
                    if block:
                        break
        if block is None:
            raise KeyError(f"{lib}:{name} not found")
        m = re.search(r'\(extends "([^"]+)"\)', block)
        if m:
            parent = _find_block(libtext, f'(symbol "{m.group(1)}"')
            props = dict(re.findall(r'\(property "([^"]+)" "([^"]*)"', block))
            flat = parent.replace(f'"{m.group(1)}', f'"{name}')
            for key, val in props.items():
                flat = re.sub(r'(\(property "%s" ")[^"]*(")' % re.escape(key),
                              lambda mm: mm.group(1) + val + mm.group(2), flat, count=1)
            block = flat
        self.block = block
        self.pins = {}   # (unit, pin_number) -> (x, y, name)
        pin_re = (r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) [\d.]+\)'
                  r'.*?\(name "([^"]*)".*?\(number "([^"]*)"')
        for um in re.finditer(r'\(symbol "%s_(\d+)_\d+"' % re.escape(name), block):
            unit = int(um.group(1))
            ub = _find_block(block[um.start():], um.group(0))
            for pm in re.finditer(pin_re, ub, re.S):
                x, y, pname, pnum = pm.groups()
                key = (unit if unit else 1, pnum)
                self.pins[key] = (float(x), float(y), pname)
        if not self.pins:  # SnapMagic/UL style: pins directly in the main block
            for pm in re.finditer(pin_re, block, re.S):
                x, y, pname, pnum = pm.groups()
                self.pins[(1, pnum)] = (float(x), float(y), pname)

    def pin_names(self, unit=1):
        return {num: n for (u, num), (_, _, n) in self.pins.items() if u in (0, unit)}

    def emit_libsym(self):
        return self.block.replace(f'(symbol "{self.name}"',
                                  f'(symbol "{self.lib}:{self.name}"', 1)


class Placed:
    def __init__(self, sym, ref, value, x, y, rot=0, unit=1, footprint=""):
        self.sym, self.ref, self.value = sym, ref, value
        self.x, self.y, self.rot, self.unit = x, y, rot, unit
        self.footprint = footprint
        self.uuid = _uuid()

    def pin_pos(self, pnum):
        """Absolute schematic position of a pin's connection point."""
        key = (self.unit, str(pnum))
        if key not in self.sym.pins:            # common-unit pins live in unit 0
            key = (0, str(pnum))
            if key not in self.sym.pins:
                for (u, n), v in self.sym.pins.items():
                    if n == str(pnum):
                        key = (u, n)
                        break
        px, py, _ = self.sym.pins[key]
        r = self.rot % 360
        if r == 0:
            dx, dy = px, -py
        elif r == 90:
            dx, dy = -py, -px
        elif r == 180:
            dx, dy = -px, py
        else:
            dx, dy = py, px
        return (round(self.x + dx, 3), round(self.y + dy, 3))

    def label_rot(self, pnum):
        """Rotation that makes a label extend outward from the symbol body."""
        px, py = self.pin_pos(pnum)
        dx, dy = px - self.x, py - self.y
        if dx == 0 and dy == 0:
            return 0
        if abs(dx) >= abs(dy):
            return 0 if dx > 0 else 180
        return 270 if dy > 0 else 90

    def _field_spots(self):
        """Reference/Value positions outside the unit's pin bounding box:
        wide symbols get fields above/below (centered); tall ones get them at
        the top-right (left-justified); power ports get a compact side note."""
        pts = [self.pin_pos(num) for (u, num) in self.sym.pins if u in (0, self.unit)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if self.ref.startswith("#"):
            return (self.x + 1.27, self.y - 1.27, "left"), (self.x + 1.27, self.y + 1.27, "left")
        if (x1 - x0) >= (y1 - y0):
            return (self.x, y0 - 3.81, ""), (self.x, y1 + 3.81, "")
        return (x1 + 2.54, y0 - 1.27, "left"), (x1 + 2.54, y0 + 1.27, "left")

    def emit(self, project, path):
        pins = "\n".join(
            f'    (pin "{num}" (uuid {_uuid()}))'
            for (u, num) in sorted(self.sym.pins, key=lambda k: k[1])
            if u in (0, self.unit) or self._unit_count() == 1)
        (rx, ry, rj), (vx, vy, vj) = self._field_spots()
        rjust = f" (justify {rj})" if rj else ""
        vjust = f" (justify {vj})" if vj else ""
        rhide = " hide" if self.ref.startswith("#") else ""
        if self.ref.startswith("#FLG"):
            vjust += " hide"
        return f"""  (symbol (lib_id "{self.sym.lib}:{self.sym.name}") (at {self.x} {self.y} {self.rot}) (unit {self.unit})
    (in_bom yes) (on_board yes) (dnp no)
    (uuid {self.uuid})
    (property "Reference" "{self.ref}" (at {rx} {ry} 0) (effects (font (size 1.27 1.27)){rjust}{rhide}))
    (property "Value" "{self.value}" (at {vx} {vy} 0) (effects (font (size 1.27 1.27)){vjust}))
    (property "Footprint" "{self.footprint}" (at {self.x} {self.y} 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "~" (at {self.x} {self.y} 0) (effects (font (size 1.27 1.27)) hide))
{pins}
    (instances (project "{project}" (path "{path}" (reference "{self.ref}") (unit {self.unit}))))
  )"""

    def _unit_count(self):
        return len({u for (u, _) in self.sym.pins})


class Sheet:
    """One .kicad_sch file being assembled."""

    def __init__(self, project, path):
        self.project, self.path = project, path
        self.uuid = _uuid()
        self.symbols = []       # Placed
        self.items = []         # raw text chunks
        self.libsyms = {}       # "lib:name" -> text

    def add(self, placed):
        self.symbols.append(placed)
        key = f"{placed.sym.lib}:{placed.sym.name}"
        self.libsyms.setdefault(key, placed.sym.emit_libsym())
        return placed

    def glabel(self, net, pos, rot=0, shape="passive"):
        self.items.append(
            f'  (global_label "{net}" (shape {shape}) (at {pos[0]} {pos[1]} {rot}) '
            f'(fields_autoplaced) {FONT} (uuid {_uuid()}))')

    def label(self, net, pos, rot=0):
        self.items.append(
            f'  (label "{net}" (at {pos[0]} {pos[1]} {rot}) {FONT} (uuid {_uuid()}))')

    def power(self, net, x, y, ground=False, rot=0):
        sym = power_symbol(net, ground=ground)
        p = Placed(sym, f"#PWR{len(self.symbols):03d}", net, x, y, rot)
        self.add(p)
        return p

    def pwr_flag(self, x, y):
        sym = get_symbol("power", "PWR_FLAG")
        p = Placed(sym, f"#FLG{len(self.symbols):03d}", "PWR_FLAG", x, y, 0)
        self.add(p)
        return p

    def no_connect(self, pos):
        self.items.append(f'  (no_connect (at {pos[0]} {pos[1]}) (uuid {_uuid()}))')

    def wire(self, p1, p2):
        self.items.append(
            f'  (wire (pts (xy {p1[0]} {p1[1]}) (xy {p2[0]} {p2[1]})) '
            f'(stroke (width 0) (type default)) (uuid {_uuid()}))')

    def text(self, s, x, y):
        esc = s.replace('"', "'")
        self.items.append(f'  (text "{esc}" (at {x} {y} 0) {FONT} (uuid {_uuid()}))')

    def emit(self, paper="A4"):
        libs = "\n".join(self.libsyms.values())
        syms = "\n".join(p.emit(self.project, self.path) for p in self.symbols)
        items = "\n".join(self.items)
        return f"""(kicad_sch (version 20230121) (generator kicad_gen)
  (uuid {self.uuid})
  (paper "{paper}")
  (lib_symbols
{libs}
  )
{items}
{syms}
  (sheet_instances (path "/" (page "1")))
)
"""


_symcache = {}


def get_symbol(lib, name):
    key = (lib, name)
    if key not in _symcache:
        _symcache[key] = Symbol(lib, name)
    return _symcache[key]


def power_symbol(net, ground=False):
    """Synthesize a power-port symbol whose hidden power_in pin carries the
    net name — net naming is then guaranteed by KiCad's global-pin rule,
    independent of power-library Value/pin-name semantics."""
    key = ("LB_PWR", net)
    if key in _symcache:
        return _symcache[key]
    if ground:
        gfx = ("(polyline (pts (xy -1.27 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27)) "
               "(stroke (width 0) (type default)) (fill (type none)))"
               "(polyline (pts (xy 0 0) (xy 0 -1.27)) (stroke (width 0) (type default)) (fill (type none)))")
        val_at = "(at 0 -5.08 0)"
    else:
        gfx = ("(polyline (pts (xy 0 0) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))"
               "(polyline (pts (xy -0.762 1.27) (xy 0.762 1.27) (xy 0 2.54) (xy -0.762 1.27)) "
               "(stroke (width 0) (type default)) (fill (type outline)))")
        val_at = "(at 0 5.08 0)"
    block = f"""(symbol "{net}" (power) (pin_names (offset 0)) (in_bom yes) (on_board yes)
      (property "Reference" "#PWR" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "{net}" {val_at} (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "{net}_0_1"
        {gfx}
      )
      (symbol "{net}_1_1"
        (pin power_in line (at 0 0 90) (length 0) hide (name "{net}" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
      )
    )"""
    _symcache[key] = Symbol("LB_PWR", net, block=block)
    return _symcache[key]
