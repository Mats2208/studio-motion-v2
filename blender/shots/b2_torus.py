"""B2 3.00-7.30 s: the object inside the design app viewport (1560x990, shown at 1040x660).

3.00-4.00 wireframe only, 4.00-4.60 clay fades in under the wire, wire gone by 5.00.
Material switches on the beats the HTML cursor clicks: 5.00 violet glass, 5.50 coral satin,
6.00 lilac chrome, 6.50 final violet plastic + it comes alive (squash, stretch, half turn, jump).
"""
import math
from mathutils import Vector, Euler
import bpy
import lib_sm as L

SHOT = "b2_torus"
SWITCH = [5.0, 5.5, 6.0, 6.5]
BASE_Z = 0.98


def torus(sc, name, mat, seg=(96, 48)):
    bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.21, major_segments=seg[0], minor_segments=seg[1])
    ob = bpy.context.active_object
    for c in ob.users_collection:
        c.objects.unlink(ob)
    sc.collection.objects.link(ob)
    ob.name = name
    ob.data.shade_smooth()
    L.assign(ob, mat)
    ob.rotation_mode = "XYZ"
    return ob


def build(preview=False):
    sc, info = L.new_scene(SHOT, preview)
    L.world_color(sc, "#F1EDF8", 0.8)
    L.link(sc, L.cyclorama("sweep", width=24, depth=16, height=10, radius=2.5,
                           mat=L.matte("viewport_sweep", L.PAL["viewport"], rough=0.9))).location = (0, 3.0, 0)

    clay = L.matte("clay", "#F3F0EC", rough=0.55)
    p = clay.node_tree.nodes["Principled BSDF"]
    wire_m = L.emission("wire", L.PAL["violet"], 1.0)
    variants = {
        "glass": L.glass("v_glass", "#9C7BFF", rough=0.04, ior=1.45),
        "coral": L.satin("v_coral", L.PAL["coral"], rough=0.36, sheen=0.4),
        "chrome": L.chrome("v_chrome", "#CFC3FF", rough=0.16),
        "violet": L.plastic("v_violet", L.PAL["violet"], rough=0.2, coat=0.7),
    }
    objs = {"clay": torus(sc, "t_clay", clay)}
    wire = torus(sc, "t_wire", wire_m, seg=(36, 18))
    md = wire.modifiers.new("wire", "WIREFRAME"); md.thickness = 0.0065; md.use_replace = True
    wire.data.polygons.foreach_set("use_smooth", [False] * len(wire.data.polygons))
    for k, m in variants.items():
        objs[k] = torus(sc, "t_" + k, m)
    order = ["clay", "glass", "coral", "chrome", "violet"]

    cam = L.camera(sc, lens=50, fstop=4.0)
    cam.location = (0, -5.2, 1.85)
    L.look_at(cam, (0, 0, BASE_Z + 0.05))
    cam.data.dof.focus_distance = (Vector((0, 0, BASE_Z)) - cam.location).length

    L.area(sc, "key", (-3.0, -2.5, 4.4), (0, 0, BASE_Z), 4.0, 560, "#FFF6EE")
    L.area(sc, "fill", (3.6, -2.8, 1.6), (0, 0, BASE_Z), 3.0, 160, L.PAL["lilac"])
    rim = L.area(sc, "rim", (1.6, 2.2, 2.6), (0, 0, BASE_Z), 1.0, 260, L.PAL["coral"], size_y=0.4, spread=35)
    L.area(sc, "wall", (0, -1.0, 5.5), (0, 6.0, 2.0), 6.0, 900, "#FFFFFF", size_y=3.0, spread=90)
    L.reflector(sc, "card", (-1.2, -3.4, 2.6), (0, 0, BASE_Z), 2.6, 1.4, strength=6.0)

    L.light_link(sc, rim, list(objs.values()) + [wire])

    def alpha_mat(mat, a):
        pb = mat.node_tree.nodes["Principled BSDF"]
        pb.inputs["Alpha"].default_value = a

    def pose(t, f):
        # which solid is visible
        idx = sum(1 for s in SWITCH if t >= s)
        for i, k in enumerate(order):
            ob = objs[k]
            ob.hide_render = ob.hide_viewport = (i != idx)
            ob.keyframe_insert("hide_render", frame=f); ob.keyframe_insert("hide_viewport", frame=f)
        clay_a = L.smooth(L.span(t, 4.0, 4.6))
        p.inputs["Alpha"].default_value = clay_a
        p.inputs["Alpha"].keyframe_insert("default_value", frame=f)
        wa = 1.0 - L.smooth(L.span(t, 4.6, 5.0))
        wire.hide_render = wire.hide_viewport = wa <= 0.001
        wire.keyframe_insert("hide_render", frame=f); wire.keyframe_insert("hide_viewport", frame=f)
        wire_m.node_tree.nodes["Emission"].inputs[1].default_value = 1.6 * wa
        wire_m.node_tree.nodes["Emission"].inputs[1].keyframe_insert("default_value", frame=f)

        # base motion: slow turn, gentle float
        yaw = 70 * L.in_out_sine(L.span(t, 3.0, 6.5))
        tilt = 62 - 6 * L.smooth(L.span(t, 3.0, 4.2))
        z = BASE_Z + 0.03 * math.sin(2 * math.pi * (t - 3.0) / 2.0)
        sx = sy = sz = 1.0
        # beat pops on each material switch
        for s in SWITCH[:3]:
            if t >= s:
                sx += 0.04 * L.damped((t - s) / 0.45, 1.5, 4.0) * (1 if t - s < 0.45 else 0)
        sy = sz = sx
        # comes alive at 6.50: anticipation squash, stretch on take-off, jump with half turn, land squash
        if t >= 6.5:
            a = L.span(t, 6.50, 6.60); b = L.span(t, 6.60, 6.75)
            squash = math.sin(math.pi * a) * (1 - b)
            stretch = math.sin(math.pi * b)
            sz = 1 - 0.14 * squash + 0.14 * stretch
            sx = sy = 1 + 0.07 * squash - 0.06 * stretch
            j = L.span(t, 6.62, 7.28)
            z += 0.55 * 4 * j * (1 - j)
            yaw += 180 * L.in_out_cubic(L.span(t, 6.62, 7.20))
            tilt += -14 * math.sin(math.pi * j)
            land = L.span(t, 7.20, 7.30)
            sz *= 1 - 0.10 * math.sin(math.pi * land)
            sx *= 1 + 0.05 * math.sin(math.pi * land); sy = sx
        for ob in list(objs.values()) + [wire]:
            ob.location = (0, 0, z)
            ob.rotation_euler = Euler((math.radians(tilt), 0, math.radians(yaw)))
            ob.scale = (sx, sy, sz)
            L.key(ob, f, scale=True)

    L.bake(sc, info, pose)
    for ob in list(objs.values()) + [wire]:
        L.linear_fcurves(ob)
    return sc
