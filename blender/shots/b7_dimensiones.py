"""B7 22.00-23.00 s (alpha): "dimensiones." rises through a holdout edge while perfectly
front-on — reading as flat type, centred at (960, 640) px and 1300 px wide — then tilts
back 16 degrees (and 5 degrees of yaw) as the camera rises, revealing its extrusion under each letter."""
import math
from mathutils import Vector, Euler, Matrix
import bpy
import lib_sm as L

SHOT = "b7_dimensiones"
D = 12.0
FW = 36 / 85 * D
WIDTH_M = 1300 / 1920 * FW
T_IN = L.TL["emphasis"]["dimensiones"]["start"]


def build(preview=False):
    sc, info = L.new_scene(SHOT, preview)
    L.world_color(sc, L.PAL["ink"], 0.35)
    txt = L.text_obj("dim_text", "dimensiones.", "InstrumentSerif-Italic.ttf", size=1.0, extrude=0.055, bevel=0.008)
    txt.data.align_y = "BOTTOM_BASELINE"
    L.link(sc, txt)
    bpy.context.view_layer.update()
    me = L.mesh_from(txt, "dim_mesh")
    bpy.data.objects.remove(txt, do_unlink=True)
    xs = [v.co.x for v in me.vertices]
    s = WIDTH_M / (max(xs) - min(xs))
    me.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, 0, 0)))
    me.transform(Matrix.Scale(s, 4))
    me.transform(Matrix.Rotation(math.radians(90), 4, "X"))
    ob = L.link(sc, bpy.data.objects.new("dimensiones", me))
    me.shade_smooth()
    zs = [v.co.z for v in me.vertices]
    H = max(zs)
    face = L.plastic("dim_violet", L.PAL["violet"], rough=0.24, coat=0.6)
    L.assign(ob, face)

    # holdout plane in front of the text, top edge at the baseline: the text rises from behind it
    bpy.ops.mesh.primitive_plane_add(size=1)
    hp = bpy.context.active_object
    for c in hp.users_collection: c.objects.unlink(hp)
    sc.collection.objects.link(hp); hp.name = "holdout"
    hp.scale = (FW * 2, 3.0, 1); hp.rotation_euler = (math.radians(90), 0, 0)
    hp.location = (0, -0.7, -1.5 - 0.02)
    L.assign(hp, L.holdout())

    # camera: text centre at y = 640 px -> camera looks slightly above the text centre
    zc = H / 2
    FH = FW * 9 / 16
    cam_z = zc + (640 - 540) / 1080 * FH
    cam = L.camera(sc, lens=85, fstop=4.0)
    cam.data.dof.focus_object = ob

    L.area(sc, "key", (-4.0, -6.0, 4.0), (0, 0, zc), 4.0, 2200, "#FFF4EC")
    L.area(sc, "edge", (5.5, 1.5, 1.5), (0, 0, zc), 2.0, 1600, L.PAL["coral"], size_y=0.6)
    L.area(sc, "rim", (-5.5, 2.0, 2.5), (0, 0, zc), 2.0, 900, L.PAL["lilac"], size_y=0.6)
    L.reflector(sc, "card", (-2.0, -9.0, 3.0), (0, 0, zc), 6.0, 2.5, strength=6.0)

    def pose(t, f):
        rise = L.out_expo(L.span(t, T_IN, T_IN + 0.32))
        ob.location = (0, 0, L.lerp(-H * 1.15, 0, rise))
        turn = L.in_out_cubic(L.span(t, T_IN + 0.30, 23.0))
        ob.rotation_euler = Euler((math.radians(-16 * turn), 0, math.radians(5 * turn)))   # tilt back: depth shows under each letter
        L.key(ob, f, rot=True)
        ang = math.radians(-4 * turn)
        cam.location = (D * math.sin(ang), -D * math.cos(ang) + 0.6 * turn, cam_z + 0.35 * turn)
        L.look_at(cam, (0, 0, cam_z))
        L.key(cam, f)

    L.bake(sc, info, pose)
    L.linear_fcurves(ob); L.linear_fcurves(cam)
    return sc
