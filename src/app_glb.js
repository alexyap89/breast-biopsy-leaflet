

/* ================================================================= SCENE == */

/* ============================================================================
   FNAC scene v6 — human form, staged reveal, anatomically-scaled technique.
   1 world unit = 5 cm.  +X = patient left, +Y = cranial, +Z = anterior.
   ========================================================================== */
/* ============================================================================
   FNAC scene - built from the Blender model (model/fnac_scene_v12.glb).

   The viscera come from Z-Anatomy via the department build (real thyroid,
   trachea with cartilage rings, larynx, parathyroids); the probe, needle and
   dressing are the same authored instruments; the skin is the authored
   `patient__bust` - head, neck and shoulders grafted in Blender - exported in
   the same GLB as everything else.

   This note used to say the procedural body mesh "cannot be used as a skin
   surface and is discarded", and that the skin was therefore an envelope built
   around the viscera. That stopped being true when the graft landed:
   app_scene.js now takes `patient__bust` as the skin (bustBody(BUST)) and the
   fitted envelope - buildBody() below - survives only as the fallback for a
   build that ships without a bust.

   1 world unit = 1 m. The patient's neck axis is +Y, anterior is +Z, and the
   whole scene is anchored so the nodule sits at the origin.
   ========================================================================== */
const GLB_B64='';

function glbBuffer(){
  const bin=atob(GLB_B64), n=bin.length, out=new Uint8Array(n);
  for(let i=0;i<n;i++) out[i]=bin.charCodeAt(i);
  return out.buffer;
}

function parseGLB(A){
  const dv=new DataView(A);
  const total=dv.getUint32(8,true);
  let off=12, json=null, binStart=0;
  while(off<total){
    const cl=dv.getUint32(off,true), ct=dv.getUint32(off+4,true);
    if(ct===0x4E4F534A) json=JSON.parse(new TextDecoder().decode(new Uint8Array(A,off+8,cl)));
    else binStart=off+8;
    off+=8+cl;
  }
  const CT={5120:Int8Array,5121:Uint8Array,5122:Int16Array,5123:Uint16Array,5125:Uint32Array,5126:Float32Array};
  const NC={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT2:4,MAT3:9,MAT4:16};
  function acc(i){
    const a=json.accessors[i], bv=json.bufferViews[a.bufferView];
    const TA=CT[a.componentType], n=NC[a.type], el=TA.BYTES_PER_ELEMENT;
    const base=binStart+(bv.byteOffset||0)+(a.byteOffset||0);
    const stride=bv.byteStride||n*el;
    const out=new TA(a.count*n);
    if(base%el===0 && stride===n*el){ out.set(new TA(A,base,a.count*n)); return out; }
    const sdv=new DataView(A);
    for(let k=0;k<a.count;k++) for(let c=0;c<n;c++){
      const p=base+k*stride+c*el;
      out[k*n+c]= a.componentType===5126?sdv.getFloat32(p,true)
               : a.componentType===5125?sdv.getUint32(p,true)
               : a.componentType===5123?sdv.getUint16(p,true)
               : a.componentType===5121?sdv.getUint8(p)
               : a.componentType===5122?sdv.getInt16(p,true):sdv.getInt8(p);
    }
    return out;
  }
  const root=new THREE.Group();
  for(const nd of json.nodes){
    const m=json.meshes[nd.mesh]; if(!m) continue;
    m.primitives.forEach((pr,pi)=>{
      const g=new THREE.BufferGeometry();
      for(const k in pr.attributes){
        const a=json.accessors[pr.attributes[k]];
        g.setAttribute(k==='POSITION'?'position':k==='NORMAL'?'normal':
          k==='TEXCOORD_0'?'uv':k.toLowerCase(),
          new THREE.BufferAttribute(acc(pr.attributes[k]),NC[a.type]));
      }
      if(pr.indices!==undefined) g.setIndex(new THREE.BufferAttribute(acc(pr.indices),1));
      if(!g.getAttribute('normal')) g.computeVertexNormals();
      const o=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0x888888}));
      o.name=m.primitives.length>1?(nd.name+'#'+pi):nd.name;
      o.userData.role=(nd.name||'').split('__')[0];
      if(nd.matrix) o.applyMatrix4(new THREE.Matrix4().fromArray(nd.matrix));
      else{ if(nd.translation)o.position.fromArray(nd.translation);
            if(nd.rotation)o.quaternion.fromArray(nd.rotation);
            if(nd.scale)o.scale.fromArray(nd.scale); }
      root.add(o);
    });
  }
  return root;
}

/* Role -> colour, as specified for this leaflet:
     thyroid  pink / muted coral     nodule   a darker contrasting red
     airway   light neutral grey     needle   white / metallic
     probe    dark grey              dressing pale
   The face roles (eye, iris, brow, lip, mouth) are back: the bust
   carries facial detail again, and each of those is separate geometry so it can
   hold its own colour. They are listed in the skin-fade group in app_scene.js. */
const ROLE_COL={
  body:0xf2ece3,        // skin, pale rather than tan: the surface is the picture
  duct:0xc04a55,        // lactiferous ducts, the red structures in the cutaway
  muscle:0x9d4a44,      // pectoralis, deeper and duller than the ducts
  gland:0xf0c98a,       // breast glandular tissue
  lesion:0xb8323c,      // the lump the page is about
  probe:0x3d4553,       // ultrasound probe, dark slate
  needle:0xf2f5f8,      // needle and marker clip, near-white metal
  clip:0xc9ced6,
  dressing:0xf5f0e6};   // pale dressing

