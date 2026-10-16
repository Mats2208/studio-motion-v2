"""Shared helpers for every STUDIO MOTION V2 shot.

Every shot script builds its own scene from nothing, reads timeline.json and
bakes motion per frame from analytic easing functions, so a shot is fully
reproducible from its script plus the timeline.
"""
import json, math
from pathlib import Path
import bpy, bmesh
from mathutils import Vector, Matrix, Euler, Quaternion

ROOT = Path(__file__).resolve().parents[1]
TL = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
FPS = TL["fps"]
PAL = TL["palette"]
FONT_DIR = ROOT / "film/assets/fonts"
RENDER_DIR = ROOT / "renders"

# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, t): return a + (b - a) * t
def span(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 != t0 else float(t >= t1)
def smooth(x): x = clamp(x); return x * x * (3 - 2 * x)
def smoother(x): x = clamp(x); return x * x * x * (x * (x * 6 - 15) + 10)
def out_cubic(x): x = clamp(x); return 1 - (1 - x) ** 3
def in_cubic(x): x = clamp(x); return x ** 3
def out_quart(x): x = clamp(x); return 1 - (1 - x) ** 4
def out_expo(x): x = clamp(x); return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)
def in_out_cubic(x): x = clamp(x); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def in_out_sine(x): x = clamp(x); return -(math.cos(math.pi * x) - 1) / 2
def back_out(x, s=1.70158):
    x = clamp(x) - 1
    return x * x * ((s + 1) * x + s) + 1
def damped(x, cycles=2.0, decay=5.0):
    """1 -> 0 decaying oscillation, used for settles."""
    return math.exp(-decay * x) * math.cos(2 * math.pi * cycles * x) if x > 0 else 1.0
def vlerp(a, b, t): return Vector(a).lerp(Vector(b), t)

def catmull(points, u):
    """Uniform Catmull-Rom through points, u in [0,1]."""
    pts = [Vector(p) for p in points]
    n = len(pts) - 1
    f = clamp(u) * n
    i = min(int(f), n - 1); t = f - i
    p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(i + 2, n)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)

# ---------------------------------------------------------------- color
def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def hex_lin(h, a=1.0):
    h = h.lstrip("#")
    return tuple(srgb_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)

# ---------------------------------------------------------------- scene
def shot_info(shot_id):
    return next(s for s in TL["shots"] if s["id"] == shot_id)

