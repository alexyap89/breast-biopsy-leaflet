#!/usr/bin/env python3
"""Print the node/mesh inventory of a GLB, one line per mesh, sorted by name.

    python3 tools/glb_nodes.py model/fnac_scene_web.glb
    python3 tools/glb_nodes.py --json a.glb b.glb     # diffable dumps
    python3 tools/glb_nodes.py --compare old.glb new.glb   # node-set diff

Used to prove that a rebuilt model keeps every node the leaflet depends on:
index.html groups meshes by the role prefix before "__" (patient__head,
thyroid__Thyroid gland, needle__shaft, ...), so a dropped or renamed node is a
silent visual regression.
"""
import json, os, struct, sys


def load(path):
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:4] != b"glTF":
        raise SystemExit(f"{path}: not a GLB")
    jlen = struct.unpack("<I", d[12:16])[0]
    j = json.loads(d[20:20 + jlen])
    acc = j["accessors"]
    rows = []
    for n in j.get("nodes", []):
        if "mesh" not in n:
            continue
        for pi, prim in enumerate(j["meshes"][n["mesh"]]["primitives"]):
            a = acc[prim["attributes"]["POSITION"]]
            rows.append({
                "name": n.get("name", "?"),
                "prim": pi,
                "verts": a["count"],
                "mat": j["materials"][prim["material"]]["name"] if "material" in prim else None,
                "bbox_min": [round(v, 4) for v in a.get("min", [])],
                "bbox_max": [round(v, 4) for v in a.get("max", [])],
            })
    return j, sorted(rows, key=lambda r: (r["name"], r["prim"]))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        raise SystemExit(__doc__)

    if "--compare" in flags:
        old, new = args[0], args[1]
        _, a = load(old)
        _, b = load(new)
        na, nb = {r["name"] for r in a}, {r["name"] for r in b}
        print(f"  {old}: {len(na)} nodes, {sum(r['verts'] for r in a)} verts")
        print(f"  {new}: {len(nb)} nodes, {sum(r['verts'] for r in b)} verts")
        for label, s in (("MISSING in new", na - nb), ("ADDED in new", nb - na)):
            if s:
                print(f"\n  {label} ({len(s)}):")
                for n in sorted(s):
                    print(f"    {n}")
            else:
                print(f"\n  {label}: none")
        vmap = {r["name"]: r["verts"] for r in b}
        drift = [(r["name"], r["verts"], vmap[r["name"]]) for r in a
                 if r["name"] in vmap and r["verts"] != vmap[r["name"]]]
        print(f"\n  vertex-count changes: {len(drift)}")
        for n, x, y in drift[:20]:
            print(f"    {n}: {x} -> {y}")
        # only a dropped/renamed node is a hard failure: index.html groups by
        # name, so vertex drift on a surviving node is reported, not fatal
        return 0 if not (na - nb) else 1

    for path in args:
        j, rows = load(path)
        if "--json" in flags:
            print(json.dumps(rows, indent=1))
            continue
        print(f"\n{path}: {len(rows)} meshes, "
              f"{len(j.get('materials', []))} materials, "
              f"{sum(r['verts'] for r in rows)} verts")
        for r in rows:
            print(f"  {r['name']:46s} p{r['prim']} {r['verts']:>6d}v "
                  f"{str(r['mat']):16s} {r['bbox_min']}..{r['bbox_max']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        os._exit(0)
