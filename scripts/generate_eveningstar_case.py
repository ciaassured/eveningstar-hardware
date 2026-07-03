#!/usr/bin/env python3
"""Generate a two-piece EveningStar PCB enclosure with FreeCAD.

Run with:

    bash scripts/generate_eveningstar_case.sh

The script reads mechanical anchors from pcb/EveningStar.kicad_pcb and writes
STEP/STL/FCStd output into mechanical/.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import FreeCAD as App
    import Part
except ImportError as exc:  # pragma: no cover - only hit outside FreeCADCmd
    raise SystemExit("Run this script with FreeCADCmd, not system python.") from exc

try:
    import pcbnew
except ImportError as exc:  # pragma: no cover
    raise SystemExit("KiCad pcbnew Python bindings are required.") from exc


ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "pcb" / "EveningStar.kicad_pcb"
OUTPUT_DIR = ROOT / "mechanical"
SCALE = 1_000_000


@dataclass(frozen=True)
class CaseConfig:
    wall: float = 2.4
    bottom: float = 2.0
    pcb_edge_clearance: float = 0.55
    base_height: float = 23.0
    board_floor_clearance: float = 2.8
    lid_thickness: float = 2.4
    outer_fillet: float = 1.3
    lid_fillet: float = 0.9
    insert_hole_diameter: float = 3.6
    insert_hole_depth: float = 6.0
    screw_clearance_diameter: float = 3.0
    switch_access_diameter: float = 5.0
    led_view_diameter: float = 2.4
    pcb_thickness: float = 1.6
    slot_rail_width: float = 1.4
    slot_rail_end_clearance: float = 14.0
    external_ear_radius: float = 6.2
    external_ear_overlap: float = 2.4
    din_mount_hole_diameter: float = 3.4
    din_mount_hole_spacing: float = 52.5


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class FootprintBox:
    ref: str
    value: str
    description: str
    x: float
    y: float
    width: float
    height: float
    center_x: float
    center_y: float


@dataclass(frozen=True)
class BoardData:
    min_x: float
    min_y: float
    width: float
    height: float
    outline: list[Point]
    footprints: dict[str, FootprintBox]


def mm(value: int | float) -> float:
    return float(value) / SCALE


def point_from_vec(vec: object) -> Point:
    return Point(mm(vec.x), mm(vec.y))


def load_board() -> BoardData:
    board = pcbnew.LoadBoard(str(BOARD_PATH))
    outline: list[Point] = []
    for drawing in board.GetDrawings():
        if drawing.GetLayerName() != "Edge.Cuts" or not hasattr(drawing, "GetPolyShape"):
            continue
        poly = drawing.GetPolyShape()
        if poly.OutlineCount() < 1:
            continue
        ring = poly.Outline(0)
        outline = [point_from_vec(ring.CPoint(i)) for i in range(ring.PointCount())]
        break

    if not outline:
        raise RuntimeError(f"Could not find an Edge.Cuts polygon in {BOARD_PATH}")

    min_x = min(p.x for p in outline)
    min_y = min(p.y for p in outline)
    max_x = max(p.x for p in outline)
    max_y = max(p.y for p in outline)
    width = max_x - min_x
    height = max_y - min_y

    footprints: dict[str, FootprintBox] = {}
    for fp in board.GetFootprints():
        ref = str(fp.GetReference())
        value = str(fp.GetValue())
        description = ""
        try:
            description = str(fp.GetFieldText("Description"))
        except Exception:
            pass

        box = fp.GetBoundingBox(False, False)
        fp_box = FootprintBox(
            ref=ref,
            value=value,
            description=description,
            x=mm(box.GetX()),
            y=mm(box.GetY()),
            width=mm(box.GetWidth()),
            height=mm(box.GetHeight()),
            center_x=mm(box.GetX() + box.GetWidth() / 2),
            center_y=mm(box.GetY() + box.GetHeight() / 2),
        )
        footprints[ref] = fp_box

    return BoardData(
        min_x=min_x,
        min_y=min_y,
        width=width,
        height=height,
        outline=outline,
        footprints=footprints,
    )


def rounded_box(length: float, width: float, height: float, z: float, radius: float) -> Part.Shape:
    shape = Part.makeBox(length, width, height, App.Vector(0, 0, z))
    if radius <= 0:
        return shape
    try:
        return shape.makeFillet(radius, shape.Edges)
    except Exception:
        return shape


def tidy(shape: Part.Shape) -> Part.Shape:
    try:
        shape = shape.removeSplitter()
    except Exception:
        pass
    if not shape.isValid():
        raise RuntimeError("Generated an invalid FreeCAD shape")
    return shape


def fuse_all(shape: Part.Shape, additions: list[Part.Shape]) -> Part.Shape:
    if not additions:
        return tidy(shape)
    result = shape
    for addition in additions:
        result = result.fuse(addition)
    return tidy(result)


def cut_all(shape: Part.Shape, cutters: list[Part.Shape]) -> Part.Shape:
    result = shape
    for cutter in cutters:
        result = result.cut(cutter)
    return tidy(result)


def vertical_cylinder(
    x: float,
    y: float,
    radius: float,
    height: float,
    z: float,
) -> Part.Shape:
    return Part.makeCylinder(radius, height, App.Vector(x, y, z), App.Vector(0, 0, 1))


def board_to_case(point: Point, board: BoardData, cfg: CaseConfig) -> Point:
    origin = cfg.wall + cfg.pcb_edge_clearance
    return Point(point.x - board.min_x + origin, point.y - board.min_y + origin)


def box_to_case(fp: FootprintBox, board: BoardData, cfg: CaseConfig) -> FootprintBox:
    origin = cfg.wall + cfg.pcb_edge_clearance
    return FootprintBox(
        ref=fp.ref,
        value=fp.value,
        description=fp.description,
        x=fp.x - board.min_x + origin,
        y=fp.y - board.min_y + origin,
        width=fp.width,
        height=fp.height,
        center_x=fp.center_x - board.min_x + origin,
        center_y=fp.center_y - board.min_y + origin,
    )


def make_board_proxy(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    board_bottom_z = cfg.bottom + cfg.board_floor_clearance
    points = [
        App.Vector(
            p.x - board.min_x + cfg.wall + cfg.pcb_edge_clearance,
            p.y - board.min_y + cfg.wall + cfg.pcb_edge_clearance,
            board_bottom_z,
        )
        for p in board.outline
    ]
    points.append(points[0])
    return Part.Face(Part.makePolygon(points)).extrude(App.Vector(0, 0, cfg.pcb_thickness))


def external_insert_positions(board: BoardData, cfg: CaseConfig) -> list[Point]:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    outer_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    x_left = cfg.external_ear_radius + 8.0
    x_right = outer_length - x_left
    y_offset = cfg.external_ear_radius - cfg.external_ear_overlap
    return [
        Point(x_left, -y_offset),
        Point(x_right, -y_offset),
        Point(x_left, outer_width + y_offset),
        Point(x_right, outer_width + y_offset),
    ]


def din_mount_positions(board: BoardData, cfg: CaseConfig) -> list[Point]:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    outer_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    x_center = outer_length / 2
    y_center = outer_width / 2
    half_spacing = cfg.din_mount_hole_spacing / 2
    return [
        Point(x_center - half_spacing, y_center),
        Point(x_center + half_spacing, y_center),
    ]


def side_cutout_boxes(
    board: BoardData,
    cfg: CaseConfig,
    outer_length: float,
    outer_width: float,
) -> list[Part.Shape]:
    cutters: list[Part.Shape] = []
    z_min = cfg.bottom + 0.2
    z_max = cfg.base_height + 0.6
    z_size = z_max - z_min
    wall_cut = cfg.wall + cfg.pcb_edge_clearance + 2.0

    rj11 = box_to_case(board.footprints["RJ1"], board, cfg)
    cutters.append(
        Part.makeBox(
            wall_cut,
            rj11.height + 3.0,
            z_size,
            App.Vector(-1.0, rj11.center_y - (rj11.height + 3.0) / 2, z_min),
        )
    )

    rj45 = box_to_case(board.footprints["J4"], board, cfg)
    cutters.append(
        Part.makeBox(
            wall_cut,
            rj45.height + 3.0,
            z_size,
            App.Vector(
                outer_length - cfg.wall - cfg.pcb_edge_clearance,
                rj45.center_y - (rj45.height + 3.0) / 2,
                z_min,
            ),
        )
    )

    barrel = box_to_case(board.footprints["U4"], board, cfg)
    cutters.append(
        Part.makeBox(
            wall_cut,
            barrel.height + 3.0,
            z_size,
            App.Vector(
                outer_length - cfg.wall - cfg.pcb_edge_clearance,
                barrel.center_y - (barrel.height + 3.0) / 2,
                z_min,
            ),
        )
    )

    usb = box_to_case(board.footprints["J2"], board, cfg)
    usb_z_min = cfg.bottom + cfg.board_floor_clearance
    cutters.append(
        Part.makeBox(
            usb.width + 4.0,
            wall_cut,
            z_max - usb_z_min,
            App.Vector(
                usb.center_x - (usb.width + 4.0) / 2,
                outer_width - cfg.wall - cfg.pcb_edge_clearance,
                usb_z_min,
            ),
        )
    )

    return cutters


def make_slotfit_base(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    outer_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)

    body = rounded_box(outer_length, outer_width, cfg.base_height, 0, cfg.outer_fillet)
    ears = [
        vertical_cylinder(pos.x, pos.y, cfg.external_ear_radius, cfg.base_height, 0)
        for pos in external_insert_positions(board, cfg)
    ]
    base = fuse_all(body, ears)

    inner = Part.makeBox(
        outer_length - 2 * cfg.wall,
        outer_width - 2 * cfg.wall,
        cfg.base_height - cfg.bottom + 1.0,
        App.Vector(cfg.wall, cfg.wall, cfg.bottom),
    )
    base = base.cut(inner)

    origin = cfg.wall + cfg.pcb_edge_clearance
    rail_z = cfg.bottom
    rail_height = cfg.board_floor_clearance
    rail_length = board.width - 2 * cfg.slot_rail_end_clearance
    rail_depth = cfg.slot_rail_width + cfg.pcb_edge_clearance
    additions: list[Part.Shape] = []
    if rail_length > 0:
        additions.extend(
            [
                Part.makeBox(
                    rail_length,
                    rail_depth,
                    rail_height,
                    App.Vector(
                        origin + cfg.slot_rail_end_clearance,
                        origin - cfg.pcb_edge_clearance,
                        rail_z,
                    ),
                ),
                Part.makeBox(
                    rail_length,
                    rail_depth,
                    rail_height,
                    App.Vector(
                        origin + cfg.slot_rail_end_clearance,
                        origin + board.height - cfg.slot_rail_width,
                        rail_z,
                    ),
                ),
            ]
        )

    base = fuse_all(base, additions)

    cuts: list[Part.Shape] = []
    for pos in external_insert_positions(board, cfg):
        cuts.append(
            vertical_cylinder(
                pos.x,
                pos.y,
                cfg.insert_hole_diameter / 2,
                cfg.insert_hole_depth + 0.5,
                cfg.base_height - cfg.insert_hole_depth,
            )
        )

    for pos in din_mount_positions(board, cfg):
        cuts.append(
            vertical_cylinder(
                pos.x,
                pos.y,
                cfg.din_mount_hole_diameter / 2,
                cfg.bottom + 1.0,
                -0.5,
            )
        )

    cuts.extend(side_cutout_boxes(board, cfg, outer_length, outer_width))
    return cut_all(base, cuts)


def make_slotfit_lid(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    outer_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    z_min = -0.5
    z_height = cfg.lid_thickness + 1.0

    body = rounded_box(outer_length, outer_width, cfg.lid_thickness, 0, cfg.lid_fillet)
    ears = [
        vertical_cylinder(pos.x, pos.y, cfg.external_ear_radius, cfg.lid_thickness, 0)
        for pos in external_insert_positions(board, cfg)
    ]
    lid = fuse_all(body, ears)

    cuts: list[Part.Shape] = []
    for pos in external_insert_positions(board, cfg):
        cuts.append(
            vertical_cylinder(
                pos.x,
                pos.y,
                cfg.screw_clearance_diameter / 2,
                z_height,
                z_min,
            )
        )

    for ref in ("S1", "S2", "S3"):
        fp = board.footprints[ref]
        pos = board_to_case(Point(fp.center_x, fp.center_y), board, cfg)
        cuts.append(
            vertical_cylinder(
                pos.x,
                pos.y,
                cfg.switch_access_diameter / 2,
                z_height,
                z_min,
            )
        )

    for ref in ("D4", "D6", "D12"):
        fp = board.footprints[ref]
        pos = board_to_case(Point(fp.center_x, fp.center_y), board, cfg)
        cuts.append(
            vertical_cylinder(
                pos.x,
                pos.y,
                cfg.led_view_diameter / 2,
                z_height,
                z_min,
            )
        )

    return cut_all(lid, cuts)


def add_object(doc: App.Document, name: str, shape: Part.Shape) -> object:
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    return obj


def write_exports(
    base: Part.Shape,
    lid: Part.Shape,
    board_proxy: Part.Shape,
    prefix: str,
    pcb_reference_name: str,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument(prefix)
    add_object(doc, "base", base)
    lid_obj = add_object(doc, "lid", lid)
    lid_obj.Placement.Base = App.Vector(0, 76, 0)
    board_obj = add_object(doc, "pcb_reference", board_proxy)
    board_obj.Placement.Base = App.Vector(0, 0, 0)
    doc.recompute()
    fcstd_path = OUTPUT_DIR / f"{prefix}.FCStd"
    if fcstd_path.exists():
        fcstd_path.unlink()
    doc.saveAs(str(fcstd_path))

    base.exportStep(str(OUTPUT_DIR / f"{prefix}_base.step"))
    lid.exportStep(str(OUTPUT_DIR / f"{prefix}_lid.step"))
    board_proxy.exportStep(str(OUTPUT_DIR / pcb_reference_name))

    base.exportStl(str(OUTPUT_DIR / f"{prefix}_base.stl"))
    lid.exportStl(str(OUTPUT_DIR / f"{prefix}_lid.stl"))


def write_slotfit_report(board: BoardData, cfg: CaseConfig) -> None:
    body_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    body_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    y_offset = cfg.external_ear_radius - cfg.external_ear_overlap
    switch_refs = {
        ref: {
            "label": board.footprints[ref].description,
            "case_position_mm": asdict(board_to_case(Point(board.footprints[ref].center_x, board.footprints[ref].center_y), board, cfg)),
            "hole_diameter_mm": cfg.switch_access_diameter,
        }
        for ref in ("S1", "S2", "S3")
    }
    led_refs = {
        ref: {
            "label": board.footprints[ref].value,
            "case_position_mm": asdict(board_to_case(Point(board.footprints[ref].center_x, board.footprints[ref].center_y), board, cfg)),
            "hole_diameter_mm": cfg.led_view_diameter,
        }
        for ref in ("D4", "D6", "D12")
    }
    data = {
        "source_board": str(BOARD_PATH.relative_to(ROOT)),
        "variant": "slot-fit PCB tray with external lid screws",
        "board_size_mm": {"x": board.width, "y": board.height},
        "case_body_size_mm": {"x": body_length, "y": body_width, "z_base": cfg.base_height},
        "case_overall_size_mm": {
            "x": body_length,
            "y": body_width + 2 * y_offset + 2 * cfg.external_ear_radius,
            "z_base": cfg.base_height,
        },
        "slot_fit": {
            "bottom_protrusion_allowance_mm": cfg.board_floor_clearance,
            "board_bottom_z_mm": cfg.bottom + cfg.board_floor_clearance,
            "pcb_edge_clearance_mm": cfg.pcb_edge_clearance,
            "rail_width_mm": cfg.slot_rail_width,
            "rail_height_mm": cfg.board_floor_clearance,
            "rail_bottom_z_mm": cfg.bottom,
            "rail_top_z_mm": cfg.bottom + cfg.board_floor_clearance,
            "usb_c_slot_bottom_z_mm": cfg.bottom + cfg.board_floor_clearance,
        },
        "threaded_insert": {
            "intended_size": "M2.5 heat-set insert in external ears",
            "base_pilot_hole_diameter_mm": cfg.insert_hole_diameter,
            "base_pilot_hole_depth_mm": cfg.insert_hole_depth,
            "lid_screw_clearance_diameter_mm": cfg.screw_clearance_diameter,
            "positions_mm": [asdict(pos) for pos in external_insert_positions(board, cfg)],
        },
        "din_rail_mount": {
            "source_model": "mechanical/din-rail-bracket-heat-insert-version.step",
            "intended_screw": "M3 clearance through case bottom into bracket heat-set inserts",
            "bracket_insert_pitch_mm": cfg.din_mount_hole_spacing,
            "case_hole_diameter_mm": cfg.din_mount_hole_diameter,
            "case_hole_positions_mm": [asdict(pos) for pos in din_mount_positions(board, cfg)],
        },
        "switch_access_holes": switch_refs,
        "led_view_holes": led_refs,
        "config": asdict(cfg),
    }
    (OUTPUT_DIR / "eveningstar_case_slotfit_report.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    board = load_board()
    cfg = CaseConfig()
    slot_base = make_slotfit_base(board, cfg)
    slot_lid = make_slotfit_lid(board, cfg)
    slot_board_proxy = make_board_proxy(board, cfg)
    write_exports(
        slot_base,
        slot_lid,
        slot_board_proxy,
        "eveningstar_case_slotfit",
        "eveningstar_case_slotfit_pcb_reference.step",
    )
    write_slotfit_report(board, cfg)
    App.Console.PrintMessage(f"Wrote enclosure files to {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()
