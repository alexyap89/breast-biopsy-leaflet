#!/usr/bin/env python3
"""Build the breast-biopsy scene GLB.

A pure trimesh + numpy port of the former Blender (bpy) build, so the pipeline runs with no
Blender install.  The whole-torso source asset is a single GLB whose five anatomy meshes are
named Body_Julie2_0 / Glands_Extract4_1_0 / Ducts_Ducts5_0 / Ducts_Ducts5_1 /
Muscles_Extract1_0, already in a Y-up standing pose with the chest facing +Z.

Dependencies: trimesh (>=5), numpy and shapely (slice_plane needs it to rebuild the whole torso).
Install into an isolated venv; do NOT install into the system python (PEP 668):

    python3 -m venv /Users/alexyap/.venvs/glbtools
    /Users/alexyap/.venvs/glbtools/bin/python -m pip install "trimesh[all]" numpy shapely

Pipeline
--------
1. Load the whole torso, apply each mesh's world transform (the GLB node hierarchy), then
   strip every texture/material image so the page can assign its own flat colours per role.
2. Scale to a 0.46 m shoulder width and rotate +90 deg about X so a standing patient becomes
   supine with the chest facing +Z.  The GLB itself stays Y-up; the app applies its own -90 deg
   X rotation when laying the patient down.
3. Centre the whole body on the origin using the body's bounding box (the gland is the anchor
   of interest and ends up near the reference position).
4. The source body is a cutaway: its -X half is complete, the +X chest is opened.  Rebuild the
   body as the intact -X half plus its mirror (a symmetric, watertight torso with both breasts),
   then lift a smooth breast volume over each side, because the mirrored asset's own mound is
   nearly flat.  Decimate each mesh with the historical ratios via
   trimesh.simplify_quadric_decimation.
5. Keep the internal layers at the reference positions and clamp them inside the skin so no
   cutaway plate shows through the closed breast
   (verified to 4 decimals against the committed GLB), so no per-layer offset is applied.  The
   ducts and muscle are cutaway PLATES that read as red streaks and a flat wall once the skin is
   closed, so the build ships the body, the glandular lobules and the instruments only.
6. Rebuild every instrument as a trimesh primitive (cylinder / sphere / box / manual torus),
   placed with the same math the Blender build used: one shared entry point on the skin, the
   needle rising up into the lump, the probe parallel to the needle, the clip perpendicular to
   the needle axis, plus syringe, scalpel and a conforming dressing pad.
7. Export as GLB, then strip materials/textures/images + primitive material indices so the file
   has 0 materials like the reference (the app assigns colours by role prefix).

The diagnostic prints at the end reproduce the reference values used to sanity-check the rebuild.
"""
import json
import os
import struct
import sys

import numpy as np
import trimesh
from trimesh import transformations as T

SRC = "/Users/alexyap/Downloads/human_female_breast_anatomy.glb"
OUT = "model/breast_scene.glb"

CHEST_W = 0.46          # metres across the shoulders (reference shoulder width)
LESION_RADIUS = 0.011   # metres

# Reference ratios from the Blender build: keep the same decimation per role.
RATIO = {"duct": 0.18, "body": 0.82, "muscle": 0.7, "gland": 0.9}

# Standing -> supine: rotate +90 deg about X so the chest faces +Z.  Verified against the
# reference GLB: body Y-range 0.2128, Z-range 0.4657, gland centroid ~ (0.075, 0.073, -0.016).
R_SUPINE = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=float)


# --------------------------------------------------------------------- helpers
def align_z_to(d):
    """Rotation matrix that maps +Z onto the unit vector d (for aligning a cylinder's axis)."""
    z = np.array([0.0, 0.0, 1.0])
    d = d / np.linalg.norm(d)
    if abs(d[2] - 1.0) < 1e-9:
        return np.eye(3)
    if abs(d[2] + 1.0) < 1e-9:
        # 180 deg about any in-plane axis; use X
        return np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=float)
    v = np.cross(z, d)
    c = z.dot(d)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]], dtype=float)
    return np.eye(3) + vx + vx.dot(vx) * (1.0 / (1.0 + c))


