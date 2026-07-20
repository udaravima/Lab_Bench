# PCB layout guide — placement rules per board

Status of layout work as of 2026-07-19, and per-cluster placement guidance for
hand-layout in KiCad. Net names below are exactly as in the verified netlists
(`check_netlist.py` green on phase-2 and backplane). Pin numbers were verified
against the footprints + netlist, not memory.

## Where each board stands

| Board | Schematic | Netlist check | PCB |
|---|---|---|---|
| phase1-module | done | green | **done** — `phase1-module.kicad_pcb`: placement, pours, planes, critical routes, 0 DRC copper errors; some signal nets unrouted (autoroute.py is WIP) |
| phase2-module | done (hand-arranged) | green (173 comps, 116 nets) | not started — this doc is the placement plan |
| phase3-backplane | done | green (30 comps) | not started |
| phase3-manager | done | not yet re-checked | not started |

Phase-1's board is the reference implementation: open it next to this doc —
every rule below is applied there and visible (input band → FET straddle →
SW island → inductor → output band; the ground seam; the AGND pocket).

---

# Phase-2 module (130 × 90 mm, 4-layer)

## Frame constraints (frozen in MECHANICAL.md)

- **Left edge = backplane edge**: J1 (XT60PW-M power) + J5 (1×08 signal row).
  J1's shroud must overhang the board edge ~2 mm so power mates before signals.
  The two through-hole retention legs (3.8 mm behind the pads) must stay on the
  board — keep the footprint origin ≥ ~4.5 mm inboard.
- **Right edge = front panel**: J4 (XT60PW-M output), shroud overhanging.
- 30 mm slot pitch → component height near the long edges matters less than
  total board+parts thickness; the tall parts (C14 radial, L1/L3, XT60s) are
  all fine, just keep them off the card-guide edges (top/bottom ~3 mm).
- Stackup JLC04161H-7628, 1 oz outer. Bus pours get solder-reinforcement mask
  openings; the 2 oz decision comes only after the thermal soak test.
- 4 × M3 mounting holes in the corners, 3 fiducials.

## XT60 polarity — HARD GATE

In the `labbench:XT60PW-M` footprint, **pad 1 is the pad at (+3.0, +3.6) mm**
in footprint coordinates and pad 2 at (+3.0, −3.6); legs are pads 3/4 at
(−3.0, ∓6.75). J1 pad 1 = VBUS, J1 pad 2 = PGND; J4 pad 1 = VOUT, pad 2 =
PGND. Before gerbers, do the planned continuity check of module J1 against the
backplane's mating XT60PW-F **in the mated orientation** — a mirrored footprint
here reverses supply polarity on every module.

## Layer plan (same as phase-1)

- **F.Cu** — components + the named power pours (below), routed hot loops.
- **In1** — ground planes: PGND under the whole power region, AGND under the
  analog region, split at a seam; AGND *pockets* carved out of PGND (higher
  zone priority) where AGND-referenced ICs must live inside the power region.
- **In2** — logic power: 5V0 and 3V3 zones under their consumers.
- **B.Cu** — ground fills mirroring In1, plus signal routing.
- Planes joined at **one point only**: NT1 (net tie, PGND pad 2 / AGND pad 1).
  Place NT1 on the seam near the output sensing cluster (that is where the
  measurement references matter).

## Power flow and suggested floorplan

Current flows left → right. Suggested arrangement (x→ 0..130, y↓ 0..90):

