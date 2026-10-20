"""Build the breast-biopsy scene GLB.

Source: "Human Female Breast Anatomy" by Anatomy by Doctor Jana (Sketchfab), CC-BY-4.0.
It ships as a torso with one breast cut away to show the lobules, ducts and pectoral
muscle - which is exactly the view the opening steps need.

The import arrives under Sketchfab_model/Breast.fbx/RootNode with a ~880-unit parent
offset, so every mesh is baked into world space first and unparented. One uniform matrix
then scales the lot to metres, lays the patient supine (chest toward +Z) and centres the
chest on the origin.

Props are authored here: the lump, an ultrasound probe, a spring-loaded core needle with
its trough, the marker clip and the dressing. Every object is named `role__part`; the
page's loader takes the text before `__` as the role.

    blender -b -P build_breast.py -- model/breast_scene.glb
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix, Euler

SRC = "/Users/alexyap/Downloads/human_female_breast_anatomy.glb"
OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else "model/breast_scene.glb"
os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)

CHEST_W       = 0.46      # metres across the shoulders
LESION_DEPTH  = 0.022     # under the skin surface
LESION_RADIUS = 0.011

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)

# ---------------------------------------------------------------- bake + name
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
body = next(o for o in meshes if 'Body' in o.name)
ROLE_OF = {'Body': 'body', 'Glands': 'gland', 'Ducts': 'duct', 'Muscles': 'muscle'}

for o in meshes:
    o.parent = None
    o.data.transform(o.matrix_world)          # bake the Sketchfab offset into the mesh
    o.matrix_world = Matrix.Identity(4)
    for k, role in ROLE_OF.items():
        if o.name.startswith(k):
            o.name = f"{role}__{o.name.split('_')[0].lower()}"
            break
bpy.context.view_layer.update()

# ------------------------------------------------- metres, supine, centred
bb = [body.matrix_world @ Vector(c) for c in body.bound_box]
width = max(v.x for v in bb) - min(v.x for v in bb)
scale = CHEST_W / max(width, 1e-6)

M = (Matrix.Translation(Vector((0, 0, 0))) @
     Matrix.Rotation(math.radians(90), 4, 'X') @     # standing -> supine, chest faces +Z
     Matrix.Diagonal((scale, scale, scale, 1.0)))
for o in meshes:
    o.data.transform(M)
    o.matrix_world = Matrix.Identity(4)

# centre on the chest, using the gland as the anchor of interest
bpy.context.view_layer.update()
gb = [Vector(c) for c in body.bound_box]
bbmin = Vector((min(v.x for v in gb), min(v.y for v in gb), min(v.z for v in gb)))
bbmax = Vector((max(v.x for v in gb), max(v.y for v in gb), max(v.z for v in gb)))
ctr = (bbmin + bbmax) / 2
for o in meshes:
    o.data.transform(Matrix.Translation(-ctr))
    o.matrix_world = Matrix.Identity(4)
bpy.context.view_layer.update()

gland = next((o for o in bpy.data.objects if o.name.startswith('gland__')), None)
gc = Vector((0, 0, 0))
if gland:
    pts = [gland.matrix_world @ v.co for v in gland.data.vertices]
    gc = sum(pts, Vector()) / len(pts)
print("GLAND CENTRE", tuple(round(c, 4) for c in gc))

# The cut-away breast is left open on purpose: it is the view the opening steps need, and
# filling it (as an earlier pass did) closes it with one enormous flat face that reads as a
# sheet of plastic lying on the chest.

# ---------------------------------------------------------------- materials
def mat(name, color, rough=0.55, metal=0.0, alpha=1.0, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = 'BLEND'
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = 0.5
    return m

SKIN  = mat("m_skin",  (0.90, 0.79, 0.70), 0.62)
LES   = mat("m_lesion",(0.62, 0.14, 0.18), 0.45, emit=(0.3, 0.04, 0.04))
METAL = mat("m_metal", (0.80, 0.82, 0.86), 0.26, metal=0.9)
PROBE = mat("m_probe", (0.18, 0.21, 0.26), 0.45, metal=0.2)
WHITE = mat("m_white", (0.94, 0.95, 0.97), 0.5)
CLIPM = mat("m_clip",  (0.74, 0.76, 0.80), 0.34, metal=0.85)

if body.data.materials:
    body.data.materials[0] = SKIN
else:
    body.data.materials.append(SKIN)

def sphere(n, loc, r, m, segs=40):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=segs, ring_count=segs//2)
    o = bpy.context.active_object; o.name = n; o.data.materials.append(m)
    bpy.ops.object.shade_smooth(); return o

def cyl(n, p0, p1, r, m, v=24):
    p0, p1 = Vector(p0), Vector(p1); d = p1 - p0
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, vertices=v, location=(p0+p1)/2)
    o = bpy.context.active_object; o.name = n; o.data.materials.append(m)
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = d.to_track_quat('Z','Y')
    bpy.ops.object.shade_smooth(); return o

def box(n, loc, size, m, bevel=0.003):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object; o.name = n; o.data.materials.append(m)
    o.scale = size; bpy.ops.object.transform_apply(scale=True)
    if bevel:
        md = o.modifiers.new("b", 'BEVEL'); md.width = bevel; md.segments = 3
        bpy.ops.object.modifier_apply(modifier=md.name)
    return o

# ---------------------------------------------------------------- the lump
lump = Vector((gc.x, gc.y, gc.z))
sphere("lesion__lump", lump, LESION_RADIUS, LES, 40)

# ------------------------------------------------------------ probe + needle
entry  = Vector((lump.x - 0.062, lump.y, lump.z + 0.052))
tip    = lump + Vector((0, 0, 0))
d      = (tip - entry).normalized()

cyl("needle__shaft", entry - d*0.050, tip, 0.0018, METAL)
cyl("needle__guide", entry - d*0.018, entry + d*0.008, 0.0030, PROBE, 20)
cyl("needle__hub",   entry - d*0.050, entry - d*0.070, 0.0055, WHITE, 20)
tb = box("needle__trough", tip - d*0.010, (0.0016, 0.0022, 0.014), METAL, bevel=0.0004)
tb.rotation_mode = 'QUATERNION'; tb.rotation_quaternion = d.to_track_quat('Z','Y')

# Seat the probe on the actual skin, found by casting down from above at its footprint.
fx, fy = lump.x - 0.050, lump.y + 0.010
hit, loc, nor, idx = body.ray_cast(Vector((fx, fy, 0.5)), Vector((0, 0, -1)))
skin_z = loc.z if hit else lump.z + 0.045
foot = Vector((fx, fy, skin_z))
box("probe__body", foot + Vector((0, 0, 0.024)), (0.034, 0.056, 0.048), PROBE, bevel=0.008)
box("probe__footprint", foot + Vector((0, 0, 0.001)), (0.030, 0.020, 0.004), WHITE)
print("PROBE SEAT", round(skin_z, 4), "hit", hit)

bpy.ops.mesh.primitive_torus_add(location=lump + Vector((0,0,0.004)),
                                 major_radius=0.0022, minor_radius=0.0005,
                                 major_segments=24, minor_segments=8)
c = bpy.context.active_object; c.name = "clip__marker"; c.data.materials.append(CLIPM)
c.rotation_euler = Euler((math.radians(78), 0, math.radians(20)), 'XYZ')
bpy.ops.object.shade_smooth()

cyl("dressing__pad", entry + Vector((0,0,0.002)), entry - Vector((0,0,0.0005)), 0.016, WHITE, 32)

# ------------------------------------------------------------------- export
# The page assigns its own materials per role (app_scene.js), so the source textures would
# only add ~9 MB of image data to a file that is inlined into the HTML.
RATIO = {'duct': 0.18, 'body': 0.82, 'muscle': 0.7, 'gland': 0.9}
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    o.data.materials.clear()
    role = o.name.split('__')[0]
    r = RATIO.get(role)
    if r:
        bpy.context.view_layer.objects.active = o
        md = o.modifiers.new("dec", 'DECIMATE'); md.ratio = r
        bpy.ops.object.modifier_apply(modifier=md.name)
        for poly in o.data.polygons:
            poly.use_smooth = True
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True,
                          export_apply=True, export_yup=True)
print("WROTE", OUT, os.path.getsize(OUT))
for o in bpy.data.objects:
    if o.type == 'MESH':
        print("  part", o.name, len(o.data.vertices))
