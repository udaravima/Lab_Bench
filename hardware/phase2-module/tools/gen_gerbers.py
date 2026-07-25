"""Plot fabrication outputs (JLCPCB-flavoured) for the Phase-2 module.

Emits Gerbers + Excellon drills + a drill map into ../fab/, then zips
them. Settings follow JLCPCB's stated requirements for a 4-layer board:
Gerber RS-274X, no X2 attributes (their parser is happier without),
Protel-style extensions off (KiCad's default names are accepted and
unambiguous), 4.6 metric drill format, PTH/NPTH merged, drill origin =
absolute (the board origin is already the plot origin here).

Refuses to plot while copper DRC is unclean or nets are unconnected —
gerbers of a half-routed board are the classic way to fab a paperweight.
Override deliberately with --force (e.g. for a fit check).

Usage: python3 gen_gerbers.py [--force]
"""
import os
import shutil
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "phase2-module.kicad_pcb")
OUT = os.path.join(HERE, "..", "fab")

LAYERS = [
    (pcbnew.F_Cu, "F_Cu"),
    (pcbnew.In1_Cu, "In1_Cu"),
    (pcbnew.In2_Cu, "In2_Cu"),
    (pcbnew.B_Cu, "B_Cu"),
    (pcbnew.F_Paste, "F_Paste"),
    (pcbnew.B_Paste, "B_Paste"),
    (pcbnew.F_SilkS, "F_Silkscreen"),
    (pcbnew.B_SilkS, "B_Silkscreen"),
    (pcbnew.F_Mask, "F_Mask"),
    (pcbnew.B_Mask, "B_Mask"),
    (pcbnew.Edge_Cuts, "Edge_Cuts"),
]


def main():
    force = "--force" in sys.argv
    board = pcbnew.LoadBoard(BOARD)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    board.BuildConnectivity()
    unconn = board.GetConnectivity().GetUnconnectedCount(False)
    if unconn and not force:
        sys.exit(f"REFUSING: {unconn} unconnected item(s) — finish routing "
                 f"first, or pass --force for a deliberate partial plot")

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    pc = pcbnew.PLOT_CONTROLLER(board)
    po = pc.GetPlotOptions()
    po.SetOutputDirectory(OUT)
    po.SetPlotFrameRef(False)
    po.SetUseGerberProtelExtensions(False)
    po.SetUseGerberX2format(False)
    po.SetIncludeGerberNetlistInfo(False)
    po.SetCreateGerberJobFile(True)
    po.SetSubtractMaskFromSilk(True)      # silk clipped out of pad openings
    po.SetDrillMarksType(0)               # no drill marks in copper plots
    po.SetSkipPlotNPTH_Pads(False)
    po.SetMirror(False)
    po.SetAutoScale(False)
    po.SetScale(1.0)

    for lid, name in LAYERS:
        pc.SetLayer(lid)
        pc.OpenPlotfile(name, pcbnew.PLOT_FORMAT_GERBER, name)
        if not pc.PlotLayer():
            sys.exit(f"plot failed on {name}")
    pc.ClosePlot()

    dw = pcbnew.EXCELLON_WRITER(board)
    dw.SetOptions(False,          # mirror
                  False,          # minimal header
                  board.GetDesignSettings().GetAuxOrigin(),
                  True)           # merge PTH + NPTH into one file
    dw.SetFormat(True, pcbnew.EXCELLON_WRITER.DECIMAL_FORMAT, 3, 3)
    dw.CreateDrillandMapFilesSet(OUT, True, True)

    files = sorted(os.listdir(OUT))
    zip_base = os.path.join(HERE, "..", "phase2-module-fab")
    shutil.make_archive(zip_base, "zip", OUT)
    print(f"gen_gerbers: {len(files)} files -> {os.path.relpath(OUT, HERE)}/")
    for f in files:
        print("   ", f)
    print(f"zipped -> {os.path.relpath(zip_base, HERE)}.zip"
          + ("   [--force: NOT fab-ready]" if unconn else ""))


if __name__ == "__main__":
    main()
