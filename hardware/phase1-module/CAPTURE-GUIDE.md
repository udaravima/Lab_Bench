# Phase-1 Module — KiCad Capture Guide

Companion to [docs/06-phase1-circuit-design.md](../../docs/06-phase1-circuit-design.md)
(all component values live there — this file is structure, naming, and checklists
for drawing the schematic).

## Suggested hierarchical sheets

| Sheet | Contents | Reused in Phase 2? |
|---|---|---|
| `power-stage` | LM5145, FETs, L, C_in/C_out, RT/ILIM/SS parts, snubber footprint | Replaced (LM5143 2-phase) |
| `control-core` | Base divider, both EAs + Type-II parts, BAT54 diode-OR, R_inj, DAC80502 | **Yes — draw carefully** |
| `sensing` | Shunt, INA240A3 + output RC, INA228, measurement divider + ADC buffer | **Yes** |
| `disconnect` | Back-to-back FETs, LTC7004, TLV7011 OVP comparator | **Yes** |
| `aux-rails` | TPS54202 5 V, 3.3 V LDO | **Yes** |
| `mcu-can` | STM32G431CBT6, TCAN1042, SWD + UART headers, slot straps, NTC inputs, LED | **Yes** |
| `io` | Power terminals, backplane/bench connector, test points, preload | Adapted |

Draw `control-core`, `sensing`, `disconnect`, `aux-rails`, `mcu-can` as reusable
hierarchical sheets — Phase 2 swaps only `power-stage` and `io`.

## Net naming (match these exactly — firmware/docs use them)

| Net | Meaning |
|---|---|
| `VBUS` / `PGND` | Input bus and power ground |
| `SW` | Switch node |
| `VOUT_INT` | Post-LC, before shunt |
| `VOUT` | After shunt + disconnect FETs = output terminal |
| `VOUT_SNS` | Kelvin sense tap at the terminals (feeds measurement divider + INA228) |
| `FB` | LM5145 feedback node (base divider + both injections land here) |
| `EA_V_OUT`, `EA_I_OUT` | Error-amp outputs (before diodes) |
| `V_MEAS`, `I_MEAS` | 0–2.5 V / 0–1.6 V scaled measurements (EAs + MCU ADC) |
| `V_REF`, `I_REF` | DAC outputs |
| `5V0`, `3V3`, `AGND` | Aux rails; AGND is the quiet analog ground island |
| `/HW_EN` | Backplane enable (active high = run) |
| `CAN_H`, `CAN_L` | Bus |
| `NTC_FET`, `NTC_IND` | Thermistor dividers |
| `DEM`, `OUT_REQ`, `DROOP_EN` | MCU GPIO controls |

## Grounding plan (decide before drawing, not during layout)

- `PGND`: switching currents — FET loop, C_in, C_out, shunt.
- `AGND`: DAC, EAs, INA240/INA228 grounds, measurement divider bottom.
- Single tie point `PGND↔AGND` **at the shunt's Kelvin ground pad** — that makes
  the shunt the common reference for both regulation and telemetry.
- LM5145 analog pins (RT, SS, COMP side) per its datasheet grounding note.

## ERC / review checklist before ordering

- [ ] Every EA output reaches FB only through diode + R_inj (no DC path around the diode).
- [ ] Measurement divider taps `VOUT_SNS`, not `VOUT_INT` (shunt + FET drop must be inside the loop).
- [ ] INA240 input pins Kelvin to the shunt pads (dedicated tracks, no plane sharing).
- [ ] DAC power-on state = 0 V verified against DAC80502 config pins.
- [ ] TLV7011 OVP threshold divider from `VOUT_INT` (protects even with FETs closed → check both tap options and pick at review).
- [ ] /HW_EN gates LM5145 EN *and* LTC7004 enable in hardware (MCU GPIO is OR'd in, cannot override).
- [ ] All five loop test points + the two 10 Ω FRA injection breaks present.
- [ ] NTCs physically placed at FET drain copper and inductor pad (note on schematic for layout).
- [ ] Preload 2.2 kΩ / 1 W across `VOUT`.
- [ ] TVS on `VBUS` at the connector; reverse-polarity note (bench harness is keyed).
- [ ] Every IC: 100 nF decoupler per supply pin + bulk per rail.
- [ ] Footprints double-checked against ordered package variants (RGY/PWP/DGK etc.).

## Layout notes to carry forward

1. FET half-bridge + C_in loop as tight as physically possible (first priority).
2. Shunt Kelvin routing before anything else on the output side.
3. AGND island under the analog corner, stitched at the single tie point only.
4. SW node copper small (EMI) but thick (current); snubber right at the low-side FET.
5. Gate-drive traces short, over solid ground.
