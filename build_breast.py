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
# The needle enters in line with the probe's long axis, at its foot end - the way a
# freehand US-guided biopsy is actually done. Running it across the probe is what made the
# shaft collide with the handle no matter where the probe was put.
entry  = Vector((lump.x - 0.070, lump.y - 0.010, lump.z + 0.040))
tip    = lump + (lump - entry).normalized() * 0.022   # crosses the lump and exits
d      = (tip - entry).normalized()

cyl("needle__shaft", entry - d*0.050, tip, 0.0018, METAL)
cyl("needle__guide", entry - d*0.018, entry + d*0.008, 0.0030, PROBE, 20)
cyl("needle__hub",   entry - d*0.050, entry - d*0.070, 0.0055, WHITE, 20)
tb = box("needle__trough", tip - d*0.010, (0.0016, 0.0022, 0.014), METAL, bevel=0.0004)
tb.rotation_mode = 'QUATERNION'; tb.rotation_quaternion = d.to_track_quat('Z','Y')

# ------------------------------------------------------------ ultrasound probe
# A linear-array transducer, not a box: a thin head with a strip footprint, a narrower
# handle behind it and a cable stub. It sits medial to the needle track so the two never
# share space - a needle entering at the probe's lateral edge and running beneath it is
# the geometry the frames need to read.
# ---------------------------------------------------------- ultrasound probe
# Geometry follows the FNAC leaflet's probe, which reads correctly: a flat rectangular
# footprint ON the skin, a tapered body behind it, a cylindrical handle angled up and back,
# and a cable. The skin normal here is +Z and the long axis runs head-to-foot (Y).
px, py = lump.x - 0.006, lump.y + 0.022
zs = []
for dx in (-0.011, 0.0, 0.011):
    for dy in (-0.024, 0.0, 0.024):
        hit, loc, nor, idx = body.ray_cast(Vector((px + dx, py + dy, 0.5)), Vector((0, 0, -1)))
        if hit:
            zs.append(loc.z)
skin_z = max(zs) if zs else 0.0985

FOOT_LEN, FOOT_WID, FOOT_H = 0.052, 0.016, 0.004      # along Y, along X, thickness
GAP = 0.0015                                            # hovers a hair above the skin
base = skin_z + GAP

probe_parts = [
    box("probe__footprint", Vector((px, py, base + FOOT_H / 2)),
        (FOOT_WID, FOOT_LEN, FOOT_H), WHITE, bevel=0.0012),
    box("probe__body", Vector((px, py, base + FOOT_H + 0.014)),
        (FOOT_WID * 1.15, FOOT_LEN * 0.42, 0.028), PROBE, bevel=0.0035),
]
# handle: 28 deg off the skin normal, leaning back toward the head end
hd_start = Vector((px, py + 0.006, base + 0.030))
hd_dir = Vector((0.0, math.sin(math.radians(28)), math.cos(math.radians(28))))
hd_end = hd_start + hd_dir * 0.085
probe_parts.append(cyl("probe__handle", hd_start, hd_end, 0.013, PROBE, 18))
cb_dir = Vector((0.0, math.sin(math.radians(42)), math.cos(math.radians(42))))
probe_parts.append(cyl("probe__cable", hd_end, hd_end + cb_dir * 0.070, 0.006, PROBE, 12))

# Sit the assembly flush with the sloping breast rather than hovering at one edge.
def _skin_at(x, y):
    hit, loc, nor, idx = body.ray_cast(Vector((x, y, 0.5)), Vector((0, 0, -1)))
    return loc.z if hit else skin_z
slope = (_skin_at(px, py + 0.024) - _skin_at(px, py - 0.024)) / 0.048
tilt = max(-0.17, min(0.17, math.atan(slope)))   # cap the tilt; a steep slope would bury an edge
pivot = Vector((px, py, base))
R = (Matrix.Translation(pivot) @ Matrix.Rotation(tilt, 4, 'X') @ Matrix.Translation(-pivot))
for o in probe_parts:
    o.matrix_world = R @ o.matrix_world

# Turn the assembly a quarter turn about the skin normal: its long axis then runs along X,
# the same axis the needle travels, so probe, lesion and needle share one imaging plane -
# which is how a freehand ultrasound-guided biopsy is actually set up.
Rz = (Matrix.Translation(Vector((px, py, base))) @ Matrix.Rotation(math.radians(90), 4, 'Z')
      @ Matrix.Translation(-Vector((px, py, base))))
for o in probe_parts:
    o.matrix_world = Rz @ o.matrix_world
print("PROBE footprint", FOOT_LEN, "x", FOOT_WID, "m | tilt", round(math.degrees(tilt), 1),
      "deg | long axis along X, in line with the needle")

# ------------------------------------------------------------- clearance check
# True separation between the needle shaft and the whole probe, not just an x-gap: sample the
# shaft and measure each sample's distance to the probe box.
probe_objs = [bpy.data.objects[n] for n in
              ('probe__body', 'probe__handle', 'probe__footprint', 'probe__cable')]
pb = []
for o in probe_objs:
    pb += [o.matrix_world @ Vector(c) for c in o.bound_box]
pmin = Vector((min(v[i] for v in pb) for i in range(3)))
pmax = Vector((max(v[i] for v in pb) for i in range(3)))

def box_dist(q, lo, hi):
    d = Vector((max(lo[i] - q[i], 0.0, q[i] - hi[i]) for i in range(3)))
    return d.length