```
     0        20        40         55        75        95       112      130
  0 ┌──────────────────────────────────────┬─────────────────────────────────┐
    │ J1 ► F1 ► VBUS_FUSED ► R70 ► Q14 ────► VBUS_P │ Q1 ►SW1► L1 ►CS_A► │   │
    │ (XT60)  [D5+C91]   [U12 LM5069 clstr]│ column │ Q2*        R36/R42 │ V │ [U4 C33 R31 C31]
 20 │                                      │ C6-C9  │  (phase A strip)   │ O │ R30/R34 ► VOUT_SW
    │                                      │        ├────────────────────┤ U │ ▼ Q3/Q10
 33 │  [aux: C50 C51 U8 C52 L2 C54 C55]    │ C14    │  U3 + comp cluster │ T │ DISC_SRC  ▼ Q4/Q11
    │  [R50 R51 U9 C56 C57]                │        │  (AGND pocket)     │ _ │ VOUT ► J4 (XT60)
 47 │                                      │ C10-13 ├────────────────────┤ I │
    │                                      │        │ Q13*       R37/R57 │ N │ [U6+C41/42, U5+C34,
 60 │ J5 (1×08 signal row, left edge)      │        │ Q12 ►SW2► L3 ►CS_B │ T │  R32/R33/C32 pocket]
 67 ├────────────── PGND above / AGND below — seam, NT1 star ────────────────┤
    │ [U11+C69/70 CAN]  [U1 DAC, U2 EAs + integrators]  [U10 MCU + Y1]       │
    │ [R60/R61/C62]     [EN cluster, OVP U7/D8, droop U13][I2C R62/R63]      │
 90 └──[J3 UART]────[J6 fan Q8 D6]────[J2 SWD]────[D7+R66 LED]───────────────┘
                                          (* = low-side FET, rotated so its
                                             source leads exit into PGND)
```

Phase B mirrors phase A about the horizontal centerline of the power block so
**both SW islands face U3 in the middle** — gate loops of the two phases come
out symmetric, which is what current sharing wants. VOUT_INT is a vertical
column collecting both phases; the output caps straddle from it into PGND.

## Named F.Cu pours (the power nets that deserve copper areas)

`VBUS` (J1↔F1) → `VBUS_FUSED` (F1, D5, C91, R70.1, R71.1, U12.2) →
`HS_SENSE` (R70.2, Q14 drain tab, U12.1) → `VBUS_P` (Q14 source, C6–C14,
Q1/Q12 drains, R29.1, U8 VIN + C50/C51, R60.1, R75.1) → `SW1`/`SW2` islands
(keep them SMALL — they are the dV/dt antennas) → `PH_CS_A`/`PH_CS_B` sense
islands → `VOUT_INT` → `VOUT_SW` → `DISC_SRC` → `VOUT` (J4).
PGND bands sit adjacent to VBUS_P and VOUT_INT so every decoupling cap
straddles pour-to-pour with near-zero loop.

## Cluster-by-cluster placement rules

### 1. Hot-swap front end (top-left)
- **D5 (SMBJ TVS) + C91** directly at the fused input, shortest possible loop
  into PGND — they only clamp what their inductance lets them see.
- **R70 (1m5 2512 sense)**: U12's pins 1/2 (SENSE across R70) must be routed
  as a Kelvin pair from the *pad edges*, not from the pour. Keep U12 within
  ~10 mm of R70.
- **Q14 (CSD19536, TO-263-2)**: tab = drain = HS_SENSE, pin 1 = gate
  (HS_GATE), pin 3 = source → VBUS_P. Orient so the source lead exits toward
  the VBUS_P region. Give the tab copper — it dissipates during the inrush
  ramp and carries 20+ A afterward.
- **U12 (LM5069) cluster**: C90 (timer) at pin 6; R74 (PLIM) at pin 7;
  R71/R72/R73 UV/OV divider next to pins 3/4 — these are high-impedance
  nodes, keep them away from SW islands and gate traces. R75 (PGD pull-up to
  VBUS_P) near pin 8; HS_PGD also feeds U8 pin 9 (aux buck enable), so route
  it toward the aux cluster.

### 2. Bridges — the hot loops (the most important rule on the board)
- Per phase, the loop **VBUS_P → HS-FET drain → source → SW → LS-FET drain →
  source → PGND → input caps → VBUS_P** must be minimal-area. Put **4 of the
  8 input MLCCs (C6–C13, 1210) hard against each phase's FET pair**, pads
  straddling VBUS_P↔PGND. C14 (radial bulk) sits behind them; it handles the
  low-frequency slug, not the loop.