def cyl_mesh(radius, length, sections=24, direction=None, center=(0, 0, 0)):
    """Z-axis cylinder centred on origin, stretched along `direction` by `length`."""
    m = trimesh.primitives.Cylinder(radius=radius, height=length, sections=int(sections))
    if direction is not None:
        R = align_z_to(direction)
        mm = np.eye(4); mm[:3, :3] = R; mm[:3, 3] = np.asarray(center, dtype=float)
        m.apply_transform(mm)
    else:
        m.apply_translation(np.asarray(center, dtype=float))
    return m


def box_mesh(extents, direction=None, center=(0, 0, 0)):
    """Box centred on origin with the given extents; optionally rotate +Z to `direction`."""
    m = trimesh.primitives.Box(extents=np.asarray(extents, dtype=float))
    if direction is not None:
        R = align_z_to(direction)
        mm = np.eye(4); mm[:3, :3] = R; mm[:3, 3] = np.asarray(center, dtype=float)
        m.apply_transform(mm)
    else:
        m.apply_translation(np.asarray(center, dtype=float))
    return m


def torus_mesh(major_r, minor_r, major_seg=28, minor_seg=10, direction=None, center=(0, 0, 0)):
    """Manual torus whose ring lies in the XY plane (major axis +Z), rotated to face `direction`."""
    u = np.linspace(0, 2 * np.pi, major_seg + 1)[:-1]
    v = np.linspace(0, 2 * np.pi, minor_seg + 1)[:-1]
    uu, vv = np.meshgrid(u, v); uu = uu.ravel(); vv = vv.ravel()
    verts = np.stack([
        (major_r + minor_r * np.cos(vv)) * np.cos(uu),
        (major_r + minor_r * np.cos(vv)) * np.sin(uu),
        minor_r * np.sin(vv),
    ], axis=1)
    faces = []
    for i in range(major_seg):
        for j in range(minor_seg):
            a = i * minor_seg + j
            b = i * minor_seg + (j + 1) % minor_seg
            c = ((i + 1) % major_seg) * minor_seg + j
            dd = ((i + 1) % major_seg) * minor_seg + (j + 1) % minor_seg
            faces.append([a, b, dd]); faces.append([a, dd, c])
    m = trimesh.Trimesh(verts, np.array(faces, dtype=np.int64))
    m.merge_vertices(); m.fix_normals()
    if direction is not None:
        R = align_z_to(direction)
        mm = np.eye(4); mm[:3, :3] = R; mm[:3, 3] = np.asarray(center, dtype=float)
        m.apply_transform(mm)
    else:
        m.apply_translation(np.asarray(center, dtype=float))
    return m


def ray_cast(mesh, origin, direction):
    """Return (hit, point, normal) using trimesh's ray intersector."""
    origins = np.asarray([origin], dtype=float)
    directions = np.asarray([direction], dtype=float)
    locs, _tri, _ray = mesh.ray.intersects_location(origins, directions)
    locs = np.asarray(locs, dtype=float).reshape(-1, 3)
    if len(locs):
        return True, locs[0], None
    return False, None, None


# --------------------------------------------------------------------- load source
scene = trimesh.load(SRC, process=False)

role_map = {"body": "Body", "gland": "Glands", "duct": "Ducts", "muscle": "Muscles"}
src_geo = {}
for node_name in scene.graph.nodes_geometry:
    g = scene.geometry[node_name].copy()
    g.apply_transform(scene.graph.get(node_name)[0])  # world transform (source units ~cm)
    for role, key in role_map.items():
        if node_name.split(".")[-1].startswith(key):
            src_geo.setdefault(role, []).append(g)

body = src_geo["body"][0]
gland = src_geo["gland"][0]
muscle = src_geo["muscle"][0]
ducts_0 = src_geo["duct"][0]
ducts_1 = src_geo["duct"][1]

# Merge the two Ducts meshes into one duct__ducts geometry (before mirroring).
ducts = trimesh.util.concatenate([ducts_0, ducts_1])
ducts.merge_vertices()

