#!/usr/bin/env python3

"""Render a looping turntable animation of a KiCad board on a transparent background.

The board stands on a narrow end edge, leans, and rides an upright turntable
with the camera level. The lean belongs to the board rather than to the viewer,
so it swings round with the spin: the component side is seen from below, the
bare copper side from above half a turn later, and the board rocks from side to
side through the edge-on quarters.

`kicad-cli pcb render --rotate` takes one set of Euler angles per image and
applies them X outermost, which puts the X rotation in view space. Leaning the
viewer is all that can be expressed directly. To lean the board instead, each
frame composes spin * lean * stand itself and decomposes the result back into
the angles KiCad expects.

KiCad's automatic framing fits each projection to the canvas individually, which
would make the board pulse in size and clip at the angles where its silhouette
is widest. The zoom is instead calibrated once from a low resolution probe pass
over the same angles and then held constant for the render pass.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import subprocess
import tempfile

TRIM_GEOMETRY = re.compile(r"(?P<width>\d+)x(?P<height>\d+)(?P<x>[+-]\d+)(?P<y>[+-]\d+)")

# Zoom used for the probe pass. Any value that keeps the board inside the probe
# canvas at every angle works, because orthographic scale is linear in zoom.
PROBE_ZOOM = 0.3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--name", default="EveningStar-turntable")
    parser.add_argument("--frames", type=int, default=180)
    # How far the board leans off its turntable. Negative leans the board
    # towards the camera at the front of the spin, so the component side is seen
    # from below and the bare copper side from above half a turn later.
    parser.add_argument("--tilt", type=float, default=-20.0)
    # Turn the long axis of the board upright so it stands on a narrow end.
    parser.add_argument("--stand", type=float, default=90.0)
    # Portrait canvas, sized to the aspect of the widest silhouette in a spin.
    # Leaning the board rather than the viewer widens that silhouette, because
    # the board rocks from side to side through the edge-on quarters.
    parser.add_argument("--width", type=int, default=560)
    parser.add_argument("--height", type=int, default=970)
    # Frames are rendered at this multiple of the output size and downscaled,
    # which anti-aliases silkscreen text and board edges.
    parser.add_argument("--supersample", type=int, default=2)
    # Fraction of the canvas the widest angle is allowed to occupy.
    parser.add_argument("--fill", type=float, default=0.94)
    # Applied to a throwaway copy of the board; see tinted_board. KiCad lightens
    # the mask considerably over copper, so this sits well below the blue it is
    # meant to read as on screen.
    parser.add_argument("--mask-colour", default="#123A7A", help="solder mask colour")
    # 33 ms is the closest WebP frame duration to 30 fps.
    parser.add_argument("--frame-delay", type=int, default=33, help="milliseconds")
    parser.add_argument("--quality", type=int, default=65, help="WebP quality")
    return parser.parse_args()


def angles(count: int) -> list[float]:
    return [360.0 * index / count for index in range(count)]


def tinted_board(board: Path, work: Path, colour: str) -> Path:
    """Copy the board next to its libraries with a solder mask colour applied.

    A colour reaches the 3D render only through the board stackup;
    `kicad-cli` ignores KiCad's colour themes entirely, and this board carries no
    stackup, so it renders in the default green. Rather than write a stackup into
    the design, where it would also become fabrication metadata, the render owns
    a throwaway copy of the board.

    The copy sits in a directory of symlinks to the real project so that
    ${KIPRJMOD} still resolves the project's footprints and 3D models.
    """
    work.mkdir(parents=True, exist_ok=True)
    for entry in sorted(board.parent.iterdir()):
        if entry.name != board.name:
            (work / entry.name).symlink_to(entry)

    # Dielectric is sized so the copper and core still total the 1.6 mm the
    # board declares, keeping the rendered edge the right thickness.
    stackup = f'''
		(stackup
			(layer "F.SilkS" (type "Top Silk Screen"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (color "{colour}") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "core") (thickness 1.53) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (color "{colour}") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen"))
			(copper_finish "None")
			(dielectric_constraints no)
		)'''

    text = board.read_text()
    marker = "\n\t(setup\n"
    if marker not in text:
        raise RuntimeError("no (setup ...) block to attach a stackup to")
    tinted = work / board.name
    tinted.write_text(text.replace(marker, marker.rstrip("\n") + stackup + "\n", 1))
    return tinted


Matrix = tuple[tuple[float, float, float], ...]


def rotation(axis: int, degrees: float) -> Matrix:
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    if axis == 0:
        return ((1.0, 0.0, 0.0), (0.0, cos, -sin), (0.0, sin, cos))
    if axis == 1:
        return ((cos, 0.0, sin), (0.0, 1.0, 0.0), (-sin, 0.0, cos))
    return ((cos, -sin, 0.0), (sin, cos, 0.0), (0.0, 0.0, 1.0))


def multiply(left: Matrix, right: Matrix) -> Matrix:
    return tuple(
        tuple(sum(left[row][k] * right[k][col] for k in range(3)) for col in range(3))
        for row in range(3)
    )


def euler_xyz(matrix: Matrix) -> tuple[float, float, float]:
    """Decompose into the X-outermost Euler angles KiCad's --rotate applies.

    Returns degrees for a rotation equal to Rx * Ry * Rz.
    """
    sin_y = min(1.0, max(-1.0, matrix[0][2]))
    y = math.asin(sin_y)
    if abs(sin_y) < 1.0 - 1e-9:
        x = math.atan2(-matrix[1][2], matrix[2][2])
        z = math.atan2(-matrix[0][1], matrix[0][0])
    else:
        # Gimbal lock: X and Z act on the same axis, so fold the whole residual
        # rotation into Z.
        x = 0.0
        z = math.atan2(matrix[1][0], matrix[1][1])
    return math.degrees(x), math.degrees(y), math.degrees(z)


def pose(spin: float, tilt: float, stand: float) -> tuple[float, float, float]:
    """Angles that lean the board by `tilt` and turn it `spin` about the vertical.

    Composing the lean inside the spin is what makes it belong to the board: at
    a spin of zero this is exactly (tilt, 0, stand), and half a turn later the
    same lean is pointing at the camera instead of away from it.
    """
    return euler_xyz(
        multiply(rotation(1, spin), multiply(rotation(0, tilt), rotation(2, stand)))
    )


def render(board: Path, destination: Path, rotation: float, tilt: float,
           stand: float, zoom: float, width: int, height: int) -> None:
    subprocess.run(
        [
            "kicad-cli", "pcb", "render",
            "--rotate", "{:.4f},{:.4f},{:.4f}".format(*pose(rotation, tilt, stand)),
            "--use-board-stackup-colors",
            "--zoom", f"{zoom:.6f}",
            "--width", str(width),
            "--height", str(height),
            # "basic" omits the floor plane that the higher quality settings
            # cast a shadow onto; that shadow would be baked into the otherwise
            # transparent background.
            "--quality", "basic",
            "--background", "transparent",
            "--output", str(destination),
            str(board),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def calibrate_zoom(frames: list[Path], requested: tuple[int, int],
                   fill: float) -> float:
    """Return the zoom that fits every probed silhouette inside the canvas.

    KiCad keeps the pivot at the canvas centre, so the binding constraint is the
    largest distance from the centre to any silhouette edge across all angles.

    Silhouettes are measured against the requested canvas rather than the
    returned one. KiCad renders into a canvas a little smaller than asked for,
    by a border that shrinks as the request grows, but scales the projection by
    the size it was asked for. Normalising against the returned size would
    therefore read a different aspect at probe scale than at render scale, and
    the small probe canvas is where that distortion is worst.
    """
    reported = subprocess.run(
        ["magick", "identify", "-format", "%w %h %@\n", *(str(f) for f in frames)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    requested_x = requested[0] / 2.0
    requested_y = requested[1] / 2.0

    half_width = half_height = 0.0
    for line in reported.splitlines():
        canvas_width, canvas_height, geometry = line.split()
        bounds = TRIM_GEOMETRY.fullmatch(geometry)
        if bounds is None:
            raise RuntimeError(f"unexpected trim geometry: {geometry}")
        left = int(bounds["x"])
        top = int(bounds["y"])
        centre_x = int(canvas_width) / 2.0
        centre_y = int(canvas_height) / 2.0
        half_width = max(
            half_width,
            abs(left - centre_x) / requested_x,
            abs(left + int(bounds["width"]) - centre_x) / requested_x,
        )
        half_height = max(
            half_height,
            abs(top - centre_y) / requested_y,
            abs(top + int(bounds["height"]) - centre_y) / requested_y,
        )

    extent = max(half_width, half_height)
    if extent <= 0.0:
        raise RuntimeError("probe pass produced no visible board")
    return PROBE_ZOOM * fill / extent


def downscale(source: Path, destination: Path, width: int, height: int) -> None:
    subprocess.run(
        [
            "magick", str(source),
            # Resize with associated alpha so the fully transparent black
            # background cannot bleed a dark fringe into the board edges.
            "-alpha", "associate",
            "-filter", "Lanczos",
            "-resize", f"{width}x{height}",
            "-alpha", "disassociate",
            # KiCad returns a canvas slightly smaller than the requested size,
            # so pad back to the exact output geometry.
            "-background", "none",
            "-gravity", "center",
            "-extent", f"{width}x{height}",
            "-strip",
            str(destination),
        ],
        check=True,
    )


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Frames stay out of the build output. KiCad resolves a handful of pixels
    # differently between runs at a few angles, which the lossy encode absorbs
    # but which would leave the retained PNGs, and so the derivation, not
    # reproducible.
    with tempfile.TemporaryDirectory() as scratch:
        run(args, Path(scratch))


def run(args: argparse.Namespace, scratch: Path) -> None:
    probe_dir = scratch / "probe"
    raw_dir = scratch / "raw"
    frame_dir = scratch / "frames"
    for directory in (probe_dir, raw_dir, frame_dir):
        directory.mkdir(parents=True, exist_ok=True)

    board = tinted_board(args.board, scratch / "board", args.mask_colour)
    rotations = angles(args.frames)

    probe_size = (max(args.width // 3, 1), max(args.height // 3, 1))
    probe_frames = []
    for index, rotation in enumerate(rotations):
        frame = probe_dir / f"{index:04d}.png"
        render(board, frame, rotation, args.tilt, args.stand, PROBE_ZOOM,
               *probe_size)
        probe_frames.append(frame)

    zoom = calibrate_zoom(probe_frames, probe_size, args.fill)
    print(f"turntable zoom: {zoom:.6f}")

    frames = []
    for index, rotation in enumerate(rotations):
        raw = raw_dir / f"{index:04d}.png"
        render(board, raw, rotation, args.tilt, args.stand, zoom,
               args.width * args.supersample, args.height * args.supersample)
        frame = frame_dir / f"{index:04d}.png"
        downscale(raw, frame, args.width, args.height)
        frames.append(frame)

    subprocess.run(
        [
            "img2webp",
            "-loop", "0",
            "-d", str(args.frame_delay),
            "-lossy", "-q", str(args.quality), "-m", "6",
            *(str(frame) for frame in frames),
            "-o", str(args.output / f"{args.name}.webp"),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
