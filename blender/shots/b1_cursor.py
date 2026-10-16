"""B1 1.50-3.10 s: the caret, seen edge-on, turns into the 3D cursor, holds, then lunges out of frame right.

Frame 1 match: the cursor is exactly edge-on, 600 px tall, centred at x=1300 px, y=540 px,
which is where the HTML caret (after "idea.") has grown to; it holds edge-on until 1.62 s.
"""
import math
from mathutils import Vector, Matrix, Euler
import lib_sm as L

SHOT = "b1_cursor"
CAM_D0, CAM_D1 = 7.56, 7.15          # 85 mm: frame height = 0.2382 * D -> cursor 1.0 m = 600 px at 7.56 m
X0 = 340 / 1080 * (0.2382 * CAM_D0)   # 340 px right of centre: where the HTML caret ends after "idea." (x=1300)


def build(preview=False):
    sc, info = L.new_scene(SHOT, preview)
    L.world_color(sc, L.PAL["ink"], 0.25)
    sweep = L.link(sc, L.cyclorama("sweep", width=40, depth=24, height=14, radius=3.5,
                                   mat=L.matte("ink_sweep", "#15101F", rough=0.55)))
    sweep.location = (0, 2.0, -1.6)

    cur = L.link(sc, L.cursor("cursor", 1.0, 0.12, L.plastic("violet_plastic", L.PAL["violet"], 0.22, 0.6)))
    cur.modifiers["bevel"].width = 0.035
    cur.rotation_mode = "QUATERNION"

    cam = L.camera(sc, lens=85, fstop=2.8)
    cam.data.dof.focus_object = cur

    L.area(sc, "key", (-5.0, -2.2, 3.6), (0, 0, 0), 2.4, 650, "#FFF4EC")
    L.area(sc, "fill", (4.0, -5.0, -1.0), (0, 0, 0), 3.0, 60, L.PAL["lilac"])
    L.area(sc, "rim", (2.4, 2.6, 2.2), (0, 0, 0.1), 1.6, 900, L.PAL["coral"], size_y=0.4)
    L.area(sc, "pool", (1.0, 4.0, 4.5), (2.0, 12.0, 1.0), 3.0, 260, "#7B5CFF", spread=60)
    L.area(sc, "strip", (0.0, -1.2, 3.2), (0, 0, 0), 5.0, 300, "#FFFFFF", size_y=0.35)
    L.reflector(sc, "card", (-1.4, -5.2, 1.9), (X0, 0, 0), 3.2, 1.6, strength=9.0)

    def pose(t, f):
        # yaw: 90 deg (edge-on) -> 22 deg hero with a gentle overshoot, then drift
        a = L.span(t, 1.62, 2.35)              # 1.50-1.62 edge-on hold for the caret crossfade
        yaw = L.lerp(90, 22, L.back_out(a, 1.15))
        yaw -= 3 * L.smooth(L.span(t, 2.35, 2.55))
        pitch = 8 * L.out_cubic(a)
        roll = 0.0
        loc = Vector((X0, 0.0, 0.0 + 0.02 * L.smooth(L.span(t, 1.5, 2.5))))
        # anticipation 2.50-2.60, lunge 2.60-3.10
        ant = L.in_out_sine(L.span(t, 2.50, 2.60)) * (1 - L.span(t, 2.60, 2.70))
        yaw += 4 * ant
        loc.y += 0.10 * ant
        lu = L.in_cubic(L.span(t, 2.60, 3.10))
        loc += Vector((1.95, -4.3, 0.38)) * lu
        yaw += -48 * lu
        roll += 24 * lu
        pitch += -10 * lu
        cur.location = loc
        q = (Euler((0, 0, math.radians(yaw))).to_quaternion()
             @ Euler((math.radians(90 + pitch), 0, 0)).to_quaternion()
             @ Euler((0, math.radians(roll), 0)).to_quaternion())
        cur.rotation_quaternion = q
        L.key(cur, f)
        d = L.lerp(CAM_D0, CAM_D1, L.smooth(L.span(t, 1.5, 3.1)))
        cam.location = (0.04 * L.smooth(L.span(t, 1.5, 3.1)), -d, 0.0)
        L.look_at(cam, (0.04 * L.smooth(L.span(t, 1.5, 3.1)), 0, 0))
        L.key(cam, f)

    L.bake(sc, info, pose)
    L.linear_fcurves(cur); L.linear_fcurves(cam)
    return sc
