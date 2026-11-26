/* Breast core-biopsy leaflet — MEDIA edition stage app.
   Same step machine, audio and i18n as the 3D page; the canvas is replaced by a
   media stage: each step shows a graded still (JPG) or a drawn SVG diagram, and
   video beats play a short muted clip when present. */
(() => {
  const stage = document.getElementById('mediaStage');
  const chips = document.getElementById('steps');
  const label = document.getElementById('stepLabel');
  const note = document.getElementById('stepNote');
  const srText = document.getElementById('srText');
  const stepCount = document.getElementById('stepCount');
  const btnPlay = document.getElementById('btnPlay');
  const langPick = document.getElementById('langPick');
  const btnSound = document.getElementById('btnSound');
  /* AI disclosure sits ON the media, not only in the intro copy: feedback was that
     patients could not tell the pictures were synthetic. */
  const aiBadge = document.createElement('span');
  aiBadge.className = 'ai-badge';
  aiBadge.setAttribute('data-i18n', 'k261');
  aiBadge.textContent = 'AI-generated illustration';
  if (stage) stage.appendChild(aiBadge);

  /* media: kind = 'img' | 'svg' | 'vid'; vid falls back to img while loading */
  const STEPS = [
    {t:"Your breast and the lump",
     n:"The lump your doctor wants to check is inside your breast. Most breast lumps are not cancer, but a sample is the only way to know for certain.",
     media:{kind:'img', src:'assets/b1_anatomy.jpg?v=19', alt:"Side-view illustration of the breast: fat, gland and ducts around a grey lump, sitting on the chest muscle."}},
    {t:"Finding the lump with ultrasound",
     n:"You lie on your back with your arm above your head. The doctor moves an ultrasound probe over the skin, and the screen shows the lump, where it sits and how deep it is.",
     media:{kind:'vid', src:'assets/m2_probe_glide.mp4?v=19', poster:'assets/b2_probe.jpg', alt:"A sterile-sleeved ultrasound probe glides over the skin with a little clear gel, guided by a gloved hand."}},
    {t:"Cleaning the skin",
     n:"The skin over the lump is cleaned and the area is covered with a sterile drape. That is all this step involves, and it takes a moment.",
     media:{kind:'vid', src:'assets/m3_drape.mp4?v=19', poster:'assets/b3_drape.jpg', alt:"Gloved hands unfold a light-blue sterile drape and bring it gently toward you."}},
    {t:"Numbing the area",
     n:"Local anaesthetic is injected into the skin and deeper into the breast. It stings for a few seconds, and then the area goes numb. You stay awake the whole time.",
     media:{kind:'vid', src:'assets/m4_lido.mp4?v=19', poster:'assets/b4_lido.jpg?v=19', alt:"A small syringe with a fine needle advances into the skin beside the areola; the skin dimples as the anaesthetic goes in."}},
    {t:"A small nick in the skin",
     n:"The anaesthetic has taken effect and the skin is numb. A tiny nick is made in the skin at the spot the needle will enter, so the biopsy needle passes through cleanly.",
     media:{kind:'img', src:'assets/b5_nick.jpg?v=19', alt:"A blue-gloved hand holds a fine scalpel blade against the numb skin, making a tiny nick at the entry spot."}},
    {t:"The biopsy needle goes in",
     n:"The biopsy needle is introduced under ultrasound guidance and guided into the lump. When the device fires you will hear a loud click and see a quick movement; each time, a thin core of tissue is taken. The needle is drawn back and re-introduced until enough tissue has been collected.",
     media:{kind:'vid', src:'assets/m6_needle.mp4?v=19', poster:'assets/b6_needle.jpg?v=19', alt:"Beside the flat grey linear ultrasound probe, the biopsy needle advances into the skin beside the areola and stops, the skin dimpling at the entry point."}},
    {t:"The marker clip",
     n:"A very small clip is left at the spot, so the area can be found again later. You cannot feel it, and it is safe to have an MRI scan with it in place.",
     media:{kind:'img', src:'assets/b7_clip.jpg?v=19', alt:"Side-view illustration: a small metallic marker clip sits inside the grey lump; a magnified inset shows the clip."}},
    {t:"Pressure, then a dressing",
     n:"Firm pressure is held over the spot to stop any bleeding, then a dressing is applied. It stays on, and stays dry, for 48 hours.",
     media:{kind:'img', src:'assets/b8_dressing.jpg?v=19', alt:"A blue-gloved hand presses a folded square of sterile gauze firmly onto the skin beside the areola; a strip of tape lies ready on the drape."}},
    {t:"Afterwards, and your results",
     n:"The numbness wears off within a few hours. Soreness and bruising settle over a few days to two weeks. Use paracetamol if you need it, not ibuprofen or aspirin. Results usually take about two weeks.",
     media:{kind:'img', src:'assets/b9_after.jpg?v=19', alt:"From below, the masked, capped clinician looks down with a warm smile and a reassuring nod; a band of blue drape runs along the bottom of the frame."}},
  ];

  let cur=0, playing=false, guided=false, timer=null, curClip=null;
  /* Synthesised biopsy-gun click (cock + fire), fired in sync with step 6's clip. */
  const gunClick = new Audio('assets/click.mp3?cv=8');
  gunClick.preload = 'auto'; gunClick.volume = 0.9;   /* loud but leaves headroom over narration */
  function gunTick(e){
    const v = e.target;
    if(!audioOn || !v || v.tagName!=='VIDEO') return;
    if(v.currentTime < 0.20){ v.__clicked = false; return; }
    if(!v.__clicked && v.currentTime >= 0.55){
      v.__clicked = true;
      try{ gunClick.currentTime = 0; const p = gunClick.play(); if(p&&p.catch) p.catch(()=>{}); }catch(_){}
    }
  }
  const clipCache={}, mediaCache={};

  /* --- media stage -------------------------------------------------------- */
  function mountMedia(step){
    const m=step.media;
    let node=mediaCache[m.src];
    if(!node){
      if(m.kind==='vid'){
        node=document.createElement('video');
        node.src=m.src; node.muted=true; node.playsInline=true; node.loop=true; node.preload='auto';
        if(m.poster) node.poster=m.poster;
        node.setAttribute('aria-hidden','true');
      } else {
        node=document.createElement('img');
        node.src=m.src; node.alt=m.alt||'';
        node.decoding='async';
      }
      node.className='mediaEl';
      mediaCache[m.src]=node;
    }
    node.alt = (m.kind==='vid') ? '' : (m.alt||'');
    while(stage.firstChild) stage.removeChild(stage.firstChild);
    stage.appendChild(node);
    if(aiBadge && !stage.contains(aiBadge)) stage.appendChild(aiBadge);   /* survives step changes */
    if(m.kind==='vid'){
      node.currentTime=0;
      if(/m6_needle/.test(m.src)){ node.addEventListener('timeupdate', gunTick); }
      const p=node.play(); if(p&&p.catch)p.catch(()=>{});
    }
    stage.setAttribute('aria-label', m.alt||'');
  }

  STEPS.forEach((s,i)=>{
    const b=document.createElement('button');
    b.className='stepchip'; b.setAttribute('role','tab');
    b.textContent=(i+1)+'. '+s.t;
    b.onclick=()=>{ stopPlay(); setStep(i); };
    chips.appendChild(b);
  });

  function setStep(i){
    cur=i; const s=STEPS[i];
    mountMedia(s);
    label.innerHTML='<b>Step '+(i+1)+' of '+STEPS.length+'.</b> '+s.t;
    note.textContent=s.n;
    srText.textContent='Step '+(i+1)+' of '+STEPS.length+'. '+s.t+'. '+s.n;
    stepCount.textContent=(i+1)+' / '+STEPS.length;
    refreshNav();
    [...chips.children].forEach((c,j)=>c.setAttribute('aria-current',String(j===i)));
    if(audioOn) playStepAudio(i);
  }
  function stopPlay(){ playing=false; guided=false; clearTimeout(timer); stopClip(); if(btnPlay) btnPlay.textContent='▶ Play all'; }
  function stopClip(){ if(curClip){ try{curClip.pause();}catch(_){} curClip=null; } }

  const btnPrev=document.getElementById('btnPrev');
  const btnNext=document.getElementById('btnNext');
  function refreshNav(){
    const atFirst=cur<=0, atLast=cur>=STEPS.length-1;
    if(btnPrev){ btnPrev.disabled=atFirst; btnPrev.setAttribute('aria-disabled',String(atFirst)); }
    if(btnNext){ btnNext.disabled=atLast; btnNext.setAttribute('aria-disabled',String(atLast)); }
  }
  function prevStep(){ stopPlay(); if(cur>0) setStep(cur-1); }
  function nextStep(){ stopPlay(); if(cur>0||true){ if(cur<STEPS.length-1) setStep(cur+1); } }
  if(btnPrev) btnPrev.onclick=prevStep;
  if(btnNext) btnNext.onclick=nextStep;

  btnPlay && btnPlay.addEventListener('click',()=>{
    if(playing){ stopPlay(); return; }
    playing=true; guided=true; btnPlay.textContent='⏸ Pause';
    setStep(cur>=STEPS.length-1?0:cur);
  });
  function clipEnd(){ if(guided){ if(cur>=STEPS.length-1){ stopPlay(); } else { setStep(cur+1); } } }

  /* --- audio (identical contract to the 3D page) --------------------------- */
  let audioOn=true;   /* default ON (owner request) */
  const localeBroken={};
  function localeSrc(code,i){
    if(!code || localeBroken[code]) return null;
    if(typeof AUDIO_LOCALES==='undefined') return null;
    const set=AUDIO_LOCALES[code];
    const v='?av=3';
    return (set && set[String(i+1)]) ? set[String(i+1)]+v : null;
  }
  function getClip(i){
    const code=document.documentElement.lang||'en';
    const key=code+':'+i;
    if(clipCache[key]) return clipCache[key];
    const src=localeSrc(code,i);
    if(src){
      const a=new Audio(); a.src=src;
      a.addEventListener('ended',clipEnd);
      a.addEventListener('error',()=>{ localeBroken[code]=true; delete clipCache[key]; if(curClip===a) playStepAudio(i); });
      clipCache[key]=a; return a;
    }
    try{
      const entry=(typeof AUDIO!=='undefined')?AUDIO[String(i+1)]:undefined;
      if(!entry) return null;
      const mime=(typeof AUDIO!=='undefined'&&AUDIO.mime)?AUDIO.mime:'audio/mpeg';
      const bin=atob(entry.b64), n=bin.length, arr=new Uint8Array(n);
      for(let j=0;j<n;j++) arr[j]=bin.charCodeAt(j);
      const a=new Audio(); a.src=URL.createObjectURL(new Blob([arr],{type:mime}));
      a.addEventListener('ended',clipEnd);
      clipCache[key]=a; return a;
    }catch(_){ return null; }
  }
  function playStepAudio(i){
    stopClip();
    const a=getClip(i); if(!a) return false;
    try{ a.currentTime=0; }catch(_){}
    const p=a.play(); if(p&&p.catch) p.catch(()=>{});
    curClip=a; return true;
  }
  btnSound && btnSound.addEventListener('click',()=>{
    audioOn=!audioOn;
    btnSound.setAttribute('aria-pressed',String(audioOn));
    /* label shows the STATE (conventional): on = narration is playing */
    btnSound.textContent=audioOn?'🔊 Sound on':'🔇 Sound off';
    if(audioOn){ playStepAudio(cur); } else { stopClip(); }
  });

  /* --- i18n (same I18N table as the 3D page) -------------------------------- */
  const EN_TXT={};
  document.querySelectorAll('[data-i18n]').forEach(el=>{ EN_TXT[el.dataset.i18n]=el.textContent; });
  const EN_STEPS=STEPS.map(s=>({t:s.t,n:s.n}));
  let lang='en';
  function setText(el,v){ if(el) el.textContent=v; }
  function stepLabel(cat,n,m){
    const t=(cat&&cat.html&&cat.html.k80)||EN_TXT.k80||'Step {n} of {m}.';
    return t.replace('{n}',n).replace('{m}',m);
  }
  function applyLang(code){
    lang=code;
    const cat=(code!=='en'&&typeof I18N!=='undefined'&&I18N[code])?I18N[code]:null;
    document.querySelectorAll('[data-i18n]').forEach(el=>{
      const v=cat&&cat.html?cat.html[el.dataset.i18n]:null;
      setText(el, v||EN_TXT[el.dataset.i18n]||el.textContent);
    });
    STEPS.forEach((s,i)=>{
      const tr=cat&&cat.steps?cat.steps['step'+String(i+1).padStart(2,'0')]:null;
      s.t=(tr&&tr.t)||EN_STEPS[i].t; s.n=(tr&&tr.n)||EN_STEPS[i].n;
    });
    [...chips.children].forEach((b,i)=>{ b.textContent=(i+1)+'. '+STEPS[i].t; });
    document.documentElement.lang=code;
    setStep(cur);
    if(langPick) langPick.value=code;
    renderPrintSheet();
  }

  /* Print is the take-home sheet. The interactive page can only show one step at a
     time; on paper that product is useless, so a hidden sheet is rendered with all
     nine steps, each with its picture and caption, in the current language. */
  let printSheet=null;
  function renderPrintSheet(){
    if(!printSheet){
      printSheet=document.createElement('section');
      printSheet.className='printsheet';
      printSheet.setAttribute('aria-hidden','true');
      const wrap=document.querySelector('.wrap')||document.body;
      wrap.appendChild(printSheet);
    }
    printSheet.textContent='';
    STEPS.forEach((s,i)=>{
      const fig=document.createElement('figure');
      const img=document.createElement('img');
      img.src=(s.media.kind==='vid')?(s.media.poster||''):s.media.src;
      img.alt=s.media.alt||'';
      const cap=document.createElement('figcaption');
      const b=document.createElement('b');
      b.textContent=(i+1)+'. '+s.t;
      const p=document.createElement('p');
      p.textContent=s.n;
      cap.appendChild(b); cap.appendChild(p);
      fig.appendChild(img); fig.appendChild(cap);
      printSheet.appendChild(fig);
    });
    const note = document.createElement('p');
    note.className = 'print-note';
    note.setAttribute('data-i18n', 'k262');
    note.textContent = 'All pictures in this guide are AI-generated illustrations; no real patient is shown.';
    printSheet.appendChild(note);
  }
  langPick && langPick.addEventListener('change',()=>{ applyLang(langPick.value); if(audioOn) playStepAudio(cur); else stopClip(); });

  document.addEventListener('keydown',e=>{
    let handled=false;
    if(e.key==='ArrowLeft'){ prevStep(); handled=true; }
    else if(e.key==='ArrowRight'){ nextStep(); handled=true; }
    else if(e.key==='Home'){ stopPlay(); setStep(0); handled=true; }
    else if(e.key==='End'){ stopPlay(); setStep(STEPS.length-1); handled=true; }
    if(handled) e.preventDefault();
  });

  if(btnSound){ btnSound.setAttribute('aria-pressed','true'); btnSound.textContent='🔊 Sound on'; }
  /* browsers block audio until a gesture: start narration on the first tap/keypress */
  const startOnGesture = () => { if(audioOn && !curClip) playStepAudio(cur); };
  document.addEventListener('pointerdown', startOnGesture, {once:true});
  document.addEventListener('keydown', startOnGesture, {once:true});
  renderPrintSheet();
  setStep(0);
})();
