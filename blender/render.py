"""Render one catalog image of a bead or charm (decision 0003).

Run by the backend as a bounded subprocess (invariant 6):

    blender -b --factory-startup --disable-autoexec --python-exit-code 1 \
        -P blender/render.py -- <job.json>

The job file is the only input, and it is data: paths, numbers and colors that the backend
computed from the company content (`cad/templates/*.json`). This script makes no product
decisions; it builds the studio scene, applies the material numbers it is given and writes
one PNG. Any problem raises, and `--python-exit-code 1` turns it into a failed exit status.

Job file keys (all required):
    input           absolute path of the GLB (metres, Y up, as exported by the backend)
    output          absolute path of the PNG to write
    resolution      square image size in pixels
    samples         Cycles samples (denoised with OpenImageDenoise)
    seed            Cycles seed (fixed, so renders are repeatable)
    rotation_deg    [x, y, z] rotation applied to the model before framing (Blender axes)
    camera          {"azimuth_deg", "elevation_deg", "lens_mm"}
    material        {"kind": "glass" | "metal", "base_color": [r, g, b] (linear),
                     "metallic", "roughness", "ior", "transmission", "coat"}
    background      [r, g, b] (linear) of the studio backdrop
"""

import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

LOG_PREFIX = "BEADSTUDIO:"

# The scene is built in normalized units: the model's largest dimension is 1.0, so the
# lights and the backdrop need no per-product tuning. The catalog shows shape and finish,
# not size (the drawing carries the dimensions).
MODEL_SIZE = 1.0


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}", flush=True)


# --- job ----------------------------------------------------------------------------------


def _number(job: dict, key: str, low: float, high: float) -> float:
    value = job[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    if not low <= value <= high:
        raise ValueError(f"{key}={value} is outside {low}..{high}")
    return float(value)


def _color(value: object, key: str) -> tuple[float, float, float]:
    if not (isinstance(value, list) and len(value) == 3):
        raise ValueError(f"{key} must be [r, g, b]")
    rgb = tuple(float(c) for c in value)
    if not all(0.0 <= c <= 1.0 for c in rgb):
        raise ValueError(f"{key} channels must be within 0..1")
    return rgb


def read_job(path: Path) -> dict:
    job = json.loads(path.read_text(encoding="utf-8"))
    for key in ("input", "output", "rotation_deg", "camera", "material", "background"):
        if key not in job:
            raise ValueError(f"job file is missing {key!r}")
    if not Path(job["input"]).is_file():
        raise FileNotFoundError(f"model not found: {job['input']}")
    if Path(job["output"]).suffix.lower() != ".png":
        raise ValueError("output must be a .png file")
    _number(job, "resolution", 64, 4096)
    _number(job, "samples", 1, 4096)
    _number(job, "seed", 0, 2**31 - 1)
    camera = job["camera"]
    _number(camera, "azimuth_deg", -180, 180)
    _number(camera, "elevation_deg", -10, 80)
    _number(camera, "lens_mm", 20, 300)
    material = job["material"]
    if material.get("kind") not in ("glass", "metal"):
        raise ValueError("material.kind must be glass or metal")
    _color(material["base_color"], "material.base_color")
    for key, low, high in (
        ("metallic", 0, 1),
        ("roughness", 0, 1),
        ("ior", 1, 3),
        ("transmission", 0, 1),
        ("coat", 0, 1),
    ):
        _number(material, key, low, high)
    _color(job["background"], "background")
    if not (isinstance(job["rotation_deg"], list) and len(job["rotation_deg"]) == 3):
        raise ValueError("rotation_deg must be [x, y, z]")
    return job


# --- scene --------------------------------------------------------------------------------


def enable_nodes(datablock: bpy.types.Material | bpy.types.World) -> None:
    """Make sure a new material or world has its node tree. Blender 5 creates it already and
    deprecates `use_nodes` (removed in 6.0); Blender 4 needs the switch."""
    if bpy.app.version < (5, 0, 0):
        datablock.use_nodes = True


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_model(path: str, rotation_deg: list[float]) -> bpy.types.Object:
    """Import the GLB, join it into one object, orient it, scale it to MODEL_SIZE and rest
    it on the floor (z = 0) centred on the origin."""
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise ValueError("the GLB has no mesh")
    for obj in meshes:
        # Bake the importer's parenting and axis conversion into the mesh.
        obj.data.transform(obj.matrix_world)
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
    for obj in [o for o in bpy.context.scene.objects if o.type != "MESH"]:
        bpy.data.objects.remove(obj)
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=meshes[0], selected_editable_objects=meshes):
            bpy.ops.object.join()
    model = meshes[0]
    model.name = "Product"

    rotation = Euler([math.radians(a) for a in rotation_deg], "XYZ").to_matrix().to_4x4()
    model.data.transform(rotation)
    corners = [Vector(v.co) for v in model.data.vertices]
    low = Vector(min(c[i] for c in corners) for i in range(3))
    high = Vector(max(c[i] for c in corners) for i in range(3))
    size = max(high - low)
    if size <= 0:
        raise ValueError("the model has no extent")
    centre = (low + high) / 2
    scale = MODEL_SIZE / size
    model.data.transform(
        Matrix.Scale(scale, 4) @ Matrix.Translation(-Vector((centre.x, centre.y, low.z)))
    )
    model.data.update()

    # Vertices are shared only inside one CAD face (backend geometry/export.py), so smooth
    # shading rounds the curved faces and keeps every CAD edge sharp.
    for polygon in model.data.polygons:
        polygon.use_smooth = True
    return model