def new_scene(shot_id, preview=False):
    info = shot_info(shot_id)
    old = bpy.data.scenes.get(shot_id)
    if old:
        for ob in list(old.collection.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.scenes.remove(old)
    sc = bpy.data.scenes.new(shot_id)
    bpy.context.window.scene = sc
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = info["w"], info["h"]
    r.resolution_percentage = 50 if preview else 100
    r.fps = FPS
    sc.frame_start, sc.frame_end = 1, info["frames"]
    r.film_transparent = info["alpha"]
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.5
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA" if info["alpha"] else "RGB"
    r.image_settings.color_depth = "16"
    r.filepath = str(RENDER_DIR / shot_id / "f_")
    c = sc.cycles
    c.device = "GPU"
    c.samples = 16 if preview else 96
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    c.denoiser = "OPTIX"
    c.max_bounces = 12
    c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces = 4, 4, 8
    c.caustics_reflective = c.caustics_refractive = False
    c.blur_glossy = 0.5
    sc.view_settings.view_transform = "Khronos PBR Neutral"   # keeps brand hues exact (AgX desaturates #6A3DF0)
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.world = bpy.data.worlds.new(shot_id + "_world")
    sc.world.use_nodes = True
    sc["shot"] = info
    return sc, info

def world_color(sc, hexcol, strength=1.0):
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = hex_lin(hexcol)
    bg.inputs[1].default_value = strength

def t_of(info, frame):
    return info["start"] + (frame - 1) / FPS

def link(sc, ob):
    sc.collection.objects.link(ob)
    return ob

# ---------------------------------------------------------------- materials
def _principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes["Principled BSDF"]

def plastic(name, hexcol, rough=0.22, coat=0.6, coat_rough=0.08, sss=0.0):
    m, p = _principled(name)
    p.inputs["Base Color"].default_value = hex_lin(hexcol)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = coat_rough
    if sss:
        p.inputs["Subsurface Weight"].default_value = sss
        p.inputs["Subsurface Radius"].default_value = (0.3, 0.15, 0.4)
        p.inputs["Subsurface Scale"].default_value = 0.05
    return m

def satin(name, hexcol, rough=0.38, sheen=0.3):
    m, p = _principled(name)
    p.inputs["Base Color"].default_value = hex_lin(hexcol)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Sheen Weight"].default_value = sheen
    p.inputs["Sheen Tint"].default_value = (1, 1, 1, 1)
    return m

def ceramic(name, hexcol="#F7F3EE", rough=0.3):
    m, p = _principled(name)
    p.inputs["Base Color"].default_value = hex_lin(hexcol)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = 0.35
    return m

def chrome(name, hexcol="#D9D2F2", rough=0.18):
    m, p = _principled(name)
    p.inputs["Base Color"].default_value = hex_lin(hexcol)
    p.inputs["Metallic"].default_value = 1.0
    p.inputs["Roughness"].default_value = rough
    return m

def glass(name, hexcol, rough=0.08, ior=1.45):
    m, p = _principled(name)
    p.inputs["Base Color"].default_value = hex_lin(hexcol)
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["Roughness"].default_value = rough
    p.inputs["IOR"].default_value = ior
    return m

def matte(name, hexcol, rough=0.85):
    m, p = _principled(name)
    p.inputs["Base Color"].default_value = hex_lin(hexcol)
    p.inputs["Roughness"].default_value = rough
    return m

def emission(name, hexcol, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); o = nt.nodes.new("ShaderNodeOutputMaterial")
    e.inputs[0].default_value = hex_lin(hexcol); e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], o.inputs[0])
    return m

def holdout(name="holdout"):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    h = nt.nodes.new("ShaderNodeHoldout"); o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(h.outputs[0], o.inputs[0])
    return m

def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob

# ---------------------------------------------------------------- geometry
CURSOR_OUTLINE = [(0, 0), (0, -16.0), (3.8, -12.6), (6.6, -19.0), (9.4, -17.8), (6.7, -11.6), (11.6, -11.6)]

