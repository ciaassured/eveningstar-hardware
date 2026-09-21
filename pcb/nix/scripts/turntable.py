#!/usr/bin/env python3

"""Render a looping turntable animation of a KiCad board on a transparent background.

The board stands upright on its bottom edge, the way round it is drawn, leans,
and rides an upright turntable with the camera level and in perspective. The
lean belongs to the board rather than to the viewer, so it swings round with the
spin: the component side is seen from above, the bare copper side from below
half a turn later, and the board rocks from side to side through the edge-on
quarters.

`kicad-cli pcb render --rotate` takes one set of Euler angles per image and
applies them X outermost, which puts the X rotation in view space. Leaning the
viewer is all that can be expressed directly. To lean the board instead, each
frame composes spin * lean * stand itself and decomposes the result back into
the angles KiCad expects.

KiCad's automatic framing fits each projection to the canvas individually, which
would make the board pulse in size and clip at the angles where its silhouette
is widest. The zoom is instead calibrated once from a low resolution probe pass
over the same angles, refined at the widest of them, and then held constant for
the render pass.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import time

TRIM_GEOMETRY = re.compile(r"(?P<width>\d+)x(?P<height>\d+)(?P<x>[+-]\d+)(?P<y>[+-]\d+)")

# Zoom used for the probe pass. It must keep the board inside the probe canvas
# at every angle, and stay above roughly 0.33, below which KiCad clamps the zoom
# and the rendered size stops following it.
PROBE_ZOOM = 0.4

# Perspective scale is not linear in zoom, so the zoom is settled against the
# angles that probed widest, re-rendered at full size, until the widest lands
# within this fraction of the requested fill. The first step aims at a fill
# short enough that perspective cannot push it off the canvas.
REFINE_ANGLES = 32
REFINE_TOLERANCE = 0.005
REFINE_PASSES = 5
FIRST_STEP_FILL = 0.7

# Stackup mask layers, which is where the 3D render takes its mask colour from.
MASK_LAYER = re.compile(
    r'(?P<head>\(layer "[FB]\.Mask"\n(?P<indent>\s*)\(type "[^"]*"\))'
    r'(?:\n\s*\(color "[^"]*"\))?'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--name", default="EveningStar-turntable")
    parser.add_argument("--frames", type=int, default=180)
    # How far the board leans off its turntable. Negative leans the top of the
    # board away from the camera at the front of the spin, so the component side
    # is seen from above and the bare copper side from below half a turn later.
    parser.add_argument("--tilt", type=float, default=-20.0)
    # Turn the board within its own plane before it is stood up. Zero keeps it
    # the way round it is drawn, standing on its bottom edge.
    parser.add_argument("--stand", type=float, default=0.0)
    parser.add_argument("--projection", choices=("perspective", "orthographic"),
                        default="perspective")
    # Canvas sized to the aspect of the widest silhouette in a spin, which for
    # this board in perspective is slightly wider than tall. Leaning the board
    # rather than the viewer adds height, because the board rocks from side to
    # side through the edge-on quarters.
    parser.add_argument("--width", type=int, default=760)
    parser.add_argument("--height", type=int, default=720)
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
    parser.add_argument("--jobs", type=int, default=default_jobs(),
                        help="frames rendered at once")
    return parser.parse_args()


def default_jobs() -> int:
    # Nix exports the cores it granted the build, with 0 meaning all of them.
    # Each kicad-cli process already keeps a few cores busy in Mesa's software
    # rasteriser and peaks around 0.6 GB, so half the cores is plenty.
    cores = int(os.environ.get("NIX_BUILD_CORES", "0")) or os.cpu_count() or 1
    return max(1, cores // 2)


def angles(count: int) -> list[float]:
    return [360.0 * index / count for index in range(count)]


def tinted_board(board: Path, work: Path, colour: str) -> Path:
    """Copy the board next to its libraries with a solder mask colour applied.

    A colour reaches the 3D render only through the board stackup; `kicad-cli`
    ignores KiCad's colour themes entirely, and the stackup this board carries
    leaves the mask colour unset, so it renders in the default green. Rather
    than set a colour in the design, where it would also become fabrication
    metadata, the render colours the mask layers of a throwaway copy.

    The copy sits in a directory of symlinks to the real project so that
    ${KIPRJMOD} still resolves the project's footprints and 3D models.
    """
    work.mkdir(parents=True, exist_ok=True)
    for entry in sorted(board.parent.iterdir()):
        if entry.name != board.name:
            (work / entry.name).symlink_to(entry)

    text, count = MASK_LAYER.subn(
        lambda layer: f'{layer["head"]}\n{layer["indent"]}(color "{colour}")',
        board.read_text(),
    )
    if count != 2:
        raise RuntimeError(f"expected 2 stackup mask layers to colour, found {count}")
    tinted = work / board.name
    tinted.write_text(text)
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
           stand: float, zoom: float, width: int, height: int,
           perspective: bool) -> None:
    subprocess.run(
        [
            "kicad-cli", "pcb", "render",
            *(["--perspective"] if perspective else []),
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


def extents(frames: list[Path], requested: tuple[int, int]) -> list[float]:
    """Return how far each silhouette reaches from the canvas centre.

    KiCad keeps the pivot at the canvas centre, so what has to fit is the
    largest distance from the centre to a silhouette edge, taken per axis as a
    fraction of the half canvas.

    Silhouettes are measured against the requested canvas rather than the
    returned one. KiCad renders into a canvas a fixed border smaller than asked
    for, but scales the projection by the size it was asked for. Normalising
    against the returned size would therefore read a different aspect at probe
    scale than at render scale, and the small probe canvas is where that
    distortion is worst. A silhouette that touches the edge of the returned
    canvas has been clipped, so how far it really reaches is unknown; it reads
    as infinite.
    """
    reported = subprocess.run(
        ["magick", "identify", "-format", "%w %h %@\n", *(str(f) for f in frames)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    requested_x = requested[0] / 2.0
    requested_y = requested[1] / 2.0

    reaches = []
    for line in reported.splitlines():
        canvas_width, canvas_height, geometry = line.split()
        bounds = TRIM_GEOMETRY.fullmatch(geometry)
        if bounds is None:
            raise RuntimeError(f"unexpected trim geometry: {geometry}")
        left = int(bounds["x"])
        top = int(bounds["y"])
        right = left + int(bounds["width"])
        bottom = top + int(bounds["height"])
        if (left <= 0 or top <= 0 or right >= int(canvas_width)
                or bottom >= int(canvas_height)):
            reaches.append(math.inf)
            continue
        centre_x = int(canvas_width) / 2.0
        centre_y = int(canvas_height) / 2.0
        reaches.append(max(
            abs(left - centre_x) / requested_x,
            abs(right - centre_x) / requested_x,
            abs(top - centre_y) / requested_y,
            abs(bottom - centre_y) / requested_y,
        ))

    if max(reaches, default=0.0) <= 0.0:
        raise RuntimeError("probe pass produced no visible board")
    return reaches


def settle_zoom(measure: Callable[[float], float], probe_zoom: float,
                probe_reach: float, fill: float) -> float:
    """Find the zoom at which the widest silhouette reaches `fill`.

    KiCad's perspective camera zooms by moving in, so a point nearer the camera
    grows faster than the zoom does: its reach r follows r = a z / (1 - c z),
    which makes z / r a straight line in z. Orthographic projection is the case
    c = 0. A secant on z / r through the last two measurements therefore lands
    on the fill in a pass or two. A clipped measurement says only that the zoom
    was too far in, so the next step backs off halfway to the last good one.
    """
    known = [(probe_zoom, probe_reach)]
    zoom = probe_zoom * FIRST_STEP_FILL / probe_reach
    for _ in range(REFINE_PASSES):
        reach = measure(zoom)
        if abs(reach - fill) <= REFINE_TOLERANCE * fill:
            return zoom
        if math.isinf(reach):
            zoom = (known[-1][0] + zoom) / 2.0
            continue
        known.append((zoom, reach))
        (zoom_0, reach_0), (zoom_1, reach_1) = known[-2:]
        slope = (zoom_1 / reach_1 - zoom_0 / reach_0) / (zoom_1 - zoom_0)
        intercept = zoom_0 / reach_0 - slope * zoom_0
        zoom = intercept / (1.0 / fill - slope)
    raise RuntimeError(f"zoom did not settle within {REFINE_PASSES} passes")


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


def in_parallel(stage: str, tasks: list[Callable[[Path], None]],
                boards: list[Path], started: float) -> None:
    """Run independent frame tasks on a pool, reporting each as it lands.

    Every frame is a separate kicad-cli process, so threads are enough to keep
    several in flight. Each task borrows a board of its own for the duration:
    KiCad locks the project beside the board file, and processes sharing one
    trip over each other's lock files. The first failure cancels whatever has
    not started.
    """
    available: queue.SimpleQueue[Path] = queue.SimpleQueue()
    for board in boards:
        available.put(board)

    def borrowing(task: Callable[[Path], None]) -> None:
        board = available.get()
        try:
            task(board)
        finally:
            available.put(board)

    with ThreadPoolExecutor(max_workers=len(boards)) as pool:
        futures: list[Future] = [pool.submit(borrowing, task) for task in tasks]
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                future.result()
                status(f"{stage} {done}/{len(futures)} "
                       f"({time.monotonic() - started:.0f}s)")
        except BaseException:
            for future in futures:
                future.cancel()
            raise


def status(message: str) -> None:
    # Nix hands the builder a pipe rather than a terminal, so stdout is block
    # buffered and nothing would appear until the render had finished.
    print(f"turntable: {message}", flush=True)


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
    refine_dir = scratch / "refine"
    raw_dir = scratch / "raw"
    frame_dir = scratch / "frames"
    for directory in (probe_dir, refine_dir, raw_dir, frame_dir):
        directory.mkdir(parents=True, exist_ok=True)

    boards = [
        tinted_board(args.board, scratch / f"board-{worker}", args.mask_colour)
        for worker in range(max(1, args.jobs))
    ]
    rotations = angles(args.frames)

    started = time.monotonic()
    count = len(rotations)
    perspective = args.projection == "perspective"
    status(f"{count} frames, {args.projection}, {len(boards)} at a time")

    probe_size = (max(args.width // 3, 1), max(args.height // 3, 1))

    # A first render on its own lets KiCad create its configuration directories
    # and fill its 3D model cache before several processes could race to write
    # them, which in a fresh build sandbox they otherwise do.
    render(boards[0], scratch / "warm-up.png", 0.0, args.tilt, args.stand,
           PROBE_ZOOM, *probe_size, perspective)
    status(f"warm-up ({time.monotonic() - started:.0f}s)")

    probe_frames = [probe_dir / f"{index:04d}.png" for index in range(count)]
    in_parallel("probe", [
        lambda board, frame=frame, rotation=rotation: render(
            board, frame, rotation, args.tilt, args.stand, PROBE_ZOOM,
            *probe_size, perspective)
        for frame, rotation in zip(probe_frames, rotations)
    ], boards, started)

    probed = extents(probe_frames, probe_size)
    if math.isinf(max(probed)):
        raise RuntimeError("the probe zoom clips the board; lower PROBE_ZOOM")

    # The zoom is settled at the full render size: KiCad returns a canvas a
    # fixed border smaller than requested, and on the small probe canvas that
    # border cuts into the very fill being aimed for.
    render_size = (args.width * args.supersample, args.height * args.supersample)
    widest_angles = [
        rotation
        for _, rotation in sorted(zip(probed, rotations), reverse=True)[:REFINE_ANGLES]
    ]
    passes = 0

    def widest_at(zoom: float) -> float:
        nonlocal passes
        passes += 1
        checks = [refine_dir / f"{passes}-{index:04d}.png"
                  for index in range(len(widest_angles))]
        in_parallel(f"refine {passes}", [
            lambda board, frame=frame, rotation=rotation: render(
                board, frame, rotation, args.tilt, args.stand, zoom,
                *render_size, perspective)
            for frame, rotation in zip(checks, widest_angles)
        ], boards, started)
        widest = max(extents(checks, render_size))
        status(f"zoom {zoom:.6f} fills {widest:.3f} of the canvas")
        return widest

    zoom = settle_zoom(widest_at, PROBE_ZOOM, max(probed), args.fill)

    frames = [frame_dir / f"{index:04d}.png" for index in range(count)]

    reaches = [0.0] * count

    def frame_task(board: Path, index: int, rotation: float) -> None:
        raw = raw_dir / f"{index:04d}.png"
        render(board, raw, rotation, args.tilt, args.stand, zoom, *render_size,
               perspective)
        reaches[index] = extents([raw], render_size)[0]
        downscale(raw, frames[index], args.width, args.height)
    in_parallel("render", [
        lambda board, index=index, rotation=rotation: frame_task(
            board, index, rotation)
        for index, rotation in enumerate(rotations)
    ], boards, started)

    # The zoom was settled on the angles that probed widest, which in
    # perspective need not be the ones that end up widest; check them all.
    widest = max(reaches)
    if math.isinf(widest):
        clipped = [index for index, reach in enumerate(reaches) if math.isinf(reach)]
        raise RuntimeError(f"frames {clipped} run off the canvas")
    status(f"widest frame fills {widest:.3f} of the canvas")

    status(f"encoding {count} frames")
    subprocess.run(
        [
            "img2webp",
            "-loop", "0",
            "-d", str(args.frame_delay),
            # Method 6 took around forty times longer on one core for about 4%
            # smaller output at the same measured quality.
            "-lossy", "-q", str(args.quality), "-m", "4",
            *(str(frame) for frame in frames),
            "-o", str(args.output / f"{args.name}.webp"),
        ],
        check=True,
    )
    status(f"done ({time.monotonic() - started:.0f}s)")


if __name__ == "__main__":
    main()
