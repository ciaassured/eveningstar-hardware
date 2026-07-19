#!/usr/bin/env python3

"""Verify that every copper zone has saved fill data on every zone layer."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew  # type: ignore  # pylint: disable=import-error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="check that a KiCad board contains saved copper-zone fills"
    )
    parser.add_argument(
        "board",
        nargs="?",
        default=Path("pcb/EveningStar.kicad_pcb"),
        type=Path,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    board = pcbnew.LoadBoard(str(args.board.resolve()))
    missing_fills: list[str] = []
    copper_zone_count = 0

    for zone in board.Zones():
        if zone.GetIsRuleArea():
            continue

        copper_zone_count += 1
        missing_layers = [
            board.GetLayerName(layer)
            for layer in zone.GetLayerSet().Seq()
            if not zone.HasFilledPolysForLayer(layer)
        ]

        if not zone.IsFilled() or missing_layers:
            net_name = zone.GetNetname() or "<no net>"
            zone_id = zone.m_Uuid.AsString()
            layers = ", ".join(missing_layers) or "all layers"
            missing_fills.append(f"{zone_id} ({net_name}): {layers}")

    if missing_fills:
        print("Copper zones without saved fill data:")
        for missing_fill in missing_fills:
            print(f"  {missing_fill}")
        print()
        print("Open the board in the pinned KiCad PCB Editor, press B to fill all")
        print("zones, save the board, and rerun this check.")
        raise SystemExit(1)

    print(f"All {copper_zone_count} copper zones contain saved fill data.")


if __name__ == "__main__":
    main()
