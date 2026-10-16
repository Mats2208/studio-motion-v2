"""B8 23.00-25.00 s (alpha): the cursor of the lockup. It swings in from a 70 degree turn,
settles into a near-front pose at (560, 520) px, 250 px tall, then bobs and drifts — never frozen."""
import math
from mathutils import Euler
import bpy
import lib_sm as L

SHOT = "b8_logo"
D = 10.0
FH = 0.2382 * D
CX = (560 - 960) / 1080 * FH
CZ = -(520 - 540) / 1080 * FH
HEIGHT = 250 / 1080 * FH


def build(preview=False):
    sc, info = L.new_scene(SHOT, preview)
    L.world_color(sc, "#F4F0EA", 0.9)
    cur = L.link(sc, L.cursor("cursor", HEIGHT, 0.13, L.plastic("violet_plastic", L.PAL["violet"], 0.22, 0.6)))
    cur.modifiers["bevel"].width = HEIGHT * 0.035
    cur.rotation_mode = "QUATERNION"
    cam = L.camera(sc, lens=85, fstop=5.6)
    cam.location = (0, -D, 0); L.look_at(cam, (0, 0, 0))
    cam.data.dof.focus_object = cur
    L.area(sc, "key", (-3.0, -6.0, 3.5), (CX, 0, CZ), 3.0, 900, "#FFF6EE")
    L.area(sc, "fill", (3.0, -5.0, 0.0), (CX, 0, CZ), 3.0, 200, L.PAL["lilac"])
    rim = L.area(sc, "rim", (CX + 1.6, 2.0, 1.6), (CX, 0, CZ), 1.0, 500, L.PAL["coral"], size_y=0.3)
    L.reflector(sc, "card", (CX - 1.2, -6.0, 1.6), (CX, 0, CZ), 3.0, 1.4, strength=8.0)

    def pose(t, f):
        a = L.span(t, 23.0, 23.65)
        yaw = L.lerp(-70, 10, L.back_out(a, 1.3)) + 5 * L.smooth(L.span(t, 23.65, 25.0))
        s = L.lerp(0.72, 1.0, L.out_cubic(a))
        bob = 0.02 * math.sin(2 * math.pi * (t - 23.0) / 1.6) * L.smooth(L.span(t, 23.4, 23.9))
        cur.location = (CX, 0, CZ + bob + 0.12 * (1 - L.out_cubic(a)))
        cur.rotation_quaternion = (Euler((0, 0, math.radians(yaw))).to_quaternion()
                                   @ Euler((math.radians(90 + 6), 0, 0)).to_quaternion()
                                   @ Euler((0, math.radians(-8 * (1 - L.out_cubic(a))), 0)).to_quaternion())
        cur.scale = (s, s, s)
        L.key(cur, f, scale=True)

    L.bake(sc, info, pose)
    L.linear_fcurves(cur)
    return sc
