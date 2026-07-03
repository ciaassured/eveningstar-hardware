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
    snap_lid_gap: float = 0.25
    snap_shoulder_wall: float = 1.8
    snap_shoulder_depth: float = 3.2
    snap_nub_height: float = 2.0
    snap_nub_width: float = 20.0
    snap_nub_position_ratio: float = 0.30
    snap_cavity_width_extra: float = 1.0
    snap_cavity_depth_clearance: float = 0.35
    snap_cavity_z_clearance: float = 0.25
    pcb_reference_marker_height: float = 1.2


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


@dataclass(frozen=True)
class SnapNub:
    side: str
    center_x: float
    width: float


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
    return Point(
        point.x - board.min_x + origin,
        board.min_y + board.height - point.y + origin,
    )


def box_to_case(fp: FootprintBox, board: BoardData, cfg: CaseConfig) -> FootprintBox:
    origin = cfg.wall + cfg.pcb_edge_clearance
    return FootprintBox(
        ref=fp.ref,
        value=fp.value,
        description=fp.description,
        x=fp.x - board.min_x + origin,
        y=board.min_y + board.height - (fp.y + fp.height) + origin,
        width=fp.width,
        height=fp.height,
        center_x=fp.center_x - board.min_x + origin,
        center_y=board.min_y + board.height - fp.center_y + origin,
    )


def make_board_proxy(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    board_bottom_z = cfg.bottom + cfg.board_floor_clearance
    points: list[App.Vector] = []
    for p in board.outline:
        case_point = board_to_case(p, board, cfg)
        points.append(App.Vector(case_point.x, case_point.y, board_bottom_z))
    points.append(points[0])
    board_shape = Part.Face(Part.makePolygon(points)).extrude(App.Vector(0, 0, cfg.pcb_thickness))

    top_z = board_bottom_z + cfg.pcb_thickness
    marker_shapes: list[Part.Shape] = [board_shape]
    for ref in ("RJ1", "J4", "U4", "J2"):
        marker = box_to_case(board.footprints[ref], board, cfg)
        marker_shapes.append(
            Part.makeBox(
                marker.width,
                marker.height,
                cfg.pcb_reference_marker_height,
                App.Vector(marker.x, marker.y, top_z),
            )
        )

    return Part.makeCompound(marker_shapes)


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


def snap_nubs(board: BoardData, cfg: CaseConfig) -> list[SnapNub]:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    x_a = outer_length * cfg.snap_nub_position_ratio
    x_b = outer_length * (1 - cfg.snap_nub_position_ratio)
    return [
        SnapNub("front", x_a, cfg.snap_nub_width),
        SnapNub("front", x_b, cfg.snap_nub_width),
        SnapNub("back", x_a, cfg.snap_nub_width),
        SnapNub("back", x_b, cfg.snap_nub_width),
    ]


def triangular_snap_prism(
    side: str,
    center_x: float,
    width: float,
    side_y: float,
    z_min: float,
    height: float,
    depth: float,
) -> Part.Shape:
    x_min = center_x - width / 2
    z_max = z_min + height
    z_mid = z_min + height / 2
    y_tip = side_y + depth if side == "front" else side_y - depth
    profile = Part.Face(
        Part.makePolygon(
            [
                App.Vector(x_min, side_y, z_min),
                App.Vector(x_min, side_y, z_max),
                App.Vector(x_min, y_tip, z_mid),
                App.Vector(x_min, side_y, z_min),
            ]
        )
    )
    return profile.extrude(App.Vector(width, 0, 0))


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
                -1.0,
                usb_z_min,
            ),
        )
    )

    return cutters


def connector_opening_report(board: BoardData, cfg: CaseConfig) -> dict[str, dict[str, object]]:
    refs = {
        "RJ1": "min_x",
        "J4": "max_x",
        "U4": "max_x",
        "J2": "min_y",
    }
    data: dict[str, dict[str, object]] = {}
    for ref, side in refs.items():
        box = box_to_case(board.footprints[ref], board, cfg)
        data[ref] = {
            "side": side,
            "center_mm": {"x": box.center_x, "y": box.center_y},
            "size_mm": {"x": box.width, "y": box.height},
        }
    return data


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


def make_snapfit_base(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    outer_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)

    base = rounded_box(outer_length, outer_width, cfg.base_height, 0, cfg.outer_fillet)

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

    nub_height = cfg.snap_nub_height
    nub_depth = nub_height / 2
    nub_z = cfg.base_height - cfg.snap_shoulder_depth
    for nub in snap_nubs(board, cfg):
        side_y = cfg.wall if nub.side == "front" else outer_width - cfg.wall
        additions.append(
            triangular_snap_prism(
                nub.side,
                nub.center_x,
                nub.width,
                side_y,
                nub_z,
                nub_height,
                nub_depth,
            )
        )

    base = fuse_all(base, additions)

    cuts: list[Part.Shape] = []
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


