"""B3 9.00-10.40 s: the drawn coral stroke lifts off the paper as a 3D ribbon.

Frame 1 is a straight-down 50 mm view from 7.0 m; the ribbon centre line is the unprojection
of timeline.json stroke_px onto z=0, so it overlays the HTML stroke. The ribbon is a strip mesh
whose shape for every frame is a shape key (exact per frame, linear blend in between for motion blur).
"""
import math
import bpy, bmesh
from mathutils import Vector, Matrix
import lib_sm as L

SHOT = "b3_ribbon"
H = 7.0
LENS, SENSOR = 50.0, 36.0
FW = SENSOR / LENS * H            # ground width covered by the frame
FH = FW * 9 / 16
N = 240                           # segments along the ribbon
W0, W1 = 18 / 1920 * FW, 0.16     # stroke width (18 px) -> ribbon width
T0 = 9.0


def px_to_ground(px, py):
    return Vector(((px - 960) / 1920 * FW, (540 - py) / 1080 * FH, 0.0))


def centre_line():
    pts = [px_to_ground(x, y) for x, y in L.TL["stroke_px"]]
    return [L.catmull(pts, i / N) for i in range(N + 1)]


BASE = None


def ribbon(t):
    """Returns (left, right) vertex lists for time t."""
    global BASE
    if BASE is None:
        BASE = centre_line()
    lift = L.smoother(L.span(t, 9.04, 10.25))
    w = L.lerp(W0, W1, L.out_cubic(L.span(t, 9.02, 9.55)))
    tt = t - T0
    left, right = [], []
    for i, p in enumerate(BASE):
        u = i / N
        q = BASE[min(i + 1, N)] - BASE[max(i - 1, 0)]
        tan = q.normalized()
        z = 0.006 + lift * (0.12 + 0.95 * math.sin(math.pi * u) ** 1.2 + 0.18 * math.sin(2 * math.pi * (1.4 * u - 0.9 * tt)))
        # gather toward the middle slightly as it rises, giving a sculptural S
        c = Vector((p.x * (1 - 0.18 * lift), p.y * (1 - 0.35 * lift) + 0.25 * lift * math.sin(math.pi * u), z))
        theta = lift * (3 * math.pi * u + 0.6 * math.sin(2 * math.pi * (u - 0.5 * tt)))
        side = tan.cross(Vector((0, 0, 1))).normalized()
        side = Matrix.Rotation(theta, 3, tan) @ side
        left.append(c + side * w / 2)
        right.append(c - side * w / 2)
    return left, right


def build(preview=False):
    global BASE
    BASE = None
    sc, info = L.new_scene(SHOT, preview)
    L.world_color(sc, "#F1ECE6", 1.35)
    floor_m = L.matte("paper", L.PAL["paper"], rough=0.92)
    bpy.ops.mesh.primitive_plane_add(size=400)
    floor = bpy.context.active_object
    for c in floor.users_collection: c.objects.unlink(floor)
    sc.collection.objects.link(floor); floor.name = "paper"; L.assign(floor, floor_m)

    # strip mesh
    me = bpy.data.meshes.new("ribbon")
    bm = bmesh.new()
    l, r = ribbon(T0)
    vl = [bm.verts.new(v) for v in l]; vr = [bm.verts.new(v) for v in r]
    for i in range(N):
        f = bm.faces.new((vl[i], vr[i], vr[i + 1], vl[i + 1]))
    bm.normal_update()
    if sum(f.normal.z for f in bm.faces) < 0:
        for f in bm.faces: f.normal_flip()
    bm.to_mesh(me); bm.free()
    rib = L.link(sc, bpy.data.objects.new("ribbon", me))
    me.shade_smooth()
    rib.data.materials.append(L.satin("coral_satin", "#FF3F1F", rough=0.46, sheen=0.0))
    rib.data.materials.append(L.satin("violet_satin", L.PAL["violet"], rough=0.36, sheen=0.3))
    so = rib.modifiers.new("solid", "SOLIDIFY"); so.thickness = 0.012; so.offset = -1
    so.material_offset = 1; so.material_offset_rim = 0
    sub = rib.modifiers.new("sub", "SUBSURF"); sub.levels = 1; sub.render_levels = 2

    # per-frame shape keys
    rib.shape_key_add(name="Basis", from_mix=False)
    nf = info["frames"]
    for f in range(1, nf + 1):
        t = L.t_of(info, f)
        l, r = ribbon(t)
        sk = rib.shape_key_add(name=f"f{f:03d}", from_mix=False)
        n = len(l)
        for i in range(n):
            sk.data[i].co = l[i]; sk.data[n + i].co = r[i]
        for ff, v in ((f - 1, 0.0), (f, 1.0), (f + 1, 0.0)):
            sk.value = v; sk.keyframe_insert("value", frame=ff)
    for fc in L._fcurves(me.shape_keys.animation_data.action):
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"

    cam = L.camera(sc, lens=LENS, fstop=5.6)
    cam.rotation_mode = "QUATERNION"
    path = [Vector((0, 0, H)), Vector((-0.9, -1.7, 5.2)), Vector((-2.3, -3.1, 2.3)), Vector((-2.7, -2.7, 1.05))]
    tgts = [Vector((0, 0, 0)), Vector((0.0, 0.1, 0.1)), Vector((0.2, 0.3, 0.4)), Vector((0.35, 0.45, 0.55))]

    L.area(sc, "key", (-1.5, -2.5, 9.0), (0, 0, 0), 9.0, 1750, "#FFF8F0")
    L.area(sc, "fill", (5.0, -4.0, 2.5), (0, 0, 0.4), 4.0, 260, L.PAL["lilac"])
    L.area(sc, "kick", (3.0, 3.5, 3.0), (0, 0, 0.5), 2.0, 420, "#FFFFFF")
    L.reflector(sc, "card", (-3.5, -4.5, 3.0), (0, 0, 0.5), 4.0, 2.0, strength=5.0)

    def pose(t, f):
        p = L.in_out_cubic(L.span(t, 9.13, 10.40))
        loc = L.catmull(path, p)
        tgt = L.catmull(tgts, p)
        fwd = (tgt - loc).normalized()
        uphint = Vector((0, 1, 0)).lerp(Vector((0, 0, 1)), L.smooth(L.span(p, 0.0, 0.6))).normalized()
        right = fwd.cross(uphint).normalized()
        up = right.cross(fwd)
        m = Matrix((right, up, -fwd)).transposed()
        cam.location = loc
        cam.rotation_quaternion = m.to_quaternion() @ Matrix.Rotation(math.radians(-6 * math.sin(math.pi * p)), 4, "Z").to_quaternion()
        cam.data.dof.focus_distance = (tgt - loc).length
        cam.data.dof.keyframe_insert("focus_distance", frame=f)
        L.key(cam, f)

    L.bake(sc, info, pose)
    L.linear_fcurves(cam)
    return sc


def match_error():
    """Max pixel distance between the frame-1 ribbon centre line and stroke_px."""
    sc = bpy.data.scenes[SHOT]
    sc.frame_set(1)
    cam = sc.camera
    err = 0.0
    line = centre_line()
    for k, (x, y) in enumerate(L.TL["stroke_px"]):
        u = k / 63
        p = line[round(u * N)]
        px = L.project(sc, cam, p)
        err = max(err, math.hypot(px[0] * (1920 / sc.render.resolution_x) - x, px[1] * (1080 / sc.render.resolution_y) - y))
    return round(err, 2)
