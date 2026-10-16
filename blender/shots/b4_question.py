"""B4 10.40-12.10 s: a 3D question mark on an ink set splits like two doors on "abren";
light pours through and the camera dollies through the gap until the frame is white at 12.0 s.
"""
import math
import bpy, bmesh
from mathutils import Vector, Matrix, Euler
import lib_sm as L

SHOT = "b4_question"
SPLIT = next(w for w in L.TL["words"] if w["key"] == "abren")["start"]
CZ = 0.95


def half(src_me, name, keep_left, mat_face, mat_cut):
    me = src_me.copy(); me.name = name
    bm = bmesh.new(); bm.from_mesh(me)
    xs = [v.co.x for v in bm.verts]
    cx = (min(xs) + max(xs)) / 2
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(cx, 0, 0), plane_no=(1, 0, 0),
                                 clear_outer=keep_left, clear_inner=not keep_left)
    cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    before = set(bm.faces)
    bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
    for f in bm.faces:
        f.material_index = 0 if f in before else 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.materials.clear(); me.materials.append(mat_face); me.materials.append(mat_cut)
    ob = bpy.data.objects.new(name, me)
    xs = [v.co.x for v in me.vertices]
    hinge = min(xs) if keep_left else max(xs)
    return ob, hinge, cx


def build(preview=False):
    sc, info = L.new_scene(SHOT, preview)
    L.world_color(sc, L.PAL["ink"], 0.2)
    L.link(sc, L.cyclorama("sweep", width=60, depth=40, height=20, radius=4.0,
                           mat=L.matte("ink_sweep", "#15101F", rough=0.5))).location = (0, 3.0, -0.6)

    txt = L.text_obj("q_text", "?", "InstrumentSerif-Italic.ttf", size=2.6, extrude=0.11, bevel=0.018)
    L.link(sc, txt)
    txt.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.view_layer.update()
    src = L.mesh_from(txt, "q_mesh")
    bpy.data.objects.remove(txt, do_unlink=True)
    # recentre: glyph bbox centre to origin in X/Z
    xs = [v.co.x for v in src.vertices]; ys = [v.co.y for v in src.vertices]
    src.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, 0)))
    src.transform(Matrix.Rotation(math.radians(90), 4, "X"))   # stand it up: glyph height along +Z

    face_m = L.plastic("q_violet", L.PAL["violet"], rough=0.26, coat=0.5)
    cut_m = L.satin("q_coral", L.PAL["coral"], rough=0.35, sheen=0.4)
    halves = []
    for keep_left, nm in ((True, "q_left"), (False, "q_right")):
        ob, hinge, cx = half(src, nm, keep_left, face_m, cut_m)
        # put the hinge on the object origin so the door rotates about its outer edge
        ob.data.transform(Matrix.Translation((-hinge, 0, 0)))
        ob.location = (hinge, 0, CZ)
        ob.data.shade_smooth()
        halves.append((L.link(sc, ob), hinge, keep_left))

    # light that pours through the gap
    panel, em = L.glow_card(sc, "panel", 4.6, 4.6, "#FFFFFF")
    panel.rotation_euler = (math.radians(90), 0, 0)
    panel.location = (0, 1.25, CZ)

    cam = L.camera(sc, lens=50, fstop=2.8)
    cam.rotation_mode = "QUATERNION"
    path = [Vector((-2.5, -7.3, 1.12)), Vector((-1.4, -6.3, 1.02)), Vector((-0.3, -4.9, 0.97)),
            Vector((-0.05, -1.5, CZ)), Vector((0.0, 0.25, CZ))]

    L.area(sc, "key", (-4.5, -3.0, 3.8), (0, 0, CZ), 2.6, 700, "#FFF4EC")
    rim1 = L.area(sc, "rimL", (-2.8, 2.6, 2.2), (0, 0, CZ), 1.4, 650, L.PAL["coral"], size_y=0.4)
    rim2 = L.area(sc, "rimR", (2.8, 2.4, 1.0), (0, 0, CZ), 1.4, 420, L.PAL["lilac"], size_y=0.4)
    L.area(sc, "pool", (0.5, 4.0, 4.5), (1.5, 12.0, 1.0), 3.0, 220, "#7B5CFF", spread=60)
    L.reflector(sc, "card", (-1.6, -4.4, 2.2), (0, 0, CZ), 3.0, 1.5, strength=7.0)
    hs = [h[0] for h in halves]
    L.light_link(sc, rim1, hs); L.light_link(sc, rim2, hs)
    L.glare(sc, "Fog Glow", threshold=0.9, strength=0.55, size=0.75)

    def pose(t, f):
        o = L.back_out(L.span(t, SPLIT, SPLIT + 0.42), 1.25)
        for ob, hinge, left in halves:
            ang = 38 * o * (1 if left else -1)
            ob.rotation_euler = Euler((0, 0, math.radians(ang)))
            ob.location = (hinge + (-0.22 if left else 0.22) * L.out_cubic(L.span(t, SPLIT, SPLIT + 0.5)), 0.0,
                           CZ + 0.015 * math.sin(2 * math.pi * (t - 10.4) / 1.7))
            L.key(ob, f)
        em.default_value = L.lerp(0.06, 9.0, L.smooth(L.span(t, SPLIT - 0.05, SPLIT + 0.45)))
        em.keyframe_insert("default_value", frame=f)
        # orbit until the split, then accelerate through the gap
        p = 0.5 * L.out_cubic(L.span(t, 10.4, SPLIT)) + 0.5 * L.in_cubic(L.span(t, SPLIT + 0.08, 12.10))
        loc = L.catmull(path, p)
        tgt = Vector((0, 1.25, CZ)).lerp(Vector((0.0, 0.0, CZ)), 1 - L.smooth(L.span(p, 0.45, 0.8)))
        cam.location = loc
        d = (tgt - loc)
        if d.length < 0.05: d = Vector((0, 1, 0))
        cam.rotation_quaternion = d.to_track_quat("-Z", "Z") @ Euler((0, 0, math.radians(-4 * (1 - p)))).to_quaternion()
        cam.data.dof.focus_distance = max(0.3, (Vector((0, 0, CZ)) - loc).length)
        cam.data.dof.keyframe_insert("focus_distance", frame=f)
        L.key(cam, f)

    L.bake(sc, info, pose)
    for ob, _, _ in halves: L.linear_fcurves(ob)
    L.linear_fcurves(cam)
    return sc