def extrude_outline(name, pts, depth, bevel=0.02, segments=6, center=True):
    """Extruded polygon in the XY plane, thickness along +Z, rounded bevel on every edge."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0)) for x, y in pts]
    face = bm.faces.new(verts)
    if face.normal.z < 0:
        face.normal_flip()
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    for v in [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]:
        v.co.z += depth
    if center:
        for v in bm.verts:
            v.co.z -= depth / 2
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    md = ob.modifiers.new("bevel", "BEVEL")
    md.width = bevel; md.segments = segments; md.limit_method = "ANGLE"
    md.angle_limit = math.radians(30); md.harden_normals = True; md.profile = 0.5
    me.shade_smooth()
    return ob

def cursor(name, height=1.0, depth_ratio=0.12, mat=None):
    """Classic pointer, tip at origin-top; origin moved to its visual centre."""
    s = height / 19.0
    pts = [(x * s, y * s) for x, y in CURSOR_OUTLINE]
    ob = extrude_outline(name, pts, depth=height * depth_ratio, bevel=height * 0.028, segments=7)
    # origin at the bounding-box centre so rotations read naturally
    cx, cy = 11.6 * s / 2 * 0.86, -19.0 * s / 2
    ob.data.transform(Matrix.Translation((-cx, -cy, 0)))
    ob["tip_offset"] = (cx, cy)
    if mat:
        assign(ob, mat)
    return ob

def rounded_box(name, size, radius, segments=6):
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob = bpy.context.active_object; ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    md = ob.modifiers.new("bevel", "BEVEL"); md.width = radius; md.segments = segments
    md.harden_normals = True
    ob.data.shade_smooth()
    return ob

def cyclorama(name, width=30, depth=20, height=12, radius=3.0, mat=None):
    """Floor that curves into a back wall (infinite studio sweep). Floor at z=0, wall at y=+depth/2."""
    prof = [(-depth / 2, 0.0)]
    y0 = depth / 2 - radius
    prof.append((y0, 0.0))
    for k in range(1, 17):
        a = k / 16 * math.pi / 2
        prof.append((y0 + radius * math.sin(a), radius - radius * math.cos(a)))
    prof.append((depth / 2, height))
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rows = []
    for x in (-width / 2, width / 2):
        rows.append([bm.verts.new((x, y, z)) for y, z in prof])
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    me.shade_smooth()
    if mat:
        assign(ob, mat)
    return ob

def text_obj(name, body, font_file, size=1.0, extrude=0.1, bevel=0.01, align="CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(str(FONT_DIR / font_file), check_existing=True)
    cu.size = size; cu.extrude = extrude; cu.bevel_depth = bevel; cu.bevel_resolution = 4
    cu.align_x = align; cu.align_y = "CENTER"
    cu.resolution_u = 24
    return bpy.data.objects.new(name, cu)

# ---------------------------------------------------------------- lights / camera
def area(sc, name, loc, target, size, energy, hexcol="#FFFFFF", shape="RECTANGLE", size_y=None, spread=180):
    li = bpy.data.lights.new(name, "AREA")
    li.shape = shape; li.size = size; li.size_y = size_y or size
    li.energy = energy; li.color = hex_lin(hexcol)[:3]
    li.spread = math.radians(spread)
    ob = link(sc, bpy.data.objects.new(name, li))
    ob.location = loc
    look_at(ob, target)
    return ob

def reflector(sc, name, loc, target, w, h, strength=3.0, hexcol="#FFFFFF", gradient=True):
    """Emissive card visible only in reflections (product-photography gradient flag)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((x * w / 2, y * h / 2, 0)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    face = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new()
    for lp in face.loops:
        lp[uv].uv = ((lp.vert.co.x / w) + 0.5, (lp.vert.co.y / h) + 0.5)
    bm.to_mesh(me); bm.free()
    ob = link(sc, bpy.data.objects.new(name, me))
    m = bpy.data.materials.new(name + "_mat"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); o = nt.nodes.new("ShaderNodeOutputMaterial")
    e.inputs[0].default_value = hex_lin(hexcol); e.inputs[1].default_value = strength
    if gradient:
        tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        mp = nt.nodes.new("ShaderNodeMapRange"); mp.inputs[1].default_value = 0.0; mp.inputs[2].default_value = 1.0
        mp.inputs[3].default_value = 0.05; mp.inputs[4].default_value = strength
        nt.links.new(tc.outputs["UV"], sep.inputs[0]); nt.links.new(sep.outputs[1], mp.inputs[0])
        nt.links.new(mp.outputs[0], e.inputs[1])
    nt.links.new(e.outputs[0], o.inputs[0])
    me.materials.append(m)
    ob.visible_camera = False; ob.visible_shadow = False; ob.visible_diffuse = False
    ob.location = loc
    look_at(ob, target)
    ob.rotation_quaternion = ob.rotation_quaternion @ Quaternion((0, 1, 0), math.pi)  # emit toward target
    return ob

def look_at(ob, target, roll=0.0):
    d = Vector(target) - ob.location
    q = d.to_track_quat("-Z", "Y")
    if roll:
        q = q @ Quaternion((0, 0, 1), roll)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = q

def camera(sc, name="cam", lens=50, fstop=2.8, focus=5.0, sensor=36):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens; cd.sensor_width = sensor; cd.sensor_fit = "HORIZONTAL"
    cd.clip_start = 0.05; cd.clip_end = 250
    cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop; cd.dof.focus_distance = focus
    cd.dof.aperture_blades = 7; cd.dof.aperture_rotation = math.radians(12)
    ob = link(sc, bpy.data.objects.new(name, cd))
    sc.camera = ob
    return ob

# ---------------------------------------------------------------- baking
def bake(sc, info, fn):
    """fn(t, frame) is called for every frame; it sets transforms and calls key()."""
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        fn(t_of(info, f), f)
    # one extra frame each side so motion blur has neighbours
    sc.frame_set(sc.frame_start)

def key(ob, f, loc=True, rot=True, scale=False):
    if loc: ob.keyframe_insert("location", frame=f)
    if rot:
        ob.keyframe_insert("rotation_quaternion" if ob.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)
    if scale: ob.keyframe_insert("scale", frame=f)

def linear_fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return
    for fc in _fcurves(ad.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

def _fcurves(action):
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out

def project(sc, cam, co):
    """World point -> pixel coordinates (top-left origin) at current frame."""
    from bpy_extras.object_utils import world_to_camera_view
    v = world_to_camera_view(sc, cam, Vector(co))
    return [round(v.x * sc.render.resolution_x * sc.render.resolution_percentage / 100 / (sc.render.resolution_percentage / 100), 2),
            round((1 - v.y) * sc.render.resolution_y, 2)]

def light_link(sc, light_ob, receivers, name=None):
    """Cycles light linking: light_ob only illuminates `receivers`."""
    col = bpy.data.collections.new(name or (light_ob.name + "_recv"))
    for ob in receivers:
        col.objects.link(ob)
    light_ob.light_linking.receiver_collection = col
    return col

def glare(sc, kind="Bloom", threshold=1.0, strength=0.6, size=0.6, saturation=1.0):
    """Blender 5.x compositor: Render Layers -> Glare -> Group Output."""
    ng = bpy.data.node_groups.new(sc.name + "_comp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers"); rl.scene = sc
    g = ng.nodes.new("CompositorNodeGlare")
    g.inputs["Type"].default_value = kind
    g.inputs["Threshold"].default_value = threshold
    g.inputs["Strength"].default_value = strength
    g.inputs["Size"].default_value = size
    g.inputs["Saturation"].default_value = saturation
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(rl.outputs["Image"], g.inputs["Image"])
    ng.links.new(g.outputs[0], out.inputs[0])
    sc.compositing_node_group = ng
    return g

def mesh_from(ob, name):
    """Evaluated geometry of any object (text, modifiers) as a new mesh datablock."""
    dg = bpy.context.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)

def glow_card(sc, name, w, h, hexcol="#FFFFFF"):
    """Plane whose emission falls off radially to transparent (soft light source seen by camera).
    Returns (object, strength_socket)."""
    bpy.ops.mesh.primitive_plane_add(size=1)
    ob = bpy.context.active_object
    for c in ob.users_collection: c.objects.unlink(ob)
    sc.collection.objects.link(ob); ob.name = name; ob.scale = (w, h, 1)
    m = bpy.data.materials.new(name + "_mat"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Location"].default_value = (-1.0, -1.0, 0); mp.inputs["Scale"].default_value = (2, 2, 1)
    # mapping: uv (0..1) -> (-1..1) after location/scale order (scale applied after location)
    mp.vector_type = "POINT"
    gr = nt.nodes.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 1.6
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[0].default_value = hex_lin(hexcol)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"]); nt.links.new(mp.outputs[0], gr.inputs[0])
    nt.links.new(gr.outputs["Fac"], pw.inputs[0]); nt.links.new(pw.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    ob.data.materials.append(m)
    ob.visible_shadow = False
    return ob, em.inputs[1]