def product_material(spec: dict) -> bpy.types.Material:
    material = bpy.data.materials.new("ProductMaterial")
    enable_nodes(material)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    rgb = spec["base_color"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Metallic"].default_value = spec["metallic"]
    bsdf.inputs["Roughness"].default_value = spec["roughness"]
    bsdf.inputs["IOR"].default_value = spec["ior"]
    bsdf.inputs["Transmission Weight"].default_value = spec["transmission"]
    bsdf.inputs["Coat Weight"].default_value = spec["coat"]

    if spec["kind"] == "glass" and spec["transmission"] > 0:
        # Shadow rays see the glass as tinted transparency, the cheap stand-in for the
        # refractive caustics that low sample counts cannot resolve: clear glass casts a
        # light, colored shadow instead of a black one.
        light_path = nodes.new("ShaderNodeLightPath")
        transparent = nodes.new("ShaderNodeBsdfTransparent")
        t = spec["transmission"] * 0.6
        transparent.inputs["Color"].default_value = (
            *(1.0 - t + t * c for c in rgb),
            1.0,
        )
        mix = nodes.new("ShaderNodeMixShader")
        links.new(light_path.outputs["Is Shadow Ray"], mix.inputs["Fac"])
        links.new(bsdf.outputs["BSDF"], mix.inputs[1])
        links.new(transparent.outputs["BSDF"], mix.inputs[2])
        links.new(mix.outputs["Shader"], output.inputs["Surface"])
    else:
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return material


def add_backdrop(color: tuple[float, float, float]) -> None:
    """A seamless studio sweep: a floor that curves up into a wall behind the product."""
    mesh = bpy.data.meshes.new("Backdrop")
    bm = bmesh.new()
    # Profile in the YZ plane: flat floor to y = 2, a quarter circle, then the wall. The
    # camera sees the floor only to about y = -0.7; beyond that it fades to a mid tone
    # (below), so flat metal faces, which reflect the floor in front of them, get a soft
    # gradient. Fading to black gave them a harsh black-to-white band (QA 2026-11-23).
    radius, depth, height, half_width, steps = 3.0, 6.0, 8.0, 12.0, 16
    curve = [
        (2.0 + radius * math.sin(t), radius - radius * math.cos(t))
        for t in (math.pi / 2 * i / steps for i in range(steps + 1))
    ]
    profile = [(-depth, 0.0), *curve, (2.0 + radius, height)]
    rows = [[bm.verts.new((x, y, z)) for (y, z) in profile] for x in (-half_width, half_width)]
    for i in range(len(profile) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    backdrop = bpy.data.objects.new("Backdrop", mesh)
    bpy.context.scene.collection.objects.link(backdrop)

    material = bpy.data.materials.new("BackdropMaterial")
    enable_nodes(material)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    # Base color: the backdrop color from y = -0.9 back, fading to a fifth of it at y = -3.5.
    coords = nodes.new("ShaderNodeTexCoord")
    split = nodes.new("ShaderNodeSeparateXYZ")
    fade = nodes.new("ShaderNodeMapRange")
    fade.interpolation_type = "SMOOTHSTEP"
    fade.inputs["From Min"].default_value = -3.5
    fade.inputs["From Max"].default_value = -0.9
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*(c * 0.18 for c in color), 1.0)
    mix.inputs["B"].default_value = (*color, 1.0)
    links.new(coords.outputs["Object"], split.inputs["Vector"])
    links.new(split.outputs["Y"], fade.inputs["Value"])
    links.new(fade.outputs["Result"], mix.inputs["Factor"])
    links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    mesh.materials.append(material)


def add_area_light(
    name: str, location: tuple[float, float, float], size: tuple[float, float], power: float
) -> None:
    """A rectangular soft box aimed just above the floor's centre; glass and metal show it
    as a window-like highlight (round lights looked like painted dots)."""
    light = bpy.data.lights.new(name, "AREA")
    light.shape = "RECTANGLE"
    light.size, light.size_y = size
    light.energy = power
    obj = bpy.data.objects.new(name, light)
    obj.location = location
    direction = Vector((0.0, 0.0, MODEL_SIZE * 0.4)) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)