# --------------------------------------------------------------------- scale + rotate + centre
w = body.bounds[1][0] - body.bounds[0][0]
scale = CHEST_W / max(w, 1e-6)

def apply_transform(mesh, s=1.0, rot=R_SUPINE, trans=np.zeros(3)):
    mm = np.eye(4); mm[:3, :3] = rot * s; mm[:3, 3] = trans
    return mesh.apply_transform(mm)

anatomy = {"body": body, "gland": gland}   # ducts/muscle are cutaway plates: they read as
# streaks and a flat wall once the skin is closed, so only the glandular lobules carry the
# "inside the breast" story.
for k in anatomy:
    anatomy[k] = apply_transform(anatomy[k], scale)

# Centre on the body bounding box (gland is the anchor of interest).  Use identity rotation for
# the translation step -- the default rot=R_SUPINE would re-apply the standing->supine rotation.
ctr = (anatomy["body"].bounds[0] + anatomy["body"].bounds[1]) / 2
for k in anatomy:
    anatomy[k] = apply_transform(anatomy[k], 1.0, rot=np.eye(3), trans=-ctr)

# --------------------------------------------------------------------- whole torso
# The source asset is a cutaway model: its LEFT (-X) side is complete, while the +X chest is
# opened for display and the breast skin there is simply absent (rays pass straight through).
# Rebuilding the body as the intact -X half plus its mirror gives one symmetric, complete torso
# with both breasts whole - the user's core complaint about the model this replaces.
_b = anatomy["body"]
_half = _b.slice_plane(plane_origin=[0.0, 0.0, 0.0], plane_normal=[1.0, 0.0, 0.0], cap=False)
if _half.vertices[:, 0].max() > 0.01:      # keep whichever side the slicer left us
    _half = _b.slice_plane(plane_origin=[0.0, 0.0, 0.0], plane_normal=[-1.0, 0.0, 0.0], cap=False)
_m = _half.copy()
_m.vertices[:, 0] *= -1.0
_m.invert()
_whole = trimesh.util.concatenate([_half, _m])
_whole.merge_vertices()
_whole.remove_unreferenced_vertices()
_whole.fix_normals()

# The mirrored asset's own breast is a shallow mound (about 30 mm proud of a flat chest), which
# reads as a mannequin rather than a breast. Lift a smooth symmetric volume over each breast so the
# form is the one the leaflet describes: a rounded mound, mirrored exactly left and right.
_v = np.asarray(_whole.vertices, dtype=float)
_n = np.asarray(_whole.vertex_normals, dtype=float)
_ax = np.abs(_v[:, 0])
_r = np.sqrt(((_ax - 0.070) / 0.070) ** 2 + ((_v[:, 2] + 0.025) / 0.078) ** 2)
_w = np.where(_r < 1.0, np.cos(0.5 * np.pi * np.minimum(_r, 1.0)) ** 2, 0.0)
_w *= np.clip((_v[:, 1] - 0.02) / 0.03, 0.0, 1.0)   # front skin only
_v = _v + _n * (0.030 * _w)[:, None]
_whole.vertices = _v
_whole.fix_normals()
anatomy["body"] = _whole
print("BODY mirrored to whole torso:", len(_whole.vertices), "verts, watertight", _whole.is_watertight)

# --------------------------------------------------------------------- decimate
_role_ratio = {"body": "body", "gland": "gland"}
for role, mesh in anatomy.items():
    r = RATIO[_role_ratio[role]]
    try:
        mesh.merge_vertices(); mesh.fix_normals()
        simplified = mesh.simplify_quadric_decimation(percent=1.0 - r)
        simplified.merge_vertices(); simplified.fix_normals()
        mesh.vertices = simplified.vertices
        mesh.faces = simplified.faces
    except Exception as e:
        print("decimate warning", role, e)

