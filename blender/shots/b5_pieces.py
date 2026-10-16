"""B5 13.40-16.00 s: seven scattered pieces lock into a sculpture on eighth notes;
the cursor lands last, on top, exactly on "lugar" (15.00 s). Exports each snap's screen
position to renders/b5_snaps.json for the HTML alignment guides.
"""
import json, math, random
import bpy
from mathutils import Vector, Euler, Quaternion
import lib_sm as L

SHOT = "b5_pieces"
TOP = 0.25
SNAPS = L.TL["events"]["snaps"]
TARGET = Vector((0.05, 0, TOP + 0.62))


def prim(sc, kind, name, mat, **kw):
    if kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=kw["r"], depth=kw["h"])
    elif kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=kw["r"])
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=96, radius1=kw["r"], depth=kw["h"])
    elif kind == "torus":
        bpy.ops.mesh.primitive_torus_add(major_radius=kw["R"], minor_radius=kw["r"], major_segments=96, minor_segments=40)
    ob = bpy.context.active_object
    for c in ob.users_collection: c.objects.unlink(ob)
    sc.collection.objects.link(ob); ob.name = name
    if kind in ("cyl", "cone"):
        md = ob.modifiers.new("bevel", "BEVEL"); md.width = 0.02; md.segments = 5; md.harden_normals = True
    ob.data.shade_smooth()
    L.assign(ob, mat)
    return ob