def add_lights() -> None:
    """Three soft boxes: key (front left, high), fill (front right, low), rim (behind), and
    a wide, dim card above the camera that a flat metal face mirrors as an even sheen."""
    add_area_light("Key", (-2.6, -2.8, 3.2), (1.4, 3.0), 420.0)
    add_area_light("Fill", (3.2, -2.4, 1.4), (2.0, 3.5), 160.0)
    add_area_light("Rim", (0.8, 2.6, 3.4), (3.0, 1.0), 260.0)
    add_area_light("Card", (0.0, -5.5, 2.2), (6.0, 2.5), 70.0)


def add_world(color: tuple[float, float, float]) -> None:
    world = bpy.data.worlds.new("Studio")
    enable_nodes(world)
    background = world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (*color, 1.0)
    # Dim: the camera never sees the world (the backdrop fills the frame), but metal faces
    # reflect it, and a dark surround is what gives polished plating its contrast.
    background.inputs["Strength"].default_value = 0.15
    bpy.context.scene.world = world


def add_camera(model: bpy.types.Object, spec: dict) -> None:
    """Turntable rig: the camera is parented to an empty at the product's centre; the empty
    turns by the azimuth and tilts by the elevation, so one number moves the camera around."""
    corners = [model.matrix_world @ Vector(v.co) for v in model.data.vertices]
    low = Vector(min(c[i] for c in corners) for i in range(3))
    high = Vector(max(c[i] for c in corners) for i in range(3))
    centre = (low + high) / 2
    radius = (high - low).length / 2

    rig = bpy.data.objects.new("TurntableRig", None)
    rig.location = centre
    # XYZ order: tilt about X first (elevation), then turn about Z (azimuth).
    rig.rotation_euler = (
        math.radians(-spec["elevation_deg"]),
        0.0,
        math.radians(spec["azimuth_deg"]),
    )
    bpy.context.scene.collection.objects.link(rig)

    data = bpy.data.cameras.new("Camera")
    data.lens = spec["lens_mm"]
    data.sensor_width = 36.0
    data.clip_start = 0.01
    data.clip_end = 100.0
    half_fov = math.atan((data.sensor_width / 2) / data.lens)
    distance = radius / math.sin(half_fov) * 1.18
    camera = bpy.data.objects.new("Camera", data)
    camera.parent = rig
    camera.location = (0.0, -distance, 0.0)
    camera.rotation_euler = (math.radians(90), 0.0, 0.0)
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera


def configure_render(job: dict) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = int(job["samples"])
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.seed = int(job["seed"])
    if job["material"]["kind"] == "glass":  # light crosses several faces of a bead
        scene.cycles.max_bounces = 16
        scene.cycles.transmission_bounces = 16
        scene.cycles.glossy_bounces = 8
    else:  # an opaque metal needs only a few reflections
        scene.cycles.max_bounces = 6
        scene.cycles.transmission_bounces = 0
        scene.cycles.glossy_bounces = 4
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.blur_glossy = 1.0
    scene.render.resolution_x = int(job["resolution"])
    scene.render.resolution_y = int(job["resolution"])
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.filepath = job["output"]


def main(argv: list[str]) -> None:
    if "--" not in argv or len(argv) != argv.index("--") + 2:
        raise SystemExit("usage: blender -b -P render.py -- <job.json>")
    job_path = Path(argv[argv.index("--") + 1])
    started = time.monotonic()
    job = read_job(job_path)
    log(f"job {job_path.name}: {Path(job['input']).name} -> {Path(job['output']).name}")

    clear_scene()
    model = import_model(job["input"], job["rotation_deg"])
    model.data.materials.clear()
    model.data.materials.append(product_material(job["material"]))
    add_backdrop(tuple(job["background"]))
    add_lights()
    add_world(tuple(job["background"]))
    add_camera(model, job["camera"])
    configure_render(job)

    log(f"rendering {job['resolution']} px, {job['samples']} samples")
    bpy.ops.render.render(write_still=True)
    if not Path(job["output"]).is_file():
        raise RuntimeError("Blender finished but wrote no image")
    log(f"done in {time.monotonic() - started:.1f} s")


if __name__ == "__main__":
    main(sys.argv)