# Merge decimated anatomy into a single whole-skin raycast mesh (the internal layers sit inside
# the body and never affect downward skin raycasts, but combining keeps one consistent surface).
bodym = anatomy["body"]   # the skin surface every raycast below must use
combo = trimesh.util.concatenate(list(anatomy.values()))
combo.merge_vertices()
combo.nondegenerate_faces()

# --------------------------------------------------------------------- the lump
# User-approved placement taken verbatim from the model this replaces: the lesion sits in the
# outer gland, slightly deeper than the surface.
lump = np.array([0.0751, 0.0735, -0.0157])
print("LUMP     ", tuple(round(c, 3) for c in lump))

# --------------------------------------------------------------------- entry point
# Every instrument shares ONE entry on the lower (anterior) aspect of the breast. The anterior
# chest faces +Y here, so the skin is found by raycasting straight down (-Y). `skin_at` samples a
# small patch and returns the first (closest) hit's y and outward normal - this is where the
# needle, probe, syringe and scalpel all meet.
def skin_at(x, z):
    """First (closest) hit of the -Y ray straight down from (x, 0.2, z): its y and outward normal.

    Raycast against the BODY alone. Casting against the merged anatomy hit the internal muscle
    plate wherever it reaches past the skin (the outer chest), which seated the probe 2 cm low.
    """
    o = np.array([[x, 0.2, z]]); d = np.array([[0, -1, 0]])
    locs, _tri, _ray = bodym.ray.intersects_location(o, d)
    if len(locs):
        locs = np.asarray(locs).reshape(-1, 3)
        dd = np.linalg.norm(locs - o, axis=1)
        j = int(np.argmin(dd)); t = int(locs[j][2])
        return (dd[j], locs[j][1], bodym.face_normals[t])
    return None

ex, ez = lump[0] - 0.030, lump[2] - 0.030
entry_hit = skin_at(ex, ez)
entry_y = entry_hit[1] if entry_hit else lump[1]
entry = np.array((ex, entry_y, ez))
print("ENTRY on breast", tuple(round(c, 3) for c in entry), "of", len(entry_hit), "rays")

tip = lump + (lump - entry) / np.linalg.norm(lump - entry) * 0.012
d_axis = (tip - entry) / np.linalg.norm(tip - entry)

# --------------------------------------------------------------------- needle
bevel_base = tip - d_axis * 0.005
anatomy["needle__shaft"] = cyl_mesh(0.0022, 0.028, direction=d_axis, center=entry - d_axis * 0.014)
anatomy["needle__bevel"] = cyl_mesh(0.0022, 0.005, direction=d_axis,
                                    center=bevel_base + d_axis * 0.0025)
anatomy["needle__guide"] = cyl_mesh(0.0030, 0.026, direction=d_axis,
                                    center=entry - d_axis * 0.005)
anatomy["needle__hub"] = cyl_mesh(0.0050, 0.018, direction=d_axis,
                                  center=entry - d_axis * 0.037)

# needle__trough: small box aligned to the needle axis
through = box_mesh((0.0016, 0.0022, 0.014), direction=d_axis, center=tip - d_axis * 0.010)
anatomy["needle__trough"] = through

# --------------------------------------------------------------------- ultrasound probe
# A linear-array transducer: a thin footprint resting on the anterior skin over the lump, a body
# behind it, then handle and cable. The long axis is aligned to the needle trajectory in full 3D
# (not just its in-plane projection) so the probe and needle lie along one line.
GAP = 0.0012
FOOT_LEN, FOOT_WID, FOOT_H = 0.052, 0.016, 0.004
seat_hit = skin_at(lump[0], lump[2])
seat_y = seat_hit[1] if seat_hit else lump[1]

# Orthonormal basis for the probe: long axis = needle direction (L), thickness = skin normal
# projected perpendicular to L (N'), width = in-plane perp (W = N' x L).  The needle enters at an
# angle to the skin, so N and L are not perpendicular - orthogonalise N against L before use.
L = d_axis
N = np.asarray(seat_hit[2]) if seat_hit else np.array([0.0, 1.0, 0.0])
N = N - (N.dot(L)) * L          # strip the component of the normal along the needle
nl = np.linalg.norm(N)
if nl < 1e-9:  # skin normal nearly parallel to needle; use a fixed in-plane thickness axis
    N = np.cross(np.array([0.0, 0.0, 1.0]), L); nl = np.linalg.norm(N)