def build(preview=False):
    sc, info = L.new_scene(SHOT, preview)
    L.world_color(sc, "#F1ECE6", 0.8)
    L.link(sc, L.cyclorama("sweep", width=40, depth=26, height=14, radius=4.0,
                           mat=L.matte("paper", L.PAL["paper"], rough=0.9))).location = (0, 4.0, 0)
    rng = random.Random(L.TL["seed"])

    lilac = L.plastic("lilac", L.PAL["lilac"], rough=0.3, coat=0.4)
    coral = L.satin("coral", L.PAL["coral"], rough=0.36, sheen=0.35)
    violet = L.plastic("violet", L.PAL["violet"], rough=0.22, coat=0.6)
    white = L.ceramic("ceramic")

    plinth = prim(sc, "cyl", "plinth", white, r=0.85, h=TOP)
    plinth.location = (0, 0, TOP / 2)

    pieces = []  # (object, slot_loc, slot_rot(euler deg), snap_time)
    cube = L.link(sc, L.rounded_box("cube", (0.62, 0.62, 0.62), 0.06)); L.assign(cube, lilac)
    pieces.append((cube, Vector((-0.22, 0.0, TOP + 0.31)), (0, 0, 8), SNAPS[0]))
    cyl = prim(sc, "cyl", "cylinder", coral, r=0.2, h=0.62)
    pieces.append((cyl, Vector((0.36, -0.04, TOP + 0.31)), (0, 0, 0), SNAPS[1]))
    slab = L.link(sc, L.rounded_box("slab", (1.08, 0.42, 0.12), 0.04)); L.assign(slab, violet)
    pieces.append((slab, Vector((0.07, -0.02, TOP + 0.68)), (0, 0, 4), SNAPS[2]))
    sph = prim(sc, "sphere", "sphere", white, r=0.17)
    pieces.append((sph, Vector((-0.36, -0.02, TOP + 0.74 + 0.17)), (0, 0, 0), SNAPS[3]))
    cone = prim(sc, "cone", "cone", lilac, r=0.13, h=0.3)
    pieces.append((cone, Vector((0.52, -0.5, TOP + 0.15)), (0, 0, 0), SNAPS[4]))
    tor = prim(sc, "torus", "torus", violet, R=0.19, r=0.075)
    pieces.append((tor, Vector((0.39, -0.02, TOP + 0.74 + 0.265)), (90, 0, 10), SNAPS[5]))
    cur = L.link(sc, L.cursor("cursor", 0.56, 0.13, violet))
    pieces.append((cur, Vector((-0.03, -0.02, TOP + 0.74 + 0.285)), (90, 0, -8), SNAPS[6]))

    # scatter poses: a loose ring around the plinth, different heights, slow independent spin
    scatter = []
    for i, (ob, slot, rot, ts) in enumerate(pieces):
        ang = math.radians(-150 + i * 47 + rng.uniform(-10, 10))
        rad = rng.uniform(1.25, 1.75)
        pos = Vector((rad * math.cos(ang), rad * math.sin(ang) * 0.6 - 0.2, rng.uniform(0.7, 2.1)))
        spin = Vector((rng.uniform(-40, 40), rng.uniform(-40, 40), rng.uniform(-60, 60)))
        base = Vector((rng.uniform(-30, 30), rng.uniform(-30, 30), rng.uniform(0, 360)))
        scatter.append((pos, base, spin))
        ob.rotation_mode = "QUATERNION"

    cam = L.camera(sc, lens=50, fstop=4.0)
    L.area(sc, "key", (-3.2, -3.0, 4.2), TARGET, 3.6, 560, "#FFF6EE")
    L.area(sc, "fill", (3.8, -2.6, 1.6), TARGET, 3.0, 220, L.PAL["lilac"])
    rim = L.area(sc, "rim", (1.5, 2.6, 3.0), TARGET, 1.4, 420, L.PAL["coral"], size_y=0.5, spread=40)
    L.area(sc, "wall", (0, -1.5, 6.0), (0, 8.0, 2.5), 7.0, 800, "#FFFFFF", size_y=3.0, spread=90)
    L.reflector(sc, "card", (-1.8, -3.6, 2.6), TARGET, 3.0, 1.5, strength=5.0)
    L.light_link(sc, rim, [p[0] for p in pieces])

    def pose(t, f):
        for i, (ob, slot, rot, ts) in enumerate(pieces):
            pos, base, spin = scatter[i]
            tt = t - 13.4
            float_pos = pos + Vector((0, 0, 0.05 * math.sin(2 * math.pi * (tt / 1.9 + i * 0.13))))
            q_float = Euler([math.radians(b + s * tt) for b, s in zip(base, spin)]).to_quaternion()
            q_slot = Euler([math.radians(a) for a in rot]).to_quaternion()
            a = L.out_cubic(L.span(t, ts - 0.42, ts))
            # arc in: lift over the sculpture on the way
            loc = float_pos.lerp(slot, a) + Vector((0, 0, 0.35 * math.sin(math.pi * a)))
            q = q_float.slerp(q_slot, L.smoother(L.span(t, ts - 0.42, ts - 0.04)))
            sq = 0.0
            if t >= ts:
                sq = 0.08 * L.damped((t - ts) / 0.5, 2.0, 5.5)
            ob.location = loc
            ob.rotation_quaternion = q
            ob.scale = (1 + sq * 0.5, 1 + sq * 0.5, 1 - sq)
            L.key(ob, f, scale=True)
        ang = math.radians(L.lerp(-22, 13, L.in_out_sine(L.span(t, 13.4, 16.0))))
        r = 5.3 - 0.25 * L.smooth(L.span(t, 13.4, 16.0))
        cam.location = (r * math.sin(ang), -r * math.cos(ang), L.lerp(1.55, 1.85, L.smooth(L.span(t, 13.4, 16.0))))
        L.look_at(cam, TARGET)
        cam.data.dof.focus_distance = (TARGET - cam.location).length
        cam.data.dof.keyframe_insert("focus_distance", frame=f)
        L.key(cam, f)

    L.bake(sc, info, pose)
    for p in pieces: L.linear_fcurves(p[0])
    L.linear_fcurves(cam)

    # screen positions of every snap, for the HTML guides (1920x1080 space)
    snaps = []
    for ob, slot, rot, ts in pieces:
        fr = round((ts - info["start"]) * L.FPS) + 1
        sc.frame_set(fr)
        px = L.project(sc, cam, slot)
        k = 1920 / sc.render.resolution_x
        snaps.append({"piece": ob.name, "t": ts, "frame": fr, "x": round(px[0] * k, 1), "y": round(px[1] * (1080 / sc.render.resolution_y), 1)})
    (L.RENDER_DIR / "b5_snaps.json").write_text(json.dumps(snaps, indent=1))
    sc.frame_set(1)
    return sc