- SON5×6 FETs (`PowerFET_SON5x6_GDS`): tab = drain (pad 2), gate = corner
  pad 1, sources = pad 3 column on the gate side. HS FET: tab in VBUS_P,
  sources into SW. LS FET: rotate 180° — tab in SW, sources into PGND.
- **SW islands small**: just FET pads, inductor pad, BST cap, snubber pads.
- **BST caps**: C27 (BST_A↔SW1), C35 (BST_B↔SW2) directly between U3 and
  each island.
- **DNP snubber pads** R40/C49 (SW1↔PGND) and R41/C58 (SW2↔PGND) right at
  each LS FET — they are useless 10 mm away.
- Gate drives from U3: G_HS_A (pins 22/23), G_LS_A (18/19), G_HS_B (8/9),
  G_LS_B (12/13) — short, direct, no vias if possible, return path over the
  PGND plane. Keep phase A and B gate lengths similar.

### 3. U3 (LM5143, VQFN-40) orientation and support
Pin sides at footprint rotation 0 (verified from land pattern + netlist):
- **Left column 1–10, top→bottom**: SS(1), COMP2(2), AGND(3), CS2(4),
  VOUT2(5), VCCX(6), NC(7), HOL2(8), HO2(9), SW2(10) — phase B exits the
  bottom-left.
- **Bottom row 11–20, left→right**: BST2(11), LO2(12), LOL2(13), PGND(14),
  VCC(15), VCC(16), PGND(17), LO1(18), LOL1(19), BST1(20).
- **Right column 21–30, bottom→top**: SW1(21), HO1(22), HOL1(23), PGOOD(24),
  VIN(25), VOUT1(26), CS1(27), FB(28), COMP1(29), SS1(30) — phase A exits the
  bottom-right, analog sense mid/upper-right.
- **Top row 31–40, right→left**: EN1(31), RES(32), FPWM(33), VDDA(34),
  AGND(35), VDDA(36), RT(37), DITH(38), SYNCOUT(39, NC), EN2(40).

So: **gate drive and power leave the bottom and lower sides; the quiet analog
(FB/COMP/SS/RT/VDDA/EN) leaves the top.** Place U3 between the two SW islands
with the bottom row facing the FETs, and give the top edge an **AGND pocket**
(In1+B.Cu island carved from PGND) carrying the whole compensation cluster:
- C22/C23 (PS_VCC) tight at pins 15/16 — this is the gate-drive reservoir,
  treat it like a decoupling loop, via straight to PGND.
- C28 (PS_VIN) at pin 25; R29 taps VBUS_P for it.
- C21 + R39 (PS_VDDA RC filter) at pins 34/36, AGND side.
- FB divider R1/R2 + injection R5/R8 at pin 28 — the FB node is the highest
  impedance node on the board; shortest copper wins. Tap VOUT_INT for R1 at
  the sense point (near the shunts), not at a random cap.
- C25/R24/C24 (COMP), C18 (SS), R26 (RT), C20 (DITH), C19 (RES) all inside
  the pocket at their pins.
- RT1/RT2 (NTCs) are AGND-referenced: RT1 goes against a phase LS FET, RT2
  between the inductors; route their signals back along the pocket/AGND.

### 4. Phase current sense (PH_CS_A / PH_CS_B)
- L1.2 → small PH_CS_A island → R36∥R42 (7m5 1206) → VOUT_INT (same for
  L3.2 → PH_CS_B → R37∥R57). The islands must be small and identical between
  phases.
- CS1 (pin 27) and VOUT1 (pin 26) sense across the A shunts; CS2 (4)/VOUT2
  (5) across B. Route each as a tight pair from the shunt pad edges back to
  U3, matched between phases — mismatch here is a current-sharing error.

