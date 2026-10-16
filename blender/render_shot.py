"""Background renderer: blender -b studio-motion-v2.blend --python render_shot.py -- <scene> [preview|final] [start] [end]
Leaves the interactive session untouched; renders one scene to renders/<scene>/f_####.png."""
import sys, bpy
args = sys.argv[sys.argv.index("--") + 1:]
name, mode = args[0], (args[1] if len(args) > 1 else "final")
sc = bpy.data.scenes[name]
bpy.context.window_manager.windows[0].scene = sc if bpy.context.window_manager.windows else None
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
sc.cycles.device = "GPU"
if mode == "final":
    sc.render.resolution_percentage = 100
    sc.cycles.samples = int(sc.get("final_samples", 96))
else:
    sc.render.resolution_percentage = 50
    sc.cycles.samples = 16
root = str(__import__("pathlib").Path(bpy.data.filepath).resolve().parents[1])   # <project>/blender/<file>.blend
sc.render.filepath = root + f"/renders/{name}{'' if mode == 'final' else '_preview'}/f_"
if len(args) > 3:
    sc.frame_start, sc.frame_end = int(args[2]), int(args[3])
sc.render.use_persistent_data = True
bpy.ops.render.render(animation=True, scene=sc.name)
print("DONE", name, mode, sc.frame_start, sc.frame_end)
