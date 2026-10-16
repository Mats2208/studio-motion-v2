"""B6 17.00-18.00 s: montage card "3D" — the cursor turns 120 degrees while its wireframe
resolves into the shaded violet plastic. Ink set; the cursor sits in the right half (x ~ 1350 px)."""
import math
from mathutils import Vector, Euler
import bpy
import lib_sm as L

SHOT = "b6_wire"


def build(preview=False):
    sc, info = L.new_scene(SHOT, preview)
    L.world_color(sc, L.PAL["ink"], 0.2)
    L.link(sc, L.cyclorama("sweep", width=40, depth=24, height=14, radius=3.5,
                           mat=L.matte("ink_sweep", "#15101F", rough=0.55))).location = (0, 2.0, -1.6)
    solid_m = L.plastic("violet_plastic", L.PAL["violet"], 0.22, 0.6)
    pb = solid_m.node_tree.nodes["Principled BSDF"]
    solid = L.link(sc, L.cursor("cursor", 1.0, 0.12, solid_m))
    solid.modifiers["bevel"].width = 0.035
    wire = L.link(sc, L.cursor("cursor_wire", 1.0, 0.12, L.emission("wire", L.PAL["lilac"], 2.2)))
    wire.modifiers["bevel"].width = 0.035; wire.modifiers["bevel"].segments = 3
    tri = wire.modifiers.new("tri", "TRIANGULATE")
    wm = wire.modifiers.new("wire", "WIREFRAME"); wm.thickness = 0.006; wm.use_replace = True
    for ob in (solid, wire):
        ob.rotation_mode = "QUATERNION"

    cam = L.camera(sc, lens=85, fstop=2.8)
    cam.location = (0, -6.8, 0.25); L.look_at(cam, (0, 0, 0.05))
    cam.data.dof.focus_object = solid
    X = 390 / 1080 * (0.2382 * 6.8)          # 390 px right of centre
    L.area(sc, "key", (-5.0, -2.2, 3.6), (X, 0, 0), 2.4, 650, "#FFF4EC")
    L.area(sc, "rim", (X + 2.4, 2.6, 2.2), (X, 0, 0.1), 1.6, 900, L.PAL["coral"], size_y=0.4)
    L.area(sc, "pool", (X + 1.0, 4.0, 4.5), (X + 2.0, 12.0, 1.0), 3.0, 260, "#7B5CFF", spread=60)
    L.reflector(sc, "card", (X - 1.4, -5.2, 1.9), (X, 0, 0), 3.2, 1.6, strength=9.0)
    L.area(sc, "fill", (X + 4.0, -5.0, -1.0), (X, 0, 0), 3.0, 120, L.PAL["lilac"])
    L.area(sc, "strip", (X, -1.2, 3.2), (X, 0, 0), 5.0, 380, "#FFFFFF", size_y=0.35)
    L.area(sc, "front", (X + 1.5, -5.5, 0.8), (X, 0, 0), 2.5, 220, "#FFF4EC")

    def pose(t, f):
        yaw = L.lerp(-80, 18, L.in_out_cubic(L.span(t, 17.0, 18.0)))
        q = Euler((0, 0, math.radians(yaw))).to_quaternion() @ Euler((math.radians(96), 0, 0)).to_quaternion()
        a = L.smooth(L.span(t, 17.15, 17.65))
        for ob in (solid, wire):
            ob.location = (X, 0, 0.03 * math.sin(math.pi * L.span(t, 17, 18)))
            ob.rotation_quaternion = q
            L.key(ob, f)
        pb.inputs["Alpha"].default_value = a
        pb.inputs["Alpha"].keyframe_insert("default_value", frame=f)
        wire.hide_render = a > 0.98
        wire.keyframe_insert("hide_render", frame=f)

    L.bake(sc, info, pose)
    L.linear_fcurves(solid); L.linear_fcurves(wire)
    return sc