### 5. Output bank and Kelvin sensing
- VOUT_INT column: polymer C15/C16/C36/C37 + MLCC C38/C40/C45–C48 straddling
  VOUT_INT↔PGND, spread along the column so both phases see them; R27
  (preload 2512) anywhere on the column.
- **R30∥R34 (Kelvin shunts, 2512)**: VOUT_INT → VOUT_SW. The pour rule from
  phase-1 applies: full-connect pours on the current path, but the **sense
  connections leave from the pad inner edges as differential pairs**. Nothing
  else connects between the shunts and the amplifiers.
- **U4 (INA240)** within ~15 mm of the shunts, C33 (5V0) at its supply;
  R31 → C31 forms the I_MEAS filter — place at U4, the filtered signal then
  travels to U2.5/U10.9.
- **U5 (INA228)** sees VOUT, VOUT_SW and I2C — place it with U6 in the
  output-side AGND pocket; C34 (3V3) at its supply pin.

### 6. Disconnect chain (mid-right)
- Two back-to-back pairs in parallel: Q3+Q4, Q10+Q11. Drains of Q3/Q10 in
  VOUT_SW; all four sources meet in DISC_SRC; drains of Q4/Q11 in VOUT.
  Common gate DISC_GATE from U6 pins 6/7.
- **U6 (LTC7004)** close to the four gates; C41 (LTC_BST↔DISC_SRC) at pins
  9/8; C42/C43 (5V0) at pins 1/2. U6 is AGND-referenced (pins 3/5/11) →
  it sits in an AGND pocket, same trick as phase-1.
- DISC_INP parts (R43 from OUT_REQ, R44 pulldown, Q7/Q9 kill transistors) can
  live in the analog region below — the node is slow.

### 7. Output measurement
- **R32/R33 (0.1 % V_MEAS divider)**: R32 taps the VOUT pour **at J4** — the
  point you promise the user — not at the cap bank. C32 at the midpoint.
  V_MEAS feeds U2.3, U13.2 and U10.8; route it along quiet AGND territory.
- VBUS telemetry R60/R61/C62: R60 taps VBUS_P at the column bottom; the
  divider midpoint is high-impedance — C62 right at R61, then to U10.14.

### 8. Aux rails (left column)
- **U8 (LMR36015)**: phase-1 audit SW-003 lesson — **C50/C51 input caps
  immediately at the VIN/PGND pins** (VIN pins 2/10, PGND 1/11), not "nearby".
  L2 at SW (pin 12); C52 (boot) at pin 4; C54/C55 output caps; R50/R51 FB
  divider away from L2's field, close to pin 7.
- **U9 (NCP1117, SOT-223)**: pin 1 GND, pin 2/tab = 3V3 out, pin 3 = 5V0 in.
  C56/C57 at in/out. The whole aux strip is PGND territory.
- Fan: J6 + Q8 + D6 near a board edge (wire exit); D6 flyback directly across
  J6's pins.

### 9. MCU / analog region (below the seam, AGND)
- **U10 (STM32G431, LQFP-48)**: C71–C74 = one 100n per VDD/VSS pair, each at
  its own package corner, < 2 mm, via to 3V3/AGND at the pad. C64/C65 bulk
  at the supply. Never share one cap between two pins.
- **Y1 (8 MHz, 3225)** at pins 5/6 (PF0/PF1), < 5 mm, C66/C67 grounding to a
  local AGND via each; keep the crystal away from SW islands, CAN, and the
  LED trace.
- C68 at NRST (pin 7) next to the package; R65 (BOOT0) at pin 45.
- ADC inputs I_MEAS (9), V_MEAS (8), VBUS_SNS (14), NTC (16/17): route away
  from switching copper; they already have RC filters — put each filter cap
  at the *end* of the run, near U10.
- **U1 (DAC80502)**: C3 at VDD; **C4 (REFIO) < 3 mm from pin 10** — this cap
  is the DAC's noise floor. R3/R6 short runs to U2's inverting inputs.
