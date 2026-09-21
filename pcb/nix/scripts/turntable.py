"""Render turntable frames of the board's GLB export with Blender's Cycles.

Run inside Blender:

    blender -b --factory-startup --python-exit-code 1 -P turntable.py -- \\
        --model EveningStar.glb --output frames/

The board stands upright on its bottom edge, the way round it is drawn, leans,
and rides a turntable under lights that stay put while it turns, so shadows
sweep across it the way they would in a studio. The lean belongs to the board
rather than to the viewer, so it swings round with the spin: the component side
is seen from above, the bare copper side from below half a turn later, and the
board rocks from side to side through the edge-on quarters.

The camera stays level and still. Its distance is solved once from the geometry
so that the widest point of the whole revolution lands at the requested fill,
which keeps the board the same size in every frame.

Frames are written as 0000.png, 0001.png, and so on, with a transparent
background. Progress lines start with "turntable:" so a caller can filter
Blender's own output down to them.
"""

import argparse
import colorsys
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

# A 36 mm wide sensor, so --focal-length reads like a full-frame lens.
SENSOR_WIDTH = 36.0

# Blender's AgX view transform with its punchy look keeps the mask a deep blue
# and plastics dark; the default look washes both out under studio lights.
VIEW_TRANSFORM = "AgX"
LOOK = "AgX - Punchy"

# The world is a studio backdrop, bright overhead and dark underfoot, as
# (height, colour) stops from straight down to straight up. The film is
# transparent, so it only shows in reflections, where it gives metal something
# to mirror, and as a little soft fill.
WORLD_STOPS = (
    (0.0, (0.06, 0.06, 0.06, 1.0)),
    (0.5, (0.55, 0.56, 0.58, 1.0)),
    (1.0, (1.0, 1.0, 1.0, 1.0)),
)
WORLD_STRENGTH = 0.6

# Area lights as (name, position, power, size). Positions and sizes are in
# multiples of the camera distance and power is scaled to match, so the lighting
# looks the same whatever distance the framing settles on. The camera looks
# along +Y with +Z up: the key is above and to the left of it, the fill low on
# the right, and the rim behind the board.
LIGHTS = (
    ("key", (-0.8, -1.0, 0.9), 40.0, 0.8),
    ("fill", (1.0, -0.7, 0.1), 12.0, 1.2),
    ("rim", (0.3, 1.0, 0.9), 30.0, 0.6),
)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="turntable.py")
    parser.add_argument("--model", required=True, help="GLB exported by kicad-cli")
    parser.add_argument("--output", required=True, help="directory for the frames")
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument("--only", default="",
                        help="comma-separated frame indices to render, for previews")
    # How far the board leans off its turntable. Negative leans the top of the
    # board away from the camera at the front of the spin.
    parser.add_argument("--tilt", type=float, default=-20.0)
    # Turn the board within its own plane before it is stood up. Zero keeps it
    # the way round it is drawn, standing on its bottom edge.
    parser.add_argument("--stand", type=float, default=0.0)
    parser.add_argument("--width", type=int, default=760)
    parser.add_argument("--height", type=int, default=720)
    # Fraction of the canvas the widest point of the revolution may reach, from
    # the centre towards the nearer edge.
    parser.add_argument("--fill", type=float, default=0.94)
    parser.add_argument("--focal-length", type=float, default=50.0, help="mm")
    # With denoising, 32 samples came within 45 dB PSNR of 64 at well under
    # two thirds of the time.
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--mask-colour", default="#123A7A", help="solder mask colour")
    return parser.parse_args(argv)


def status(message: str) -> None:
    print(f"turntable: {message}", flush=True)