inside, near = 0, 9.9
for k in range(41):
    q = entry.lerp(tip, k / 40)
    inside += 1 if all(pmin[i] < q[i] < pmax[i] for i in range(3)) else 0
    near = min(near, box_dist(q, pmin, pmax))
print("PROBE size", tuple(round(pmax[i] - pmin[i], 3) for i in range(3)),
      "| bottom z", round(pmin.z, 4), "| skin z", round(skin_z, 4))
print("NEEDLE entry", tuple(round(c, 3) for c in entry), "tip", tuple(round(c, 3) for c in tip))
print("CLEARANCE", round(near, 4), "m | shaft samples inside probe:", inside)

bpy.ops.mesh.primitive_torus_add(location=lump + Vector((0,0,0.004)),
                                 major_radius=0.0022, minor_radius=0.0005,
                                 major_segments=24, minor_segments=8)
c = bpy.context.active_object; c.name = "clip__marker"; c.data.materials.append(CLIPM)
c.rotation_euler = Euler((math.radians(78), 0, math.radians(20)), 'XYZ')
bpy.ops.object.shade_smooth()

# Dressing built like the FNAC leaflet's: a gauze pad flattened onto the skin at the entry
# point, with an adhesive strip across it.
hit, dloc, dnor, didx = body.ray_cast(Vector((entry.x, entry.y, 0.5)), Vector((0, 0, -1)))
d_skin = dloc.z if hit else skin_z
PAD_R, PAD_H = 0.016, 0.0022
cyl("dressing__pad", Vector((entry.x, entry.y, d_skin + PAD_H)),
    Vector((entry.x, entry.y, d_skin + GAP)), PAD_R, WHITE, 28)
box("dressing__strip", Vector((entry.x, entry.y, d_skin + PAD_H + 0.0012)),
    (PAD_R * 1.9, PAD_R * 0.55, 0.0016), WHITE, bevel=0.0006)

def _skin(x, y):
    hit, loc, nor, idx = body.ray_cast(Vector((x, y, 0.5)), Vector((0, 0, -1)))
    return loc.z if hit else lump.z + 0.030

# ------------------------------------------------ local anaesthetic syringe
# The anaesthetic goes in AT the point where the biopsy needle will enter, so that is where
# the syringe sits: needle tip on the skin at the entry point, barrel standing off from it.
s_tip  = Vector((entry.x, entry.y, _skin(entry.x, entry.y) + 0.001))
s_dir  = (lump - s_tip).normalized()
needle_back = s_tip - s_dir*0.026
barrel0 = needle_back - s_dir*0.004
barrel1 = barrel0 - s_dir*0.050
cyl("syringe__needle", s_tip, needle_back, 0.0006, METAL, 10)
cyl("syringe__hub",    needle_back, barrel0, 0.0018, WHITE, 12)
cyl("syringe__barrel", barrel0, barrel1, 0.0050, WHITE, 20)
cyl("syringe__plunger", barrel1, barrel1 - s_dir*0.024, 0.0022, PROBE, 12)
cyl("syringe__finger", barrel1, barrel1 - s_dir*0.003, 0.0075, PROBE, 16)
print("SYRINGE tip", tuple(round(c,3) for c in s_tip))

# ------------------------------------------------------------- scalpel
# A scalpel is a flat handle with a slender blade set at an angle to it, not a stick: the
# blade is a wedge that tapers to a cutting edge, mounted off the handle's end.
c_tip = Vector((entry.x - 0.004, entry.y - 0.006, _skin(entry.x, entry.y) + 0.0015))
c_dir = (c_tip - Vector((c_tip.x - 0.045, c_tip.y - 0.055, c_tip.z + 0.060))).normalized()

# handle: flat, thin, running away from the point of the blade
h_end = c_tip + c_dir*0.092
# handle: a flat grip, not a rod - a scalpel handle is a blade-shaped bar
h_mid = (c_tip + c_dir*0.030 + h_end) / 2
hdl = box("scalpel__handle", h_mid, (0.011, 0.006, 0.075), PROBE, bevel=0.002)
hdl.rotation_mode = 'QUATERNION'; hdl.rotation_quaternion = c_dir.to_track_quat('Z','Y')

# blade: triangular prism, apex at the skin, widening back into the handle
import bmesh as _bm
me = bpy.data.meshes.new("scalpel_blade")
bm = _bm.new()
side = c_dir.cross(Vector((0, 0, 1)))
if side.length < 1e-6:
    side = Vector((1, 0, 0))
side.normalize()
up = side.cross(c_dir).normalized()
L, W, T = 0.030, 0.0055, 0.0009
apex = c_tip
base = c_tip + c_dir*L
v = [bm.verts.new(apex + up*T), bm.verts.new(apex - up*T),
     bm.verts.new(base + side*W + up*T), bm.verts.new(base + side*W - up*T),
     bm.verts.new(base - side*W + up*T), bm.verts.new(base - side*W - up*T)]
bm.faces.new((v[0], v[2], v[3], v[1]))
bm.faces.new((v[0], v[1], v[5], v[4]))
bm.faces.new((v[0], v[4], v[2]))
bm.faces.new((v[1], v[3], v[5]))
bm.faces.new((v[2], v[4], v[5], v[3]))
bm.to_mesh(me); bm.free()
blade = bpy.data.objects.new("scalpel__blade", me)
bpy.context.scene.collection.objects.link(blade)
blade.data.materials.append(METAL)
print("SCALPEL blade at", tuple(round(c,3) for c in c_tip))

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