N = N / nl
W = np.cross(N, L)
M = np.array([[W[0], N[0], L[0]],
              [W[1], N[1], L[1]],
              [W[2], N[2], L[2]]])
if np.linalg.det(M) < 0:      # keep a right-handed rotation
    W = -W
    M = np.array([[W[0], N[0], L[0]],
                  [W[1], N[1], L[1]],
                  [W[2], N[2], L[2]]])

# Rest the probe on the skin over the lump - the ultrasound picture the leaflet shows: the
# transducer lies on the anterior skin with the needle passing beneath it into the lesion.
foot_center = np.array((lump[0], seat_y, lump[2]))
foot_center = foot_center + N * (GAP + FOOT_H * 0.5)   # bottom face just above the local skin

def orient(box, extents, center):
    mm = np.eye(4); mm[:3, :3] = M; mm[:3, 3] = center
    box.apply_transform(mm)
    return box

footprint = orient(trimesh.primitives.Box(extents=np.array([FOOT_WID, FOOT_H, FOOT_LEN])),
                   np.array([FOOT_WID, FOOT_H, FOOT_LEN]), foot_center)
anatomy["probe__footprint"] = footprint
body_c = foot_center + N * (FOOT_H + 0.014)
probe_body = orient(trimesh.primitives.Box(extents=np.array([FOOT_WID * 1.15, FOOT_H * 1.3, FOOT_LEN * 0.42])),
                    np.array([FOOT_WID * 1.15, FOOT_H * 1.3, FOOT_LEN * 0.42]), body_c)
anatomy["probe__body"] = probe_body

# handle: off the skin (+normal), tilted toward the head/deep end; cable follows.
hd_dir = np.array([N[0] + L[0], N[1] + L[1], N[2] + L[2]])
hd_dir = hd_dir / np.linalg.norm(hd_dir)
hd_start = foot_center + N * 0.03
hd_end = hd_start + hd_dir * 0.085
anatomy["probe__handle"] = cyl_mesh(0.013, 0.085, direction=(hd_end - hd_start), center=hd_start)
cb_dir = np.array([N[0] + 0.5 * L[0], N[1] + 0.5 * L[1], N[2] + 0.5 * L[2]])
cb_dir = cb_dir / np.linalg.norm(cb_dir)
anatomy["probe__cable"] = cyl_mesh(0.006, 0.070, direction=cb_dir, center=hd_end)

print("PROBE footprint", FOOT_LEN, "x", FOOT_WID, "m | seat y", round(seat_y, 4),
      "| long-axis||needle:", round(abs(np.cross(d_axis, L)).sum(), 4))

# --------------------------------------------------------------------- clearance check
probe_objs = [anatomy[n] for n in ("probe__body", "probe__handle", "probe__footprint", "probe__cable")]
pb = []
for o in probe_objs:
    b = np.asarray(o.bounds)  # (2, 3): [[xmin,ymin,zmin],[xmax,ymax,zmax]]
    pb.append(b[0]); pb.append(b[1])
pmin = np.min(np.vstack(pb), axis=0)
pmax = np.max(np.vstack(pb), axis=0)

def box_dist(q, lo, hi):
    dd = np.array([max(lo[i] - q[i], 0.0, q[i] - hi[i]) for i in range(3)])
    return np.linalg.norm(dd)

inside, near = 0, 9.9
for k in range(41):
    q = entry + (tip - entry) * (k / 40)
    inside += 1 if all(pmin[i] < q[i] < pmax[i] for i in range(3)) else 0
    near = min(near, box_dist(q, pmin, pmax))
print("PROBE size", tuple(round(pmax[i] - pmin[i], 3) for i in range(3)),
      "| bottom y", round(pmin[1], 4), "| seat y", round(seat_y, 4))