def linear_rgba(hex_colour: str) -> tuple[float, float, float, float]:
    """Convert an sRGB hex colour into the linear RGBA Blender's nodes expect."""
    channels = [int(hex_colour.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return (*(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels), 1.0)


def set_surface(material: bpy.types.Material, colour=None, metallic=None,
                roughness=None, **inputs) -> None:
    bsdf = material.node_tree.nodes["Principled BSDF"]
    if colour is not None:
        inputs["Base Color"] = colour
    if metallic is not None:
        inputs["Metallic"] = metallic
    if roughness is not None:
        inputs["Roughness"] = roughness
    for name, value in inputs.items():
        bsdf.inputs[name].default_value = value


def board_layers(root: bpy.types.Object) -> dict[str, list[bpy.types.Object]]:
    """Map each board layer, PCB, copper, pad, via, and so on, to its meshes.

    kicad-cli names these meshes <board>_<layer> and hangs them straight off
    the root, while component models sit under an empty named after their
    reference designator.
    """
    layers: dict[str, list[bpy.types.Object]] = {}
    for child in root.children:
        if child.type == "MESH":
            layer = child.data.name.split(".")[0].rsplit("_", 1)[-1]
            layers.setdefault(layer, []).append(child)
    return layers


def fix_materials(layers: dict[str, list[bpy.types.Object]], mask_colour) -> None:
    """Give the exported materials surfaces that read as a real board.

    kicad-cli sets the board layers' materials itself but carries only a colour
    over from the component models, so those arrive at glTF's defaults of fully
    metallic and fully rough, which renders plastic as dull metal. Colour is all
    there is to go on for them. These models paint bare metal in light neutral
    colours up to pure white: leads, terminals, the magjack and ESP32 shields,
    and the electrolytic's can, some with a blue cast. Those become polished
    metal, as do gold-ish ones, and the dark and strongly coloured rest plastic.
    """
    gold = (0.83, 0.63, 0.30, 1.0)
    board_surfaces = {
        "soldermask": dict(colour=mask_colour, metallic=0.0, roughness=0.35,
                           **{"Coat Weight": 0.3}),
        "pad": dict(colour=gold, metallic=1.0, roughness=0.25),
        "via": dict(colour=gold, metallic=1.0, roughness=0.25),
        "copper": dict(colour=(0.75, 0.45, 0.30, 1.0), metallic=1.0, roughness=0.35),
        "silkscreen": dict(colour=(0.9, 0.9, 0.9, 1.0), metallic=0.0, roughness=0.8),
        "PCB": dict(colour=(0.30, 0.28, 0.16, 1.0), metallic=0.0, roughness=0.7),
    }
    board_materials = set()
    for layer, meshes in layers.items():
        for mesh in meshes:
            for slot in mesh.material_slots:
                board_materials.add(slot.material)
                if layer in board_surfaces:
                    set_surface(slot.material, **board_surfaces[layer])

    for material in bpy.data.materials:
        if material in board_materials or not material.use_nodes:
            continue
        colour = material.node_tree.nodes["Principled BSDF"].inputs["Base Color"]
        hue, saturation, value = colorsys.rgb_to_hsv(*colour.default_value[:3])
        light_metal = saturation < 0.35 and value > 0.35
        gold_metal = 0.07 < hue < 0.16 and saturation > 0.5 and value > 0.5
        if light_metal or gold_metal:
            # Even polished silver reflects a little less than everything.
            tint = [min(channel, 0.92) for channel in colour.default_value[:3]]
            set_surface(material, colour=(*tint, 1.0), metallic=1.0, roughness=0.25)
        else:
            set_surface(material, metallic=0.0, roughness=0.45)


def world_points() -> np.ndarray:
    chunks = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        local = np.empty(len(obj.data.vertices) * 3)
        obj.data.vertices.foreach_get("co", local)
        world = np.array(obj.matrix_world)
        chunks.append(local.reshape(-1, 3) @ world[:3, :3].T + world[:3, 3])
    return np.concatenate(chunks)


def camera_distance(points: np.ndarray, focal: float, aspect: float,
                    fill: float) -> float:
    """Distance at which the widest point of the whole revolution reaches `fill`.

    Every point rides a circle of radius r at height z about the vertical spin
    axis. Seen from distance D along the camera axis, across the frame it
    reaches at most r / sqrt(D^2 - r^2), and up or down at most |z| / (D - r),
    each scaled by the lens against the half sensor. The maximum over points is
    therefore exact for the continuous revolution, so no frame can exceed it.
    """
    radius = np.hypot(points[:, 0], points[:, 1])
    height = np.abs(points[:, 2])
    across_scale = focal / (SENSOR_WIDTH / 2.0)
    up_scale = focal / (SENSOR_WIDTH / aspect / 2.0)

    def reach(distance: float) -> float:
        across = across_scale * radius / np.sqrt(distance ** 2 - radius ** 2)
        up = up_scale * height / (distance - radius)
        return float(max(across.max(), up.max()))

    near, far = radius.max() * 1.0001, radius.max() * 1000.0
    for _ in range(100):
        middle = (near + far) / 2.0
        if reach(middle) > fill:
            near = middle
        else:
            far = middle
    return far


def main() -> None:
    args = parse_args()
    started = time.monotonic()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.model)
    scene = bpy.context.scene

    root = next(obj for obj in scene.objects if obj.parent is None)
    layers = board_layers(root)
    fix_materials(layers, linear_rgba(args.mask_colour))

    # kicad-cli exports the board lying flat, component side up (+Z), with the
    # top edge of the drawing towards +Y. Centre it on the board outline, turn
    # it in its own plane, stand it up facing the camera, and lean it; the spin
    # then turns all of that about the vertical.
    pcb = layers["PCB"][0]
    centre = sum((pcb.matrix_world @ Vector(c) for c in pcb.bound_box), Vector()) / 8.0
    spin = bpy.data.objects.new("spin", None)
    scene.collection.objects.link(spin)
    root.parent = spin
    root.matrix_basis = (Matrix.Rotation(math.radians(args.tilt), 4, "X")
                         @ Matrix.Rotation(math.radians(90.0), 4, "X")
                         @ Matrix.Rotation(math.radians(args.stand), 4, "Z")
                         @ Matrix.Translation(-centre)
                         @ root.matrix_basis)
    bpy.context.view_layer.update()

    distance = camera_distance(world_points(), args.focal_length,
                               args.width / args.height, args.fill)
    camera = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    camera.data.lens = args.focal_length
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.sensor_width = SENSOR_WIDTH
    camera.data.clip_start = distance / 100.0
    camera.data.clip_end = distance * 10.0
    camera.location = (0.0, -distance, 0.0)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.collection.objects.link(camera)
    scene.camera = camera
    status(f"camera {distance * 1000:.1f} mm from the board centre")

    for name, position, power, size in LIGHTS:
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        light.data.energy = power * (distance / 0.5) ** 2
        light.data.size = size * distance
        light.location = [c * distance for c in position]
        light.rotation_euler = (-light.location).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(light)

    scene.world = bpy.data.worlds.new("world")
    scene.world.use_nodes = True
    nodes = scene.world.node_tree.nodes
    links = scene.world.node_tree.links
    background = nodes["Background"]
    background.inputs["Strength"].default_value = WORLD_STRENGTH
    # A world's generated coordinates are the view direction, so its Z runs
    # from -1 straight down to 1 straight up.
    direction = nodes.new("ShaderNodeTexCoord")
    axes = nodes.new("ShaderNodeSeparateXYZ")
    height = nodes.new("ShaderNodeMapRange")
    height.inputs["From Min"].default_value = -1.0
    ramp = nodes.new("ShaderNodeValToRGB")
    stops = ramp.color_ramp.elements
    for index, (position, colour) in enumerate(WORLD_STOPS):
        stop = stops[index] if index < len(stops) else stops.new(position)
        stop.position = position
        stop.color = colour
    links.new(direction.outputs["Generated"], axes.inputs["Vector"])
    links.new(axes.outputs["Z"], height.inputs["Value"])
    links.new(height.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], background.inputs["Color"])
    scene.view_settings.view_transform = VIEW_TRANSFORM
    scene.view_settings.look = LOOK

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    # A fixed seed makes the frames reproducible from one run to the next.
    scene.cycles.seed = 0
    scene.cycles.use_animated_seed = False
    scene.render.film_transparent = True
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    # Keep the scene's acceleration structures between frames, since only the
    # spin changes.
    scene.render.use_persistent_data = True
    # Nix exports the cores it granted the build, with 0 meaning all of them.
    cores = int(os.environ.get("NIX_BUILD_CORES", "0"))
    if cores:
        scene.render.threads_mode = "FIXED"
        scene.render.threads = cores

    indices = ([int(index) for index in args.only.split(",")] if args.only
               else range(args.frames))
    os.makedirs(args.output, exist_ok=True)
    for done, index in enumerate(indices, start=1):
        spin.rotation_euler = (0.0, 0.0, 2.0 * math.pi * index / args.frames)
        scene.render.filepath = os.path.join(args.output, f"{index:04d}.png")
        bpy.ops.render.render(write_still=True)
        status(f"render {done}/{len(indices)} ({time.monotonic() - started:.0f}s)")


main()