- **U2 (OPA2333 error amps)**: integrator networks C1/R4/D1 and C2/R7/D2
  tight at pins 1/2 and 6/7 — the inverting nodes are high-impedance; C5 at
  the supply. Keep U1→U2→(EA_V_OUT/EA_I_OUT toward U3's pocket) as one short
  quiet chain.
- EN cluster (Q5/Q6/D3/D4/R19–R23), droop U13+R35+R38, OVP U7+R45/R46/C44 +
  D8/R47 (REF_2V5): logic-speed nodes, group them functionally between the
  MCU and the parts they talk to. R45 taps VOUT_INT at the column bottom.
- **U11 (TCAN1042) near J5**: C69/C70 at supplies; CAN_H/L (J5 pins 1/2) as a
  differential pair straight to the connector, no stubs. R64 (CAN_STB) local.
- J5 pins: 1 CAN_H, 2 CAN_L, 3 HW_EN, 4–6 SLOT_ID0–2, 7/8 PGND.
- Edge row: J3 (UART), J2 (SWD), D7+R66 (status LED) on the bottom edge like
  phase-1.

### 10. Grounding summary (load-bearing, from phase-1)
- One PGND↔AGND tie: **NT1 only**. Everything else keeps the seam.
- AGND pockets inside the power region: (a) U3 compensation cluster,
  (b) U6/U5 output cluster. Pocket = In1 + B.Cu islands at higher zone
  priority, mirrored, stitched with their own vias.
- In2: 5V0 zones under the aux strip, U2/control-core, U4, U6/U5 pocket and
  the OVP/droop cluster; 3V3 under the MCU, DAC, CAN, INA228. A pin in the
  "wrong" zone is fine — route it; don't contort the floorplan for it.

---

# Phase-3 backplane (~330 × 100 mm, 2-layer, 2 oz) — preliminary

- 8 module slots at 30 mm pitch: per slot one **XT60PW-F** (mating check
  against the module male — same HARD GATE) + 1×08 socket, both on the same
  edge, positions must match the module edge geometry exactly. Generate the
  slot positions from one parameterized origin, don't place 8 by hand.
- Bus bars: VBUS and PGND as full-length straight copper bands (2 oz +
  solder reinforcement); feed from the supply entry at one end — size the
  bands for the worst-case slot at the far end. PGND band mirrors on both
  layers, stitched.
- CAN: single linear bus along the slot row, stubs to each slot < 25 mm,
  **120 Ω termination at both physical ends** — one end lives on the manager
  connector side.
- SLOT_ID: per-slot straps/resistors at each socket.
- Keep the manager connector and any supply-sense divider at the same end as
  the supply entry.

# Phase-3 manager (100 × 80 mm, 2-layer) — preliminary

- ESP32-S3 module: antenna edge overhanging or keep-out (no copper under the
  antenna), away from the display/CAN wiring.
- Standard rules: 100n at every supply pin pair + bulk at the module; CAN
  transceiver next to the backplane connector, differential pair, termination
  per the bus plan above; USB connector ESD diodes at the connector; buttons/
  encoder and display connector grouped on the UI edge (see ui.kicad_sch).

---

## Verification workflow while you lay out (unchanged)

The generators for *schematics* are retired (hand-owned files now), but the
checkers still work and should gate the layout:

```bash
cd hardware/phase2-module/tools
kicad-cli sch export netlist -o /tmp/p2.net ../phase2-module.kicad_sch
python3 check_netlist.py /tmp/p2.net        # must stay green while you work
python3 check_footprints.py /tmp/p2.net
# after layout exists:
python3 ../../phase1-module/tools/run_drc.py   # point it at the new .kicad_pcb
```

Before gerbers (from HANDOVER.md, still open):
1. XT60 polarity continuity check, module-vs-backplane mated orientation.
2. Re-verify LCSC stock: LTC7004 (was 5 pcs), CSD19536KTT (was 12 pcs).
