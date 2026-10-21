/* Breast-biopsy scene.
 *
 * The GLB is authored by `build_breast.py`; every node is named `role__part`, and the role
 * (the text before `__`) is what selects its group and material here. Geometry is in metres,
 * supine: the patient lies along Y with head at -Y, and the chest faces +Z.
 *
 * The module owns the rig, not the timeline. app_app.js drives it each frame by moving
 * `parts.probe`, `parts.needle`, `parts.clip`, `parts.dressing` and by setting the opacities
 * this file exposes.
 */
function buildThreeScene(THREE, root){
  const scene=new THREE.Scene();
  scene.add(new THREE.AmbientLight(0x93a4c0,1.15));
  /* A cut-away shows interior surfaces that receive little directional light, so a hemisphere
     fill keeps the section readable instead of a dark cavern. */
  scene.add(new THREE.HemisphereLight(0xffffff, 0x5a4a42, 0.55));
  const key=new THREE.DirectionalLight(0xfff4e8,1.05); key.position.set(0.6,0.4,1.2); scene.add(key);
  const fill=new THREE.DirectionalLight(0x9fc0ff,0.5); fill.position.set(-0.9,0.2,0.6); scene.add(fill);
  /* Under-fill: supine, the breast overhangs the chest wall, and key light alone leaves the
     crease under it as a black band that reads as a seam. */
  const under=new THREE.DirectionalLight(0xffd8bf,0.35); under.position.set(0.0,-0.6,-0.7); scene.add(under);

  root.updateMatrixWorld(true);

  const byRole={};
  root.traverse(o=>{ if(!o.isMesh) return;
    const r=(o.name||'').split('__')[0] || 'part';
    (byRole[r]=byRole[r]||[]).push(o);
  });

  const skinMats=[];
  const glandMats=[];
  const probeMats=[];
  const needleMats=[];
  const clipMats=[];
  const ductMats=[];
  const muscleMats=[];
  const TEXTURED=new Set(['body','gland','duct','muscle']);
  const matFor=(role)=>{
    const skin = role==='body';
    const metal = role==='needle' || role==='clip' || role==='scalpel' || role==='syringe';
    const m=new THREE.MeshPhysicalMaterial({
      color: ROLE_COL[role]!==undefined ? ROLE_COL[role] : 0xbfc6d0,
      roughness: metal ? 0.28 : (skin ? 0.62 : 0.55),
      metalness: metal ? 0.85 : 0.0,
      clearcoat: skin ? 0.18 : 0.0,
      clearcoatRoughness: 0.6,
      side: THREE.DoubleSide,
      /* The lump is translucent so the needle is visible crossing it: an opaque sphere hides
         exactly the thing the step is about. */
      transparent: skin || role==='lesion',
      opacity: 1.0,
      emissive: role==='lesion' ? 0xff7a4a : (role==='needle' ? 0xaaccff : 0x000000),
      emissiveIntensity: 0.0
    });
    if(skin) skinMats.push(m);
    if(role==='gland') glandMats.push(m);
    if(role==='probe') probeMats.push(m);
    if(role==='needle') needleMats.push(m);
    if(role==='clip') clipMats.push(m);
    return m;
  };

  const G={};
  for(const role in byRole){
    const g=new THREE.Group(); g.name=role;
    byRole[role].forEach(o=>{
      /* Anatomical meshes arrive textured from the FBX; keep those maps and only tune the
         surface. Props (probe, needle, clip, dressing) are authored here, so they get the
         flat materials. */
      const mapped = o.material && o.material.map && TEXTURED.has(role);
      if(mapped){
        o.material.roughness = role==='body' ? 0.72 : 0.6;
        o.material.metalness = 0.0;
        o.material.side = THREE.DoubleSide;
        if(role==='body'){ o.material.transparent = true; skinMats.push(o.material); }
        if(role==='gland') glandMats.push(o.material);
        if(role==='duct') ductMats.push(o.material);
        if(role==='muscle') muscleMats.push(o.material);
      } else {
        o.material = matFor(role);
      }
      g.add(o);
    });
    G[role]=g;
    scene.add(g);
  }

  /* The GLB arrives standing along Z: the glTF Y-up conversion undid the supine pose that
     build_breast.py applies in Blender. Lay it down here, once, before any anchor is measured,
     so the body runs along Y and the chest faces +Z - which is the basis the camera, the
     labels and every anchor assume. */
  for(const role in G){ G[role].rotation.x = -Math.PI/2; }
  scene.updateMatrixWorld(true);

  const centreOf=(grp)=>{
    const b=new THREE.Box3().setFromObject(grp);
    return b.getCenter(new THREE.Vector3());
  };

  const LUMP = G.lesion ? centreOf(G.lesion) : new THREE.Vector3(-0.098,0,0.114);
  const ENTRY = G.dressing ? centreOf(G.dressing) : new THREE.Vector3(-0.16,0,0.144);
  const AXIS = LUMP.clone().sub(ENTRY).normalize();      // points inward, toward the lump

  /* Needle rest position: the authored pose. Everything the timeline does is an offset from it. */
  const NEEDLE_HOME = G.needle ? G.needle.position.clone() : new THREE.Vector3();
  const PROBE_HOME  = G.probe  ? G.probe.position.clone()  : new THREE.Vector3();
  const CLIP_HOME   = G.clip   ? G.clip.position.clone()   : new THREE.Vector3();

  /* The lump is scaled about its own centre so it reads at phone size without moving the
     needle that is anchored to it. Same trick the thyroid page used for its nodule. */
  let lumpPivot=null;
  if(G.lesion){
    const c=LUMP.clone();
    lumpPivot=new THREE.Group(); lumpPivot.position.copy(c);
    [...G.lesion.children].forEach(o=>{ o.position.sub(c); lumpPivot.add(o); });
    G.lesion.add(lumpPivot);
    lumpPivot.scale.setScalar(1.25);
  }

  /* The dressing starts hidden; the timeline shows it at the end. The clip likewise only
     appears once it has been deployed, so the page never promises a marker before its step. */
  if(G.clip) G.clip.visible=false;
  if(G.syringe) G.syringe.visible=false;
  if(G.scalpel) G.scalpel.visible=false;
  if(G.dressing) G.dressing.visible=false;

  /* The needle's specimen trough ships mirrored across the body: its world centre is at
     x ≈ -0.075 while the needle shaft sits at x ≈ +0.075, so it draws as a small rectangle
     detached from the needle that slides with it. It is an export artefact, not a feature of
     any step, so hide it rather than let it float on the far side of the model. */
  if(G.needle) G.needle.children.forEach(o=>{ if(o.name && o.name.indexOf('needle__trough')===0) o.visible=false; });

  return {
    scene, root,
    body: G.body,
    parts: {
      skinMats,
      glandMats,
      probeMats,
      needleMats,
      clipMats,
      ductMats,
      muscleMats,
      body: G.body,
      lesion: G.lesion, lumpPivot,
      gland: G.gland,
      probe: G.probe, needle: G.needle,
      clip: G.clip, dressing: G.dressing,
      syringe: G.syringe, scalpel: G.scalpel,
      home: { needle: NEEDLE_HOME, probe: PROBE_HOME, clip: CLIP_HOME }
    },
    anchors: { LUMP_WORLD: LUMP, ENTRY, AXIS, NEEDLE_HOME }
  };
}