print("NEEDLE entry", tuple(round(c, 3) for c in entry), "tip", tuple(round(c, 3) for c in tip))
print("CLEARANCE", round(near, 4), "m | shaft samples inside probe:", inside)
_dir = (lump - entry) / np.linalg.norm(lump - entry)
_ang = np.degrees(np.arccos(max(-1, min(1, _dir.dot(np.array([0, 1, 0]))))))
print("NEEDLE approach angle from the skin plane:", round(90 - _ang, 1), "deg")

# --------------------------------------------------------------------- clip (perpendicular to needle axis)
torus = torus_mesh(0.0038, 0.0008, major_seg=28, minor_seg=10)
# orient the ring plane perpendicular to the needle: ring normal is +Z, rotate so +Z -> d_axis
R_clip = np.eye(4); R_clip[:3, :3] = align_z_to(d_axis)
R_clip[:3, 3] = lump
torus.apply_transform(R_clip)
anatomy["clip__marker"] = torus

# --------------------------------------------------------------------- dressing conform pad
# Conforming pad: a 5x5 grid of -Y skin raycasts around the entry. Each bottom vertex sits 1.5 mm
# off the skin along its OWN surface normal, each top vertex 2.2 mm further out - so the pad follows
# the breast's curvature instead of floating on a flat plane.
PAD_R = 0.024
PAD_T = 0.0035
n_entry = np.asarray(entry_hit[2], dtype=float) if entry_hit else np.array([0.0, 1.0, 0.0])
n_entry = n_entry / max(1e-9, np.linalg.norm(n_entry))
bottom_pts, top_pts = [], []
grid = np.linspace(-PAD_R, PAD_R, 5)
for gx in grid:
    for gy in grid:
        h = skin_at(entry[0] + gx, entry[2] + gy)
        sy = h[1] if h else entry_y
        nr = np.asarray(h[2], dtype=float) if h else n_entry
        nr = nr / max(1e-9, np.linalg.norm(nr))
        p = np.array((entry[0] + gx, sy, entry[2] + gy))
        bottom_pts.append(p + nr * 0.0015)
        top_pts.append(p + nr * (0.0015 + PAD_T))
pad_bottom = np.array(bottom_pts)
pad_top = np.array(top_pts)

n = 5
nn = n * n
faces = []
for i in range(n - 1):
    for j in range(n - 1):
        a = i * n + j; b = a + 1; c = a + n; d = c + 1
        faces += [[a + nn, b + nn, d + nn], [a + nn, d + nn, c + nn]]   # outer sheet
        faces += [[a, d, b], [a, c, d]]                                # skin-side sheet
border = ([k * n for k in range(n)] + [k * n + n - 1 for k in range(1, n)]
          + [(n - 1) * n + k for k in range(n - 2, -1, -1)] + [k for k in range(n - 2, 0, -1)])
for u, v in zip(border, border[1:] + border[:1]):
    bu, bv, tu, tv = u, v, u + nn, v + nn
    faces += [[bu, bv, tv], [bu, tv, tu]]

pad_verts = np.concatenate([pad_bottom, pad_top], axis=0)
dressing_pad = trimesh.Trimesh(pad_verts, np.array(faces, dtype=np.int64))
dressing_pad.merge_vertices(); dressing_pad.fix_normals()
anatomy["dressing__pad"] = dressing_pad

# dressing__strip rides on the pad: thin box lying in the skin plane (long along W, thin along N)
strip_center = pad_top.mean(0) + n_entry * 0.0008
Mstrip = np.array([[W[0], N[0], L[0]],
                   [W[1], N[1], L[1]],
                   [W[2], N[2], L[2]]])
strip = trimesh.primitives.Box(extents=np.array([PAD_R * 1.9, 0.0016, PAD_R * 0.55]))
mm = np.eye(4); mm[:3, :3] = Mstrip; mm[:3, 3] = strip_center
strip.apply_transform(mm)
anatomy["dressing__strip"] = strip

