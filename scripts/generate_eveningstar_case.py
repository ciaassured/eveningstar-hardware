#!/usr/bin/env python3
"""Generate a two-piece EveningStar PCB enclosure with FreeCAD.

Run with:

    bash scripts/generate_eveningstar_case.sh

The script reads mechanical anchors from pcb/EveningStar.kicad_pcb and writes
STEP/STL/FCStd output into mechanical/.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, replace
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
    low_profile_base_height: float = 10.6
    tall_component_cutout_clearance: float = 1.2
    sensor_air_hole_diameter: float = 8.0
    sensor_side_window_width: float = 10.0
    sensor_side_window_height: float = 4.5
    sensor_side_window_inner_reach: float = 5.5
    skeleton_perimeter_keepout: float = 6.2
    skeleton_min_rib_width: float = 2.8
    skeleton_base_cell_length: float = 24.0
    skeleton_base_cell_width: float = 7.0
    skeleton_lid_cell_length: float = 24.0
    skeleton_lid_cell_width: float = 7.0
    skeleton_cell_chamfer_ratio: float = 0.5
    skeleton_feature_keepout: float = 3.2
    skeleton_din_pad_radius: float = 9.0


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


TALL_COMPONENT_CUTOUT_REFS = {
    "J3": "programming header",
    "J1": "3V3 power jumper",
    "RJ1": "RJ12 MeterBus jack",
    "J4": "Ethernet jack",
    "U4": "barrel jack",
}


LOW_PROFILE_CONFIG_KEYS = {
    "low_profile_base_height",
    "tall_component_cutout_clearance",
    "sensor_air_hole_diameter",
    "sensor_side_window_width",
    "sensor_side_window_height",
    "sensor_side_window_inner_reach",
}


SKELETON_CONFIG_KEYS = {
    "skeleton_perimeter_keepout",
    "skeleton_min_rib_width",
    "skeleton_base_cell_length",
    "skeleton_base_cell_width",
    "skeleton_lid_cell_length",
    "skeleton_lid_cell_width",
    "skeleton_cell_chamfer_ratio",
    "skeleton_feature_keepout",
    "skeleton_din_pad_radius",
}


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


def config_report(
    cfg: CaseConfig,
    exclude_prefixes: tuple[str, ...] = (),
    exclude_keys: set[str] | None = None,
) -> dict[str, float]:
    excluded = exclude_keys or set()
    return {
        key: value
        for key, value in asdict(cfg).items()
        if key not in excluded and not key.startswith(exclude_prefixes)
    }


def vertical_cylinder(
    x: float,
    y: float,
    radius: float,
    height: float,
    z: float,
) -> Part.Shape:
    return Part.makeCylinder(radius, height, App.Vector(x, y, z), App.Vector(0, 0, 1))


Rect = tuple[float, float, float, float]


def rect_intersects(a: Rect, b: Rect) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def padded_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    pad: float,
) -> Rect:
    return (
        x - width / 2 - pad,
        y - height / 2 - pad,
        x + width / 2 + pad,
        y + height / 2 + pad,
    )


def grid_centers(
    min_value: float,
    max_value: float,
    item_size: float,
    pitch: float,
) -> list[float]:
    usable = max_value - min_value
    if usable < item_size:
        return []
    count = math.floor((usable - item_size) / pitch) + 1
    first = (min_value + max_value) / 2 - pitch * (count - 1) / 2
    return [first + pitch * index for index in range(count)]


def faceted_lattice_cell_x(
    center_x: float,
    center_y: float,
    length: float,
    width: float,
    chamfer_ratio: float,
    height: float,
    z: float,
) -> Part.Shape:
    half_length = length / 2
    half_width = width / 2
    chamfer = min(width * chamfer_ratio, length / 3)
    points = [
        App.Vector(center_x - half_length + chamfer, center_y - half_width, z),
        App.Vector(center_x + half_length - chamfer, center_y - half_width, z),
        App.Vector(center_x + half_length, center_y, z),
        App.Vector(center_x + half_length - chamfer, center_y + half_width, z),
        App.Vector(center_x - half_length + chamfer, center_y + half_width, z),
        App.Vector(center_x - half_length, center_y, z),
    ]
    points.append(points[0])
    return Part.Face(Part.makePolygon(points)).extrude(App.Vector(0, 0, height))


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


def board_top_z(cfg: CaseConfig) -> float:
    return cfg.bottom + cfg.board_floor_clearance + cfg.pcb_thickness


def footprint_lid_cutout(
    board: BoardData,
    cfg: CaseConfig,
    ref: str,
    clearance: float,
    z_min: float,
    z_height: float,
) -> Part.Shape:
    fp = box_to_case(board.footprints[ref], board, cfg)
    return Part.makeBox(
        fp.width + 2 * clearance,
        fp.height + 2 * clearance,
        z_height,
        App.Vector(fp.x - clearance, fp.y - clearance, z_min),
    )


def low_profile_lid_cutouts(
    board: BoardData,
    cfg: CaseConfig,
    z_min: float,
    z_height: float,
) -> list[Part.Shape]:
    cuts = [
        footprint_lid_cutout(
            board,
            cfg,
            ref,
            cfg.tall_component_cutout_clearance,
            z_min,
            z_height,
        )
        for ref in TALL_COMPONENT_CUTOUT_REFS
    ]

    sensor = box_to_case(board.footprints["U6"], board, cfg)
    cuts.append(
        vertical_cylinder(
            sensor.center_x,
            sensor.center_y,
            cfg.sensor_air_hole_diameter / 2,
            z_height,
            z_min,
        )
    )

    sensor_slot_width = max(cfg.sensor_side_window_width, sensor.width + 2.0)
    cuts.append(
        Part.makeBox(
            sensor_slot_width,
            sensor.center_y + cfg.sensor_side_window_inner_reach + 1.0,
            z_height,
            App.Vector(
                sensor.center_x - sensor_slot_width / 2,
                -1.0,
                z_min,
            ),
        )
    )
    return cuts


def sensor_side_window_cutouts(
    board: BoardData,
    cfg: CaseConfig,
) -> list[Part.Shape]:
    sensor = box_to_case(board.footprints["U6"], board, cfg)
    window_width = max(cfg.sensor_side_window_width, sensor.width + 2.0)
    z_min = board_top_z(cfg) - 0.2
    return [
        Part.makeBox(
            window_width,
            sensor.center_y + cfg.sensor_side_window_inner_reach + 1.0,
            cfg.sensor_side_window_height,
            App.Vector(
                sensor.center_x - window_width / 2,
                -1.0,
                z_min,
            ),
        )
    ]


def skeleton_lattice_cutouts(
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
    cell_length: float,
    cell_width: float,
    rib_width: float,
    chamfer_ratio: float,
    keepouts: list[Rect],
    z_min: float,
    z_height: float,
) -> list[Part.Shape]:
    cutters: list[Part.Shape] = []
    y_centers = grid_centers(min_y, max_y, cell_width, cell_width + rib_width)
    min_cell_length = max(cell_width * 1.6, cell_width + rib_width)
    for y in y_centers:
        row_min_y = y - cell_width / 2
        row_max_y = y + cell_width / 2
        blocked: list[tuple[float, float]] = []
        for keepout in keepouts:
            if keepout[3] <= row_min_y or keepout[1] >= row_max_y:
                continue
            blocked.append((max(min_x, keepout[0]), min(max_x, keepout[2])))

        merged: list[tuple[float, float]] = []
        for start, end in sorted(blocked):
            if end <= start:
                continue
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))

        free_ranges: list[tuple[float, float]] = []
        cursor = min_x
        for start, end in merged:
            if start - cursor >= min_cell_length:
                free_ranges.append((cursor, start))
            cursor = max(cursor, end)
        if max_x - cursor >= min_cell_length:
            free_ranges.append((cursor, max_x))

        for start, end in free_ranges:
            available = end - start
            target_span = cell_length * 1.4
            count = max(1, math.ceil(available / target_span))
            while count > 1 and (available - rib_width * (count - 1)) / count < min_cell_length:
                count -= 1
            length = min(cell_length, (available - rib_width * (count - 1)) / count)
            used = count * length + (count - 1) * rib_width
            center = start + (available - used) / 2 + length / 2
            for index in range(count):
                cutters.append(
                    faceted_lattice_cell_x(
                        center + index * (length + rib_width),
                        y,
                        length,
                        cell_width,
                        chamfer_ratio,
                        z_height,
                        z_min,
                    )
                )
    return cutters


def skeleton_base_floor_cutouts(board: BoardData, cfg: CaseConfig) -> list[Part.Shape]:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    outer_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    keepouts = [
        padded_rect(
            pos.x,
            pos.y,
            2 * cfg.skeleton_din_pad_radius,
            2 * cfg.skeleton_din_pad_radius,
            0,
        )
        for pos in din_mount_positions(board, cfg)
    ]
    return skeleton_lattice_cutouts(
        cfg.skeleton_perimeter_keepout,
        outer_length - cfg.skeleton_perimeter_keepout,
        cfg.skeleton_perimeter_keepout,
        outer_width - cfg.skeleton_perimeter_keepout,
        cfg.skeleton_base_cell_length,
        cfg.skeleton_base_cell_width,
        cfg.skeleton_min_rib_width,
        cfg.skeleton_cell_chamfer_ratio,
        keepouts,
        -0.5,
        cfg.bottom + 1.0,
    )


def skeleton_lid_keepouts(board: BoardData, cfg: CaseConfig) -> list[Rect]:
    keepouts: list[Rect] = []
    pad = cfg.skeleton_feature_keepout

    for ref in ("S1", "S2", "S3"):
        fp = board.footprints[ref]
        pos = board_to_case(Point(fp.center_x, fp.center_y), board, cfg)
        keepouts.append(
            padded_rect(
                pos.x,
                pos.y,
                cfg.switch_access_diameter,
                cfg.switch_access_diameter,
                pad,
            )
        )

    for ref in ("D4", "D6", "D12"):
        fp = board.footprints[ref]
        pos = board_to_case(Point(fp.center_x, fp.center_y), board, cfg)
        keepouts.append(
            padded_rect(
                pos.x,
                pos.y,
                cfg.led_view_diameter,
                cfg.led_view_diameter,
                pad,
            )
        )

    for ref in TALL_COMPONENT_CUTOUT_REFS:
        fp = box_to_case(board.footprints[ref], board, cfg)
        clearance = cfg.tall_component_cutout_clearance
        keepouts.append(
            padded_rect(
                fp.center_x,
                fp.center_y,
                fp.width + 2 * clearance,
                fp.height + 2 * clearance,
                pad,
            )
        )

    sensor = box_to_case(board.footprints["U6"], board, cfg)
    sensor_slot_width = max(cfg.sensor_side_window_width, sensor.width + 2.0)
    keepouts.append(
        padded_rect(
            sensor.center_x,
            sensor.center_y,
            cfg.sensor_air_hole_diameter,
            cfg.sensor_air_hole_diameter,
            pad,
        )
    )
    keepouts.append(
        (
            sensor.center_x - sensor_slot_width / 2 - pad,
            -pad,
            sensor.center_x + sensor_slot_width / 2 + pad,
            sensor.center_y + cfg.sensor_side_window_inner_reach + pad,
        )
    )
    return keepouts


def skeleton_lid_cutouts(board: BoardData, cfg: CaseConfig) -> list[Part.Shape]:
    outer_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    outer_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    return skeleton_lattice_cutouts(
        cfg.skeleton_perimeter_keepout,
        outer_length - cfg.skeleton_perimeter_keepout,
        cfg.skeleton_perimeter_keepout,
        outer_width - cfg.skeleton_perimeter_keepout,
        cfg.skeleton_lid_cell_length,
        cfg.skeleton_lid_cell_width,
        cfg.skeleton_min_rib_width,
        cfg.skeleton_cell_chamfer_ratio,
        skeleton_lid_keepouts(board, cfg),
        -0.5,
        cfg.lid_thickness + 1.0,
    )


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


def make_lowprofile_snapfit_base(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    base = make_snapfit_base(board, cfg)
    return cut_all(base, sensor_side_window_cutouts(board, cfg))


def make_lowprofile_snapfit_lid(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    lid = make_snapfit_lid(board, cfg)
    z_min = -0.5
    z_height = cfg.lid_thickness + cfg.snap_shoulder_depth + 1.0
    return cut_all(lid, low_profile_lid_cutouts(board, cfg, z_min, z_height))


def make_skeletonized_lowprofile_base(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    base = make_lowprofile_snapfit_base(board, cfg)
    return cut_all(base, skeleton_base_floor_cutouts(board, cfg))


def make_skeletonized_lowprofile_lid(board: BoardData, cfg: CaseConfig) -> Part.Shape:
    lid = make_lowprofile_snapfit_lid(board, cfg)
    return cut_all(lid, skeleton_lid_cutouts(board, cfg))


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
        "config": config_report(
            cfg,
            exclude_prefixes=("snap_",),
            exclude_keys=LOW_PROFILE_CONFIG_KEYS | SKELETON_CONFIG_KEYS,
        ),
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
        "config": config_report(
            cfg,
            exclude_keys=LOW_PROFILE_CONFIG_KEYS | SKELETON_CONFIG_KEYS,
        ),
    }
    (OUTPUT_DIR / "eveningstar_case_snapfit_report.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_lowprofile_report(
    board: BoardData,
    cfg: CaseConfig,
    standard_cfg: CaseConfig,
) -> None:
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
    top_pass_throughs = {}
    for ref, label in TALL_COMPONENT_CUTOUT_REFS.items():
        fp = box_to_case(board.footprints[ref], board, cfg)
        clearance = cfg.tall_component_cutout_clearance
        top_pass_throughs[ref] = {
            "label": label,
            "case_position_mm": {"x": fp.center_x, "y": fp.center_y},
            "opening_size_mm": {
                "x": fp.width + 2 * clearance,
                "y": fp.height + 2 * clearance,
            },
            "clearance_per_side_mm": clearance,
        }

    sensor = box_to_case(board.footprints["U6"], board, cfg)
    sensor_window_width = max(cfg.sensor_side_window_width, sensor.width + 2.0)
    data = {
        "source_board": str(BOARD_PATH.relative_to(ROOT)),
        "variant": "low-profile snap-fit PCB tray with top pass-through cutouts",
        "board_size_mm": {"x": board.width, "y": board.height},
        "case_body_size_mm": {"x": body_length, "y": body_width, "z_base": cfg.base_height},
        "case_overall_size_mm": {"x": body_length, "y": body_width, "z_base": cfg.base_height},
        "height_reduction": {
            "standard_base_height_mm": standard_cfg.base_height,
            "low_profile_base_height_mm": cfg.base_height,
            "reduction_mm": standard_cfg.base_height - cfg.base_height,
            "reduction_percent": (standard_cfg.base_height - cfg.base_height) / standard_cfg.base_height * 100,
            "pcb_top_z_mm": board_top_z(cfg),
            "clearance_above_pcb_top_mm": cfg.base_height - board_top_z(cfg),
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
        "top_pass_through_cutouts": top_pass_throughs,
        "temperature_humidity_sensor_opening": {
            "ref": "U6",
            "sensor": board.footprints["U6"].value,
            "case_position_mm": {"x": sensor.center_x, "y": sensor.center_y},
            "top_air_hole_diameter_mm": cfg.sensor_air_hole_diameter,
            "front_side_window": {
                "side": "min_y",
                "width_mm": sensor_window_width,
                "height_mm": cfg.sensor_side_window_height,
                "bottom_z_mm": board_top_z(cfg) - 0.2,
                "inner_reach_past_sensor_center_mm": cfg.sensor_side_window_inner_reach,
            },
        },
        "snap_fit_lid": {
            "pattern": "tapered triangular wall nubs engaging matching lid-shoulder recesses",
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
        "config": config_report(cfg, exclude_keys=SKELETON_CONFIG_KEYS),
    }
    (OUTPUT_DIR / "eveningstar_case_lowprofile_report.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_skeletonized_report(
    board: BoardData,
    cfg: CaseConfig,
    lowprofile_base: Part.Shape,
    lowprofile_lid: Part.Shape,
    skeletonized_base: Part.Shape,
    skeletonized_lid: Part.Shape,
) -> None:
    body_length = board.width + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    body_width = board.height + 2 * (cfg.wall + cfg.pcb_edge_clearance)
    lowprofile_volume = lowprofile_base.Volume + lowprofile_lid.Volume
    skeletonized_volume = skeletonized_base.Volume + skeletonized_lid.Volume
    reduction = lowprofile_volume - skeletonized_volume
    data = {
        "source_board": str(BOARD_PATH.relative_to(ROOT)),
        "variant": "skeletonized low-profile snap-fit PCB tray",
        "board_size_mm": {"x": board.width, "y": board.height},
        "case_body_size_mm": {"x": body_length, "y": body_width, "z_base": cfg.base_height},
        "case_overall_size_mm": {"x": body_length, "y": body_width, "z_base": cfg.base_height},
        "online_design_influences": [
            "successful skeletonized organizer/baseplate prints that keep only walls/ribs and avoid support-heavy roofs",
            "ribbed plastic-part guidance: keep ribs connected to walls and use ribs instead of globally thickening parts",
            "lattice guidance: keep members open, accessible, and self-supporting rather than trapping support material inside",
        ],
        "skeletonization": {
            "strategy": "faceted hex-ended lightening cells through the bottom floor and lid plate, leaving continuous perimeter walls, snap features, PCB rails, DIN screw pads, and control keepouts intact",
            "printability": "all added lattice cells are open through the print-bed-facing plate surfaces, so they print as normal perimeter holes without slicer supports",
            "base_floor_lattice_cells": len(skeleton_base_floor_cutouts(board, cfg)),
            "lid_plate_lattice_cells": len(skeleton_lid_cutouts(board, cfg)),
            "base_cell_size_mm": {
                "x": cfg.skeleton_base_cell_length,
                "y": cfg.skeleton_base_cell_width,
            },
            "lid_cell_size_mm": {
                "x": cfg.skeleton_lid_cell_length,
                "y": cfg.skeleton_lid_cell_width,
            },
            "cell_chamfer_ratio": cfg.skeleton_cell_chamfer_ratio,
            "minimum_remaining_rib_width_mm": cfg.skeleton_min_rib_width,
            "perimeter_keepout_mm": cfg.skeleton_perimeter_keepout,
            "din_screw_pad_radius_mm": cfg.skeleton_din_pad_radius,
            "functional_feature_keepout_mm": cfg.skeleton_feature_keepout,
        },
        "modeled_solid_volume": {
            "reference_variant": "eveningstar_case_lowprofile",
            "lowprofile_total_mm3": lowprofile_volume,
            "skeletonized_total_mm3": skeletonized_volume,
            "reduction_mm3": reduction,
            "reduction_percent": reduction / lowprofile_volume * 100,
            "lowprofile_base_mm3": lowprofile_base.Volume,
            "lowprofile_lid_mm3": lowprofile_lid.Volume,
            "skeletonized_base_mm3": skeletonized_base.Volume,
            "skeletonized_lid_mm3": skeletonized_lid.Volume,
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
        "din_rail_mount": {
            "source_model": "mechanical/din-rail-bracket-heat-insert-version.step",
            "intended_screw": "M3 clearance through case bottom into bracket heat-set inserts",
            "bracket_insert_pitch_mm": cfg.din_mount_hole_spacing,
            "case_hole_diameter_mm": cfg.din_mount_hole_diameter,
            "case_hole_positions_mm": [asdict(pos) for pos in din_mount_positions(board, cfg)],
        },
        "config": asdict(cfg),
    }
    (OUTPUT_DIR / "eveningstar_case_skeletonized_report.json").write_text(
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

    lowprofile_cfg = replace(cfg, base_height=cfg.low_profile_base_height)
    lowprofile_base = make_lowprofile_snapfit_base(board, lowprofile_cfg)
    lowprofile_lid = make_lowprofile_snapfit_lid(board, lowprofile_cfg)
    lowprofile_board_proxy = make_board_proxy(board, lowprofile_cfg)
    write_exports(
        lowprofile_base,
        lowprofile_lid,
        lowprofile_board_proxy,
        "eveningstar_case_lowprofile",
        "eveningstar_case_lowprofile_pcb_reference.step",
    )
    write_lowprofile_report(board, lowprofile_cfg, cfg)

    skeletonized_base = make_skeletonized_lowprofile_base(board, lowprofile_cfg)
    skeletonized_lid = make_skeletonized_lowprofile_lid(board, lowprofile_cfg)
    skeletonized_board_proxy = make_board_proxy(board, lowprofile_cfg)
    write_exports(
        skeletonized_base,
        skeletonized_lid,
        skeletonized_board_proxy,
        "eveningstar_case_skeletonized",
        "eveningstar_case_skeletonized_pcb_reference.step",
    )
    write_skeletonized_report(
        board,
        lowprofile_cfg,
        lowprofile_base,
        lowprofile_lid,
        skeletonized_base,
        skeletonized_lid,
    )
    App.Console.PrintMessage(f"Wrote enclosure files to {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()
