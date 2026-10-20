(function(){
  const canvas = document.getElementById('gl');
  const label  = document.getElementById('stepLabel');
  const note   = document.getElementById('stepNote');
  const chips  = document.getElementById('steps');
  const btnPlay= document.getElementById('btnPlay');
  const srText = document.getElementById('srText');
  const labelLayer = document.getElementById('sceneLabels');
  const root   = document.documentElement;

  /* Set true to disable all animation (accessibility / reduced motion). */
  const RM = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const STEPS = [
    {t:"Your breast and the lump",
     n:"The lump your doctor wants to check is inside your breast. Most breast lumps are not cancer, but a sample is the only way to know for certain.",
     a:{form:1, xray:0, lumpHi:0, probe:0, needle:0, passes:0, clip:0, dressing:0, labels:1}},

    {t:"Finding the lump with ultrasound",
     n:"You lie on your back with your arm above your head. The doctor moves an ultrasound probe over the skin, and the screen shows the lump, where it sits and how deep it is.",
     a:{form:1, xray:0.55, lumpHi:1, probe:1, needle:0, passes:0, clip:0, dressing:0, labels:1}},

    {t:"Cleaning the skin",
     n:"The skin over the lump is cleaned and the area is covered with a sterile drape. That is all this step involves, and it takes a moment.",
     a:{form:1, xray:0.55, lumpHi:1, probe:1, needle:0, passes:0, clip:0, dressing:0, labels:1}},

    {t:"Numbing the area",
     n:"Local anaesthetic is injected into the skin and deeper into the breast. It stings for a few seconds, and then the area goes numb. You stay awake the whole time.",
     a:{form:1, xray:0.45, lumpHi:0.6, probe:1, needle:0, passes:0, clip:0, dressing:0, labels:1}},

    {t:"The needle goes in",
     n:"A small nick is made in the skin. Watching the screen, the doctor guides the needle in under the probe and into the lump.",
     a:{form:1, xray:0.4, lumpHi:0.8, probe:1, needle:1, passes:0, clip:0, dressing:0, labels:1}},

    {t:"Taking the samples",
     n:"The device fires and takes a thin core of tissue with a click. This is repeated a few times, each one a quick click, until enough tissue has been collected.",
     a:{form:1, xray:0.35, lumpHi:1, probe:1, needle:1, passes:1, clip:0, dressing:0, labels:1}},

    {t:"The marker clip",
     n:"A very small clip is left at the spot, so the area can be found again later. You cannot feel it, and it is safe to have an MRI scan with it in place.",
     a:{form:1, xray:0.35, lumpHi:1, probe:0.85, needle:0.5, passes:0, clip:1, dressing:0, labels:1}},

    {t:"Pressure, then a dressing",
     n:"Firm pressure is held over the spot to stop any bleeding, then a dressing is applied. It stays on, and stays dry, for 48 hours.",
     a:{form:1, xray:0.2, lumpHi:0, probe:0, needle:0, passes:0, clip:1, dressing:1, labels:0}},

    {t:"Afterwards, and your results",
     n:"The numbness wears off within a few hours. Soreness and bruising settle over a few days to two weeks. Use paracetamol if you need it, not ibuprofen or aspirin. Results usually take about two weeks.",
     a:{form:1, xray:0, lumpHi:0, probe:0, needle:0, passes:0, clip:0, dressing:1, labels:0}},
  ];

  let cur=0, playing=false, timer=null, guided=false, curClip=null;
  const clipCache={};

  STEPS.forEach((s,i)=>{
    const b=document.createElement('button');
    b.className='stepchip'; b.setAttribute('role','tab');
    b.textContent=(i+1)+'. '+s.t;
    b.onclick=()=>{ stopPlay(); setStep(i); };
    chips.appendChild(b);
  });

  const A={form:0,xray:0,lumpHi:0,probe:0,needle:0,passes:0,clip:0,dressing:0,labels:0};
  const TGT=Object.assign({},A);

  function setStep(i){
    cur=i; const s=STEPS[i];
    label.innerHTML='<b>Step '+(i+1)+' of '+STEPS.length+'.</b> '+s.t;
    note.textContent=s.n;
    srText.textContent='Step '+(i+1)+' of '+STEPS.length+'. '+s.t+'. '+s.n;
    stepCount.textContent=(i+1)+' / '+STEPS.length;
    refreshNav();
    [...chips.children].forEach((c,j)=>c.setAttribute('aria-current',String(j===i)));
    for(const k of Object.keys(TGT)) TGT[k]=(s.a[k]!==undefined)?s.a[k]:0;
    if(RM){ for(const k of Object.keys(TGT)) A[k]=TGT[k]; }
    if(audioOn) playStepAudio(i);
  }
  function stopPlay(){ playing=false; guided=false; clearTimeout(timer); stopClip(); btnPlay.textContent='▶ Play all'; }

  /* -------------------------------------------------- step navigation ----- */
  const btnPrev=document.getElementById('btnPrev');
  const btnNext=document.getElementById('btnNext');
  const btnSound=document.getElementById('btnSound');
  const stepCount=document.getElementById('stepCount');

  function refreshNav(){
    const atFirst=cur<=0, atLast=cur>=STEPS.length-1;
    if(btnPrev){ btnPrev.disabled=atFirst; btnPrev.setAttribute('aria-disabled',String(atFirst)); }
    if(btnNext){ btnNext.disabled=atLast; btnNext.setAttribute('aria-disabled',String(atLast)); }
  }
  function prevStep(){ stopPlay(); if(cur>0) setStep(cur-1); }
  function nextStep(){ stopPlay(); if(cur<STEPS.length-1) setStep(cur+1); }
  if(btnPrev) btnPrev.onclick=prevStep;
  if(btnNext) btnNext.onclick=nextStep;

  /* ---- language ----------------------------------------------------------
   * Translations in src/i18n/{ms,ta,zh}.json are model-generated and were checked for
   * terminology only, not clinically. A native clinical reviewer must review them before
   * this page is used for patient education. src/i18n/en.json is the source of truth.
     Every translatable element carries data-i18n; the English stays in the markup and is captured
     once at load, so switching back to English needs no second copy in the payload. The chapter
     titles and notes live in STEPS, so those are swapped in place and the current step re-rendered.
     Audio is not swapped here: the clips ship per locale and are loaded by playStepAudio. */
  const langPick=document.getElementById('langPick');
  let lang='en';
  const EN_TXT={};
  /* 3D callout balloons. Filled after this point, so the first applyLang sees an empty list —
     their English text stays in the markup until a language is actually chosen. */
  const sceneLabelEls=[];
  document.querySelectorAll('[data-i18n]').forEach(el=>{ EN_TXT[el.dataset.i18n]=el.textContent; });
  const EN_STEPS=STEPS.map(s=>({t:s.t,n:s.n}));
  /* Replace the TEXT of a hooked element without destroying what it must keep. Three shapes
     occur in this page and each needs a different rule:
       legend  <i swatch></i>Label      -> keep the empty leading child, replace the label
       heading <span class=num>1</span> Title -> keep the numeric badge, replace the title
       prose   Text <strong>phrase</strong> more text -> the child is inline emphasis inside the
               sentence, so the whole sentence is replaced (keeping it would interleave two languages)
       k31     <strong>whole sentence</strong> -> replace the child's own text */
  function setText(el,text){
    const kids=[...el.children];
    if(!kids.length){ el.textContent=text; return; }
    const leadingText=el.firstChild && el.firstChild.nodeType===3 && el.firstChild.nodeValue.trim();
    if(leadingText){ el.textContent=text; return; }
    if(kids.length===1 && ![...el.childNodes].some(n=>n.nodeType===3 && n.nodeValue.trim())){
      kids[0].textContent=text; return;
    }
    const keep=[];
    for(const n of el.childNodes){
      if(n.nodeType===3){ if(n.nodeValue.trim()) break; continue; }
      if(n.nodeType!==1) continue;
      const t=n.textContent.trim();
      if(t==='' || /^\d+$/.test(t)) keep.push(n); else break;
    }
    el.textContent='';
    keep.forEach(k=>el.appendChild(k));
    el.appendChild(document.createTextNode(text));
  }
  function stepLabel(cat,n,m){
    const t=(cat&&cat.html&&cat.html.k80)||EN_TXT.k80||'Step {n} of {m}.';
    return t.replace('{n}',n).replace('{m}',m);
  }
  function applyLang(code){
    lang=code;
    const cat=(code!=='en' && typeof I18N!=='undefined' && I18N[code]) ? I18N[code] : null;
    document.querySelectorAll('[data-i18n]').forEach(el=>{
      const v=cat&&cat.html ? cat.html[el.dataset.i18n] : null;
      setText(el, v||EN_TXT[el.dataset.i18n]||el.textContent);
    });
    STEPS.forEach((s,i)=>{
      const tr=cat&&cat.steps ? cat.steps['step'+String(i+1).padStart(2,'0')] : null;
      s.t=(tr&&tr.t)||EN_STEPS[i].t;
      s.n=(tr&&tr.n)||EN_STEPS[i].n;
    });
    [...chips.children].forEach((b,i)=>{ b.textContent=(i+1)+'. '+STEPS[i].t; });
    sceneLabelEls.forEach(o=>{ o.el.textContent=(cat&&cat.html&&cat.html[o.key])||o.en; });
    document.documentElement.lang=code;
    label.textContent='';
    const lb=document.createElement('b');
    lb.textContent=stepLabel(cat,cur+1,STEPS.length);
    label.appendChild(lb);
    label.appendChild(document.createTextNode(' '+STEPS[cur].t));
    note.textContent=STEPS[cur].n;
    srText.textContent=stepLabel(cat,cur+1,STEPS.length)+' '+STEPS[cur].t+'. '+STEPS[cur].n;
    refreshNav();
    if(langPick) langPick.value=code;
    try{ localStorage.setItem('fnac.lang',code); }catch(_){}
  }
  if(langPick) langPick.addEventListener('change',()=>{ applyLang(langPick.value); if(audioOn) playStepAudio(cur); else stopClip(); });
  /* English is the default every visit. The language is still remembered for the switcher, but
     a returning patient should land on the language of the printed sheet, not the last pick. */

  /* Arrow / Home / End move between steps, but never while focus is on the
     canvas — there the arrows orbit the model. */
  document.addEventListener('keydown',e=>{
    const inCanvas=document.activeElement===canvas;
    let handled=false;
    if(!inCanvas){
      if(e.key==='ArrowLeft'){ prevStep(); handled=true; }
      else if(e.key==='ArrowRight'){ nextStep(); handled=true; }
      else if(e.key==='Home'){ stopPlay(); setStep(0); handled=true; }
      else if(e.key==='End'){ stopPlay(); setStep(STEPS.length-1); handled=true; }
    }
    if(handled) e.preventDefault();
  });

  /* -------------------------------------------------------------- audio ---
     Narration is inlined by the build as `AUDIO` (see head_top.html): a map of
     {mime, bytes, 1:{b64}, ..., 9:{b64}} keyed 1-by-step. It is omitted entirely
     from builds without audio files, so every reference is guarded. */
  let audioOn=false;

  function stopClip(){ if(curClip){ try{curClip.pause();}catch(_){} curClip=null; } }

  /* One clip per step per language. English is inlined (AUDIO); every other locale ships as
     audio/<code>/leaflet/stepNN.mp3 beside the page (AUDIO_LOCALES), because six locales
     inlined would add ~10 MB of base64. A missing or failing locale clip marks that language
     broken and falls back to the English clip rather than going silent. */
  const localeBroken={};

  function clipEnd(){ if(guided){ if(cur>=STEPS.length-1){ stopPlay(); } else { setStep(cur+1); } } }

  function localeSrc(code,i){
    if(!code || code==='en' || localeBroken[code]) return null;
    if(typeof AUDIO_LOCALES==='undefined') return null;
    const set=AUDIO_LOCALES[code];
    return (set && set[String(i+1)]) || null;
  }

  function getClip(i){
    const code=document.documentElement.lang||'en';
    const key=code+':'+i;
    if(clipCache[key]) return clipCache[key];
    const src=localeSrc(code,i);
    if(src){
      const a=new Audio(); a.src=src;
      a.addEventListener('ended',clipEnd);
      a.addEventListener('error',()=>{
        localeBroken[code]=true; delete clipCache[key];
        if(curClip===a) playStepAudio(i);
      });
      clipCache[key]=a;
      return a;
    }
    let a=null;
    try{
      const entry=(typeof AUDIO!=='undefined')?AUDIO[String(i+1)]:undefined;
      if(entry){
        const mime=(typeof AUDIO!=='undefined'&&AUDIO.mime)?AUDIO.mime:'audio/mpeg';
        const bin=atob(entry.b64); const n=bin.length;
        const arr=new Uint8Array(n);
        for(let j=0;j<n;j++) arr[j]=bin.charCodeAt(j);
        a=new Audio(); a.src=URL.createObjectURL(new Blob([arr],{type:mime}));
        a.addEventListener('ended',clipEnd);
        clipCache[key]=a;
      }
    }catch(_){ /* missing or failing clips degrade silently */ }
    return a;
  }

  function stepHasAudio(i){
    if(localeSrc(document.documentElement.lang||'en',i)) return true;
    return typeof AUDIO!=='undefined' && !!AUDIO[String(i+1)];
  }

  function playStepAudio(i){
    stopClip();
    const a=getClip(i);
    if(!a) return false;
    /* Rewind first. Clips are cached per step and stopClip only PAUSES, so without this a step
       replayed after being visited once resumes where it left off and plays only its tail. */
    try{ a.currentTime=0; }catch(_){}
    const p=a.play();
    if(p&&p.catch){ p.catch(()=>{}); }
    curClip=a;
    return true;
  }

  if(btnSound){
    btnSound.onclick=()=>{
      audioOn=!audioOn;
      btnSound.setAttribute('aria-pressed',String(audioOn));
      btnSound.textContent=audioOn?'🔊 Sound on':'🔇 Sound off';
      if(audioOn) playStepAudio(cur); else { stopClip(); scheduleDwell(); }
    };
  }

  /* Play all: a guided run. With audio on, each step plays its clip and the
     run advances when the clip ends; with no audio it falls back to the old
     5.2s timer. Either way it stops at the last step and toggles pause. */
  btnPlay.onclick=()=>{
    if(playing){ stopPlay(); return; }
    guided=true; playing=true; btnPlay.textContent='⏸ Pause';
    if(audioOn) playStepAudio(cur);
    else {
      audioOn=true;
      btnSound.setAttribute('aria-pressed','true');
      btnSound.textContent='🔊 Sound on';
      /* ONE call. This used to call playStepAudio twice, and because playStepAudio stops the
         current clip before starting the next one, the second call restarted the clip it had just
         begun - an audible stutter on the first step of every Play all. */
      if(!playStepAudio(cur)) { stopClip(); scheduleDwell(); }
    }
  };

  /* ------------------------------------------------------------ Timer (dwell) -- */
  function timerForStep(i){
    const note = STEPS[i].n;
    return Math.max(3.0, Math.min(14.0, 2.0 + 0.055 * note.length));
  }

  function scheduleDwell(){
    /* The no-audio path, and the fallback when a clip is missing. It used to call itself
       recursively with no timer at all, so it advanced through every remaining step in one tick -
       the run arrived at the last step instantly. `timer` existed and was cleared by stopPlay but
       was never set; it is set now, and the recursion happens when the timer fires. */
    if(cur>=STEPS.length-1){ stopPlay(); return; }
    if(audioOn && stepHasAudio(cur)) return;
    stopClip();
    timer=setTimeout(()=>{ if(playing){ setStep(cur+1); scheduleDwell(); } }, timerForStep(cur)*1000);
  }

  /* ------------------------------------------------------------ UI prefs -- */
  const SIZES=['normal','large','xl']; let sizeIdx=0;
  document.getElementById('btnSize').onclick=(e)=>{
    sizeIdx=(sizeIdx+1)%SIZES.length; const v=SIZES[sizeIdx];
    if(v==='normal') root.removeAttribute('data-size'); else root.setAttribute('data-size',v);
    e.currentTarget.setAttribute('aria-pressed',String(v!=='normal'));
    e.currentTarget.textContent=v==='normal'?'Larger text'
      :(v==='large'?'Largest text':'Reset text size');
  };
  document.getElementById('btnContrast').onclick=(e)=>{
    const on=root.getAttribute('data-contrast')==='high';
    if(on) root.removeAttribute('data-contrast'); else root.setAttribute('data-contrast','high');
    e.currentTarget.setAttribute('aria-pressed',String(!on));
  };
  /* A rotate toggle used to be wired here, to `#btnRotate` - an element that is not in the markup,
     so it was never attached. Left in, it is the same trap that broke this page before: a handler
     for an element that does not exist. The model no longer turns on its own, which is what was
     asked for, so there is nothing to toggle. */
  document.getElementById('btnPrint').onclick=()=>window.print();

  /* ------------------------------------------------------------ three.js -- */
  const T = buildThreeScene(THREE, parseGLB(glbBuffer()));
  const scene=T.scene, body=T.body, P=T.parts;
  const {LUMP_WORLD, ENTRY, AXIS, NEEDLE_HOME} = T.anchors;

  const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true,
                                            preserveDrawingBuffer:true});
  renderer.setClearColor(0x000000,0);
  const camera = new THREE.PerspectiveCamera(38, 1.6, 0.1, 200);

  /* ---------------------------------------------------------- framing -----
     The scene is one unit = 5 cm, so the whole patient (head to shoulders) is
     about 8.6 units tall while the anatomy the needle touches is about 3.2.
     A single fixed camera distance therefore either crops the body or makes
     the gland too small, so each frame is fitted to whatever that step shows:
     the body while the skin is opaque, the interior once it is see-through. */
  const look=new THREE.Vector3(), _lookT=new THREE.Vector3();
  let lookInit=false;
  const vFov = camera.fov*Math.PI/180;
  /* Exact perspective fit of a box for the current orbit: for every corner the
     camera must be far enough that the corner stays inside both frustum planes.
     Solving for the distance directly means rotating or zooming never crops. */
  const _p=new THREE.Vector3(), _u=new THREE.Vector3(), _r=new THREE.Vector3(),
        _up=new THREE.Vector3();
  function fitDist(box){
    _u.set(Math.sin(yaw)*Math.cos(pitch), Math.sin(pitch), Math.cos(yaw)*Math.cos(pitch));
    _r.set(Math.cos(yaw),0,-Math.sin(yaw));
    _up.crossVectors(_u,_r).normalize();
    const tV=Math.tan(vFov/2), tH=tV*Math.max(0.4, camera.aspect||1.6);
    let d=0.0005;
    for(let i=0;i<8;i++){
      _p.set(i&1?box.max.x:box.min.x, i&2?box.max.y:box.min.y, i&4?box.max.z:box.min.z);
      _p.sub(look);
      const qu=_p.dot(_u), qr=Math.abs(_p.dot(_r)), qp=Math.abs(_p.dot(_up));
      d=Math.max(d, qu+qr*1.10/tH, qu+qp*1.10/tV);
    }
    return d;
  }

  /* Declared BEFORE the render loop: the loop references these on frame 1,
     and a `const` declared later would throw a temporal-dead-zone error that
     silently kills the whole IIFE. */
  const SKIN_Y = ENTRY.y, SKIN_Z = ENTRY.z;

  /* --------------------------------------------------------- DOM labels --- */
  const LABELS = [
    {text:'Breast',      k:'k93', pos:LUMP_WORLD.clone().add(new THREE.Vector3(0.035,0.05,0.015)),
                          shows:a=>a.form>.5&&a.xray<.4},
    {text:'The lump',    k:'k94', pos:LUMP_WORLD.clone(),
                          shows:a=>a.lumpHi>.5},
    {text:'Ultrasound probe', k:'k95', pos:ENTRY.clone().add(new THREE.Vector3(0.035,0.02,0.055)),
                          shows:a=>a.probe>.5},
    {text:'Needle',      k:'k96', pos:ENTRY.clone().add(new THREE.Vector3(-0.03,0,0.02)),
                          shows:a=>a.needle>.45},
    {text:'Marker clip', k:'k97', pos:LUMP_WORLD.clone().add(new THREE.Vector3(0,-0.025,-0.005)),
                          shows:a=>a.clip>.5},
    {text:'Dressing',    k:'k98', pos:ENTRY.clone().add(new THREE.Vector3(0,0,0.012)),
                          shows:a=>a.dressing>.5},
  ];
  const labelEls = LABELS.map(L=>{
    const d=document.createElement('div');
    d.className='scene-label'; d.textContent=L.text;
    labelLayer.appendChild(d);
    sceneLabelEls.push({key:L.k, el:d, en:L.text});
    return d;
  });

  /* ------------------------------------------------------------ controls -- */
  /* No spin by default - the user asked for the model to stop turning on its own; the rotate
     toggle still starts it if they want it. `manual` records that the viewer has moved the camera
     themselves, which is what stops the per-step framing below from pulling it back to a default. */
  let yaw=0.34, pitch=0.14, autoRotate=false, manual=false;
  const _bis=new THREE.Vector3();      /* reused each frame: no allocation in the render loop */
  let zoomMul=1.0, dist=0.9;
  let drag=false,lx=0,ly=0,pid=null,swX=0,swY=0;

  /* Every pointer currently down on the canvas. One finger rotates; two pinch to zoom.
     `touch-action:none` on #gl is what lets the browser hand the gesture over at all - without it a
     drag scrolls the page and the browser cancels the pointer, so the model never turns on a phone. */
  const touches=new Map();
  let pinchDist=0, pinchZoom=1;
  const ZOOM_MIN=0.55, ZOOM_MAX=2.2;
  const clampZoom=z=>Math.max(ZOOM_MIN,Math.min(ZOOM_MAX,z));
  function touchSpread(){
    const p=[...touches.values()];
    if(p.length<2) return 0;
    return Math.hypot(p[0].x-p[1].x, p[0].y-p[1].y);
  }

  canvas.addEventListener('pointerdown',e=>{
    touches.set(e.pointerId,{x:e.clientX,y:e.clientY});
    autoRotate=false; manual=true;
    if(touches.size===2){
      /* second finger down: this is a pinch - not a rotate, and not a swipe. Clearing swX here is
         what stops the lift at the end of a pinch being read as "next step". */
      drag=false; swX=swY=null;
      pinchDist=touchSpread(); pinchZoom=zoomMul;
      return;
    }
    if(touches.size>2) return;
    drag=true; pid=e.pointerId;
    lx=e.clientX; ly=e.clientY; swX=e.clientX; swY=e.clientY;
    if(canvas.setPointerCapture){ try{ canvas.setPointerCapture(e.pointerId); }catch(_){} } });

  function endPointer(e){
    touches.delete(e.pointerId);
    if(touches.size<2) pinchDist=0;
    if(e.pointerId!==pid) return;
    const dir=(swX!==null)&&Math.abs(e.clientX-swX)>=40&&Math.abs(e.clientY-swY)<60?(e.clientX>swX?1:-1):0;
    drag=false;
    if(canvas.releasePointerCapture&&pid!==null){try{canvas.releasePointerCapture(pid);}catch(_){}}
    pid=null; swX=swY=null;
    if(dir===1) nextStep(); else if(dir===-1) prevStep();
  }
  canvas.addEventListener('pointerup',endPointer);
  canvas.addEventListener('pointercancel',endPointer);

  canvas.addEventListener('pointermove',e=>{
    if(!touches.has(e.pointerId)) return;
    touches.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(touches.size>=2){
      /* fingers apart = closer = SMALLER zoomMul, the same convention as the wheel below */
      const d=touchSpread();
      if(pinchDist>0 && d>0) zoomMul=clampZoom(pinchZoom*(pinchDist/d));
      return;
    }
    if(!drag) return;
    yaw+=(e.clientX-lx)*0.007;
    pitch=Math.max(-0.9,Math.min(1.2,pitch+(e.clientY-ly)*0.005));
    lx=e.clientX; ly=e.clientY; });
  canvas.addEventListener('wheel',e=>{ e.preventDefault();
    zoomMul=clampZoom(zoomMul+e.deltaY*0.0016); autoRotate=false; manual=true; },{passive:false});
  canvas.addEventListener('keydown',e=>{ const k=e.key; manual=true;
    if(k==='ArrowLeft'){yaw-=0.12;autoRotate=false;e.preventDefault();}
    else if(k==='ArrowRight'){yaw+=0.12;autoRotate=false;e.preventDefault();}
    else if(k==='ArrowUp'){pitch=Math.max(-0.7,pitch-0.07);autoRotate=false;e.preventDefault();}
    else if(k==='ArrowDown'){pitch=Math.min(1.0,pitch+0.07);autoRotate=false;e.preventDefault();}
    else if(k==='+'||k==='='){zoomMul=Math.max(0.55,zoomMul-0.12);e.preventDefault();}
    else if(k==='-'||k==='_'){zoomMul=Math.min(2.2,zoomMul+0.12);e.preventDefault();} });

  function resize(){
    const dpr=Math.min(window.devicePixelRatio||1,2);
    const r=canvas.getBoundingClientRect();
    const w=Math.max(2,Math.round(r.width)), h=Math.max(2,Math.round(r.height));
    renderer.setPixelRatio(dpr); renderer.setSize(w,h,false);
    camera.aspect=w/h; camera.updateProjectionMatrix();
  }
  window.addEventListener('resize',resize); resize();

  /* -------------------------------------------------------- render loop --- */
  let t0=performance.now(), lastRaf=performance.now(), wdOn=false;
  const v3=new THREE.Vector3();
  const ENTRY_LIFT = ENTRY.clone();
  const ENTRY_SKIN = ENTRY.clone();

  /* ---- "Collecting the cells": complete passes, not a vibration ----------
     A pass is not a wobble, and it is not a step of its own. The clinician's words:
       "1 pass is: take needle, push in and out a few times, then pull out of skin.
        Pass 2 is a new needle insertion, push in and out, and pull out."
     So step 7 runs TWO passes, each one: a few strokes inside the lump, then all the way
     out of the skin, then a beat of stillness - after which the next pass brings the needle
     back in from outside. That is why the withdrawal belongs HERE and not to step 8: step 8
     is what happens after the last pass, not the way every pass ends.
     Distances are metres (1 unit = 1 m, despite the stale 5 cm note further up): the needle's
     travel from the nodule out to the skin is about 0.077, so OUT is 0.078 - just clear of it.
     The phase is anchored to the step's own start rather than to the page clock, so step 7
     always opens on the strokes with the needle in, never on a stray frame with it outside. */
  const PASS_OUT=0.078, PASS_STROKE=0.034, PASSES=2, PASS_MS=6000, PASS_STROKES=3;
  let lastCur=-1, stepT0=0;
  function passSlide(now){
    const amp=Math.min(1,Math.max(0,A.passes))*Math.min(1,Math.max(0,A.needle));
    if(amp<0.02) return 0;
    const cyc=(now-stepT0)/PASS_MS;
    /* the first pass opens on the strokes: step 6 has just shown the needle going in, so
       re-inserting it here would read as a duplicate. Later passes do come in from outside. */
    const ph=((cyc<1 ? 0.10+cyc : cyc) % 1);
    let t;                                        /* outward fraction: 0 in, 1 fully out */
    if(ph<0.10)       t=1-ph/0.10;                /* coming in, from outside the skin */
    else if(ph<0.70){                             /* a few strokes inside the lump */
      const s=(ph-0.10)/0.60;
      t=PASS_STROKE*(0.5-0.5*Math.cos(s*Math.PI*2*PASS_STROKES));
    }
    else if(ph<0.86)  t=PASS_STROKE+(1-PASS_STROKE)*((ph-0.70)/0.16);   /* all the way out */
    else              t=1;                        /* still, needle out, before the next pass */
    return -PASS_OUT*amp*(t*t*(3-2*t));           /* smoothstep; negative = withdrawn */
  }

  /* ---- need to know which meshes are "skin" so we can fade them ---------- */

  function step(now){
    const dt=Math.min(0.05,(now-t0)/1000); t0=now;
    const k = RM ? 1 : Math.min(1, dt*2.6);
    for(const key of Object.keys(TGT)) A[key]+=(TGT[key]-A[key])*k;
    /* Anchor the pass sequence to the step's own start, so step 7 always opens with the
       needle in and the strokes under way - see passSlide. */
    if(lastCur!==cur){ lastCur=cur; stepT0=now; }
    /* Which step is "the procedure"? Steps 5-8: the ones with the probe or the needle in play.
       Used twice below - for the viewing angle, and to pull the camera in. */
    /* Only the needle steps earn the close-up. The probe alone is on screen from step 2,
       and factoring it in pulled the camera inside the torso, where nothing draws. */
    const proc=Math.max(TGT.needle, TGT.passes);
    /* The body does not turn on its own any more - the user asked for that to stop - but the rotate
       toggle can still start it, and it is held during the procedure: you cannot follow a needle
       while the neck turns away from you. `manual` is set by any drag, wheel or key press, so a view
       the viewer has taken hold of is never pulled back to a default. */
    if(autoRotate && !RM && !manual && proc<0.05) yaw+=dt*0.10;
    /* The procedure steps are framed FOR the procedure: the camera eases to the bisector of the
       ultrasound's plane and the needle, so it looks from between them - the one direction where
       the probe's face on the skin and the needle going in under it are both visible. The
       ultrasound's plane is the skin surface, whose outward direction is +Z here, and the needle's
       axis points inward, so the bisector is +Z minus AXIS. wantYaw/wantPitch are that direction
       in the same spherical convention the camera placement below already uses. */
    if(!manual && proc>0.05){
      _bis.set(0,0,1).addScaledVector(AXIS,-1).normalize();
      const wYaw=Math.atan2(_bis.x,_bis.z);
      const wPitch=Math.asin(Math.max(-1,Math.min(1,_bis.y)));
      const k=Math.min(1,dt*1.6);
      yaw  +=(wYaw  -yaw  )*k;
      pitch+=(wPitch-pitch)*k;
    }

    /* ---------- skin: fades as the x-ray view rises ---------------------- */
    /* A semi-transparent NECK, not a ghost patient. The user's requirement is to
       read the anatomy through the skin without making the whole body see-through.
       The ramp now starts at 1.0 and falls to a floor of about 0.53 at full x-ray:
       it used to start at 0.95, which meant no step was ever fully opaque, so the
       patient's first impression was a faintly ghosted body with solid black hair
       floating over it. `solid` is where the skin stops writing as glass and
       starts occluding the anatomy behind it again. */
    const op = 1 - 0.47*A.xray;
    const solid = op > 0.90;
    P.skinMats.forEach(m=>{ m.opacity=op; m.transparent=!solid;
      m.depthWrite=solid; m.needsUpdate=true; });

    /* ---------- interior ------------------------------------------------- */
    if(P.gland) P.gland.visible = A.xray > 0.02;

    /* ---------- nodule emphasis ------------------------------------------ */
    /* The highlight is the material's own emissive, NOT a depth override. This
       used to set depthTest=false and renderOrder=6 while the nodule was
       highlighted, which meant the lump punched through whatever stood in front of
       it - the probe, the skin, the head - so it looked different depending on
       what you were looking at it through. Depth testing stays on: at every step
       where the nodule is meant to be seen the skin is translucent enough to show
       it, and the emissive is what makes it read through that skin. */
    if(P.lesion) P.lesion.traverse(o=>{ if(!o.isMesh) return; const m=o.material;
      m.emissiveIntensity=0.25+1.35*A.lumpHi; m.needsUpdate=true; });
    if(P.lumpPivot) P.lumpPivot.scale.setScalar(1+0.5*A.lumpHi);

    /* ---------- probe and needle ----------------------------------------- */
    P.probe.visible = A.probe>0.03;
    P.probe.position.y = (A.probe>0.05 && !RM ? 0.0015*Math.sin(now/260) : 0);
    const active = A.needle>0.02 || A.passes>0.02;
    P.needle.visible = active;
    const slide = -(1-Math.min(1,A.needle))*0.075 + passSlide(now);
    P.needle.position.copy(NEEDLE_HOME).addScaledVector(AXIS, slide);

    /* ---------- dressing -------------------------------------------------- */
    P.dressing.visible = A.dressing>0.03;
    if(P.clip){ P.clip.visible = A.clip>0.03; P.clip.scale.setScalar(0.65+0.35*Math.min(1,A.clip)); }

    /* ---------- camera ---------------------------------------------------- */
    /* The frame is fitted to whatever that step shows: the body while the skin
       is opaque, the interior once it fades, plus any instrument on screen.
       At zoom 1 that fit is exact, so rotating or zooming out never crops the content.
       The PROCEDURE steps are the exception, deliberately: at body scale the needle, the
       probe tip and the lump are a handful of pixels, so the steps that are ABOUT the needle
       showed almost nothing of it. Steps 5-8 therefore default to a closer view. `zoomMul`
       is still the user's own zoom and still wins - this only changes the default. */
    const box=new THREE.Box3().setFromObject(P.body);
    if(A.xray>0.02){ [P.lesion,P.gland].forEach(g=>{ if(g) box.union(new THREE.Box3().setFromObject(g)); }); }
    if(A.probe>0.05) box.union(new THREE.Box3().setFromObject(P.probe));
    if(P.dressing.visible) box.union(new THREE.Box3().setFromObject(P.dressing));
    const dTarget=Math.max(0.62, fitDist(box)*(1-0.28*A.lumpHi)*zoomMul*(1-0.34*proc));
    dist+=(dTarget-dist)*Math.min(1,dt*3.0);
    box.getCenter(_lookT);
    /* Once the lump is the subject, aim at it rather than at the middle of the torso: the
       breast sits off-centre, so a body-centred look leaves the action in a corner. */
    if(A.lumpHi>0.05) _lookT.lerp(LUMP_WORLD, Math.min(1, A.lumpHi));
    if(!lookInit){ look.copy(_lookT); lookInit=true; }
    look.lerp(_lookT, Math.min(1,dt*3.0));
    camera.position.set(look.x+Math.sin(yaw)*Math.cos(pitch)*dist,
                        look.y+Math.sin(pitch)*dist,
                        look.z+Math.cos(yaw)*Math.cos(pitch)*dist);
    camera.lookAt(look);

    renderer.render(scene,camera);

    /* ---------- project labels -------------------------------------------- */
    const w=canvas.clientWidth, h=canvas.clientHeight;
    LABELS.forEach((L,i)=>{
      const el=labelEls[i];
      const vis = A.labels>0.55 && L.shows(A);
      el.style.display = vis?'block':'none';
      if(!vis) return;
      v3.copy(L.pos).project(camera);
      const x=(v3.x*0.5+0.5)*w, y=(-v3.y*0.5+0.5)*h;
      el.style.transform='translate(-50%,-50%) translate('+x.toFixed(1)+'px,'+y.toFixed(1)+'px)';
    });
  }

  /* fade helper: sets opacity on interior material groups without destroying
     their individual colours */

  function frame(now){ lastRaf=performance.now(); step(now); requestAnimationFrame(frame); }
  function startWatchdog(){ if(wdOn)return; wdOn=true;
    setInterval(()=>{ if(performance.now()-lastRaf>250) step(performance.now()); },33); }

  scene.updateMatrixWorld(true);
  setStep(0);
  requestAnimationFrame(frame);
  startWatchdog();
})();