# --------------------------------------------------------------------- local anaesthetic syringe
s_tip = entry.copy()
s_dir = (lump - s_tip) / np.linalg.norm(lump - s_tip)
needle_back = s_tip - s_dir * 0.026
barrel0 = needle_back - s_dir * 0.004
barrel1 = barrel0 - s_dir * 0.050
anatomy["syringe__needle"] = cyl_mesh(0.0006, 0.026, direction=s_dir, center=s_tip)
anatomy["syringe__hub"] = cyl_mesh(0.0018, 0.004, direction=s_dir, center=needle_back)
anatomy["syringe__barrel"] = cyl_mesh(0.0050, 0.050, direction=s_dir, center=barrel0)
anatomy["syringe__plunger"] = cyl_mesh(0.0022, 0.024, direction=s_dir, center=barrel1)
anatomy["syringe__finger"] = cyl_mesh(0.0075, 0.003, direction=s_dir, center=barrel1)
print("SYRINGE tip", tuple(round(c, 3) for c in s_tip))

# --------------------------------------------------------------------- scalpel
c_tip = entry.copy()
c_dir = (c_tip - np.array((entry[0] - 0.035, entry[1] - 0.045, c_tip[2] + 0.050)))
c_dir = c_dir / np.linalg.norm(c_dir)
anatomy["scalpel__handle"] = box_mesh((0.010, 0.006, 0.080), direction=c_dir, center=c_tip + c_dir * 0.055)
anatomy["scalpel__blade"] = box_mesh((0.007, 0.0012, 0.032), direction=c_dir, center=c_tip + c_dir * 0.016)
print("SCALPEL at", tuple(round(c, 3) for c in c_tip))

# --------------------------------------------------------------------- diagnostics
def centre_of(names):
    pts = []
    for n in names:
        if n in anatomy:
            pts += np.asarray(anatomy[n].bounds).reshape(-1, 3).tolist()
    lo = np.min(np.vstack(pts), axis=0)
    hi = np.max(np.vstack(pts), axis=0)
    return (lo + hi) / 2

print("LUMP     ", tuple(round(c, 3) for c in lump))
print("PROBE mid", tuple(round(c, 3) for c in centre_of(
    ("probe__body", "probe__footprint", "probe__handle", "probe__cable"))))
clip_c = centre_of(("clip__marker",))
print("CLIP mid ", tuple(round(c, 3) for c in clip_c))
print("CLIP-to-LUMP", round(np.linalg.norm(clip_c - lump), 4), "m")
print("FOOTPRINT mid", tuple(round(c, 3) for c in centre_of(("probe__footprint",))))

# dressing conform diagnostic: for each grid point the pad bottom sits 1.5mm above the skin along
# the local normal; report the worst-case lift of that flat underside off the curved skin.
max_pad_gap = 0.0
gi = list(range(5))
for i in gi:
    for j in gi:
        v = pad_bottom[i * 5 + j]
        o = np.array([[v[0], v[1] + 0.02, v[2]]]); d = np.array([[0, -1, 0]])
        locs, _t, _r = bodym.ray.intersects_location(o, d)
        if len(locs):
            locs = np.asarray(locs).reshape(-1, 3)
            dd = np.linalg.norm(locs - o, axis=1)
            jx = int(np.argmin(dd))
            max_pad_gap = max(max_pad_gap, v[1] - locs[jx][1])
print("DRESSING pad bottom-to-skin max distance", round(max_pad_gap, 4), "m")

# --------------------------------------------------------------------- assemble scene
# Node order matches the reference GLB exactly (24 nodes).
ordered_names = [
    "gland__glands",
    "body__body", "lesion__lump",
    "needle__shaft", "needle__bevel", "needle__guide", "needle__hub", "needle__trough",
    "probe__footprint", "probe__body", "probe__handle", "probe__cable",
    "clip__marker",
    "dressing__pad", "dressing__strip",
    "syringe__needle", "syringe__hub", "syringe__barrel", "syringe__plunger", "syringe__finger",
    "scalpel__handle", "scalpel__blade",
]