def make_snapfit_lid(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    outer_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    z_min = -0.5
    z_height = cfg.lid_thickness + 1.0

    lid = rounded_box(outer_length, outer_width, cfg.lid_thickness, 0, cfg.lid_fillet)

    shoulder_outer_x = cfg.wall + cfg.snap_lid_gap
    shoulder_outer_y = cfg.wall + cfg.snap_lid_gap
    shoulder_outer_length = outer_length - 2 * shoulder_outer_x
    shoulder_outer_width = outer_width - 2 * shoulder_outer_y
    shoulder_outer = Part.makeBox(
        shoulder_outer_length,
        shoulder_outer_width,
        cfg.snap_shoulder_depth,
        App.Vector(shoulder_outer_x, shoulder_outer_y, cfg.lid_thickness),
    )
    shoulder_inner = Part.makeBox(
        shoulder_outer_length - 2 * cfg.snap_shoulder_wall,
        shoulder_outer_width - 2 * cfg.snap_shoulder_wall,
        cfg.snap_shoulder_depth + 1.0,
        App.Vector(
            shoulder_outer_x + cfg.snap_shoulder_wall,
            shoulder_outer_y + cfg.snap_shoulder_wall,
            cfg.lid_thickness - 0.5,
        ),
    )
    shoulder = shoulder_outer.cut(shoulder_inner)
    lid = fuse_all(lid, [shoulder])

    cuts: list[Part.Shape] = []
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

    cavity_height = cfg.snap_nub_height + 2 * cfg.snap_cavity_z_clearance
    cavity_z = cfg.lid_thickness + cfg.snap_shoulder_depth - cavity_height
    cavity_depth = min(
        cfg.snap_nub_height / 2 - cfg.snap_lid_gap + cfg.snap_cavity_depth_clearance,
        cfg.snap_shoulder_wall - 0.2,
    )
    for nub in snap_nubs(board, cfg):
        side_y = shoulder_outer_y if nub.side == "front" else outer_width - shoulder_outer_y
        cuts.append(
            triangular_snap_prism(
                nub.side,
                nub.center_x,
                nub.width + 2 * cfg.snap_cavity_width_extra,
                side_y,
                cavity_z,
                cavity_height,
                cavity_depth,
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
        "connector_openings": connector_opening_report(board, cfg),
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
        "config": {key: value for key, value in asdict(cfg).items() if not key.startswith("snap_")},
    }
    (OUTPUT_DIR / "eveningstar_case_slotfit_report.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_snapfit_report(board: BoardData, cfg: CaseConfig) -> None:
    body_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    body_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    nub_height = cfg.snap_nub_height
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
        "variant": "slot-fit PCB tray with screwless snap-on lid",
        "board_size_mm": {"x": board.width, "y": board.height},
        "case_body_size_mm": {"x": body_length, "y": body_width, "z_base": cfg.base_height},
        "case_overall_size_mm": {"x": body_length, "y": body_width, "z_base": cfg.base_height},
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
        "connector_openings": connector_opening_report(board, cfg),
        "snap_fit_lid": {
            "pattern": "tapered triangular wall nubs engaging matching lid-shoulder recesses",
            "source_references": [
                "https://github.com/dcityorg/boxmaker-fusion",
                "https://formlabs.com/blog/designing-3d-printed-snap-fit-enclosures/",
                "https://github.com/Work-KewalShah/Countdown-Timer-V1",
                "https://github.com/ahmadaziz6720/lenovo_pen_case",
            ],
            "lid_gap_mm": cfg.snap_lid_gap,
            "shoulder_wall_mm": cfg.snap_shoulder_wall,
            "shoulder_depth_mm": cfg.snap_shoulder_depth,
            "nub_height_mm": cfg.snap_nub_height,
            "nub_depth_mm": nub_height / 2,
            "nub_width_mm": cfg.snap_nub_width,
            "nub_z_range_mm": {
                "bottom": cfg.base_height - cfg.snap_shoulder_depth,
                "top": cfg.base_height - cfg.snap_shoulder_depth + cfg.snap_nub_height,
            },
            "nubs": [asdict(nub) for nub in snap_nubs(board, cfg)],
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
    (OUTPUT_DIR / "eveningstar_case_snapfit_report.json").write_text(
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

    snap_base = make_snapfit_base(board, cfg)
    snap_lid = make_snapfit_lid(board, cfg)
    snap_board_proxy = make_board_proxy(board, cfg)
    write_exports(
        snap_base,
        snap_lid,
        snap_board_proxy,
        "eveningstar_case_snapfit",
        "eveningstar_case_snapfit_pcb_reference.step",
    )
    write_snapfit_report(board, cfg)
    App.Console.PrintMessage(f"Wrote enclosure files to {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()