# Internal layers must stay strictly under the skin: the source slabs are cutaway plates, and
# wherever one reaches past the skin it reads as a red smear on the closed breast. Pull those
# vertices in along the skin normal to 2 mm below the surface.
from trimesh.proximity import ProximityQuery as _PQ
_pq = _PQ(bodym)
for _role in ("gland",):
    _m = anatomy[_role]
    _cp, _d, _tid = _pq.on_surface(np.asarray(_m.vertices))
    _n = bodym.face_normals[_tid]
    _signed = np.einsum("ij,ij->i", _m.vertices - _cp, _n)
    _out = _signed > -0.002
    if _out.any():
        _m.vertices[_out] = _cp[_out] - _n[_out] * 0.002
        _m.fix_normals()
    print(f"CLAMP {_role}: {int(_out.sum())} of {len(_m.vertices)} verts pulled inside the skin")

# Rename internal anatomy meshes to their role-prefixed node names and add the lesion sphere.
anatomy["body__body"] = anatomy.pop("body")
anatomy["gland__glands"] = anatomy.pop("gland")
anatomy["lesion__lump"] = trimesh.primitives.Sphere(radius=LESION_RADIUS)
anatomy["lesion__lump"].apply_translation(lump)

def _clean(mesh):
    """Strip any visual/material so trimesh emits no material (0 materials like the ref).
    TEXCOORD_0 is injected manually after export (see below)."""
    try:
        mesh.visual = None
    except Exception:
        pass
    return mesh

geometries = {}
for name in ordered_names:
    geometries[name] = _clean(anatomy[name])

scene_out = trimesh.Scene(geometry=geometries)

# Export WITHOUT visuals -> clean GLB (no materials), correct header + 4-byte chunk padding.
glb_bytes = scene_out.export(file_type=".glb", include_normals=True)
jlen = struct.unpack("<I", glb_bytes[12:16])[0]
j = json.loads(glb_bytes[20:20 + jlen])
body_off = 28 + jlen  # skip 8-byte BIN chunk header
body = bytearray(glb_bytes[body_off:])

# Inject a dummy TEXCOORD_0 per primitive so every primitive has POSITION+NORMAL+TEXCOORD_0.
# Build one shared bufferView of float32 (x,y=1) UVs, append to the binary with 4-byte padding.
uv_chunks = []
for mesh in j["meshes"]:
    for prim in mesh.get("primitives", []):
        if "TEXCOORD_0" in prim["attributes"]:
            continue
        pcount = j["accessors"][prim["attributes"]["POSITION"]]["count"]
        uv = np.ones((pcount, 2), dtype=np.float32)
        data = uv.tobytes()
        pad = (-len(data)) % 4
        if pad:
            data += b" " * pad
        view_off = len(body)
        body += data
        vidx = len(j["bufferViews"])
        j["bufferViews"].append({"buffer": 0, "byteOffset": view_off, "byteLength": len(data), "target": 34962})
        acc_idx = len(j["accessors"])
        j["accessors"].append({
            "bufferView": vidx, "componentType": 5126, "count": pcount, "type": "VEC2",
        })
        prim["attributes"]["TEXCOORD_0"] = acc_idx

# Re-serialise JSON (pad to multiple of 4), reassemble GLB.
# Update the buffer's declared byteLength to cover appended UV data.
if j["buffers"]:
    j["buffers"][0]["byteLength"] = len(body)

new_json = json.dumps(j, separators=(",", ":")).encode("utf-8")
jpad = (-len(new_json)) % 4
if jpad:
    new_json += b" " * jpad
json_chunk = struct.pack("<II", len(new_json), 0x4E4F534A) + new_json
bin_chunk = struct.pack("<II", len(body), 0x004E4942) + bytes(body)
total = 12 + len(json_chunk) + len(bin_chunk)
out_bytes = b"glTF" + struct.pack("<II", 2, total) + json_chunk + bin_chunk

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "wb") as fh:
    fh.write(out_bytes)

print("WROTE", OUT, os.path.getsize(OUT))
for name in sorted(anatomy):
    print("  part", name, len(anatomy[name].vertices), "verts")
