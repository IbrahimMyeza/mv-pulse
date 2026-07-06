// ── STATE ──
const S={screen:'home',feedTab:'for_you',currentIdx:0,muted:false,openSheet:null,
  commentVideoId:null,commentTab:'comments',recording:false,mediaRecorder:null,
  recordedChunks:[],recordTimer:null,recordSeconds:0,progressAF:null,
  liked:new Set(),saved:new Set(),shareVideoId:null,
  voiceState:'idle',playbackAudio:null,playbackPlaying:false,
  optionsVideoId:null,optionsCreator:null,
  mediaStream:null,stopIntent:'preview',recVideoEl:null,
  pendingSwitchVideoId:null,preConfirmState:null,draftMimeType:null,
  statusFlashTimer:null,autosaveTimer:null};

const FEED=window.FEED_ITEMS||[];
const ME=window.CURRENT_USER;
const PROF_STATS=window.PROFILE_STATS||{followers:0,following:0,videos:0,replies:0};
const PROF_VIDEOS=window.PROFILE_VIDEOS||[];
const PROF_USER=window.PROFILE_USER||'';
const PROF_AVATAR=window.PROFILE_AVATAR||'';
const PROF_IS_OWNER=window.PROFILE_IS_OWNER||false;
let NOTIFS=window.NOTIFICATIONS||[];
let NOTIFS_UNREAD=window.NOTIFS_UNREAD||0;
const IS_FOLLOWING=window.IS_FOLLOWING||false;

FEED.forEach(i=>{if(i.kind==='video'){if(i.is_liked)S.liked.add(i.id);if(i.is_saved)S.saved.add(i.id);}});

// ── VIDEO OVERLAY CACHE ── id -> full video payload, populated whenever a grid/list renders
const _pvgCache={};
FEED.forEach(i=>{if(i.kind==='video')_pvgCache[i.id]=i;});

// ── INIT ──
document.addEventListener('DOMContentLoaded',()=>{
  initTheme();
  initBadge();renderFeed();initNavigation();initFeedTabs();
  initDiscoverScreen();initNotifScreen();renderProfileScreen();
  initSheetGestures();initUploadInput();initAuthTabs();initCommentTabs();initCommentInput();
  initVoiceInterruptionHandlers();showDraftBanner();
  if(window.ACTIVE_TAB&&window.ACTIVE_TAB!=='home')switchScreen(window.ACTIVE_TAB);
  if(!navigator.share)document.getElementById('native-share-btn')?.classList.add('hidden');
  // play first video immediately — don't wait for IntersectionObserver's first tick
  const firstVid=document.querySelector('.vslide[data-idx="0"] video');
  if(firstVid&&firstVid.src){firstVid.muted=true;firstVid.play().catch(()=>{});startProgress(0,firstVid);}
});

// ── TOAST ──
let _tt;
function toast(m){const e=document.getElementById('toast');e.textContent=m;e.classList.add('show');clearTimeout(_tt);_tt=setTimeout(()=>e.classList.remove('show'),2400);}

// ── BUTTON FEEDBACK ──
function btnFeedback(icon,cls){if(!icon)return;icon.classList.remove(cls);void icon.offsetWidth;icon.classList.add(cls);icon.addEventListener('animationend',()=>icon.classList.remove(cls),{once:true});}

// ── BADGE ──
function initBadge(){const b=document.getElementById('notif-badge');if(NOTIFS_UNREAD>0){b.textContent=NOTIFS_UNREAD>99?'99+':NOTIFS_UNREAD;b.classList.remove('hidden');}}

// ── NAVIGATION ──
function switchScreen(name){
  if(S.screen===name)return;
  pauseCurrentVideo();
  document.querySelectorAll('.screen').forEach(s=>{s.classList.remove('active');s.classList.add('hidden');});
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  const scr=document.getElementById('screen-'+name);
  if(scr){scr.classList.remove('hidden');scr.classList.add('active');}
  const nb=document.querySelector(`.nav-btn[data-screen="${name}"]`);
  if(nb)nb.classList.add('active');
  const hc=document.getElementById('topbar-home-center');
  const ot=document.getElementById('topbar-screen-title');
  const sb=document.getElementById('topbar-search-btn');
  const titles={discover:'Discover',notifs:'Activity',profile:'Profile'};
  if(name==='home'){
    hc.classList.remove('hidden');ot.classList.add('hidden');sb.classList.add('hidden');
    if(S.screen!=='home')resumeCurrentVideo();
  }else{
    hc.classList.add('hidden');ot.textContent=titles[name]||'';ot.classList.remove('hidden');sb.classList.remove('hidden');
  }
  S.screen=name;
  if(name==='notifs')loadNotifs();
}

function initNavigation(){
  document.querySelectorAll('.nav-btn[data-screen]').forEach(b=>b.addEventListener('click',()=>switchScreen(b.dataset.screen)));
  document.getElementById('create-nav-btn').addEventListener('click',()=>{if(!ME){openAuthModal();return;}openSheet('upload-modal');});
}

// ── HELPERS ──
function fmtNum(n){if(!n)return'0';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return String(n);}
function fmtInit(s){return(String(s||'?')[0]).toUpperCase();}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function timeAgo(iso){if(!iso)return'';const d=new Date(iso),n=new Date(),sec=Math.floor((n-d)/1000);if(sec<60)return sec+'s';if(sec<3600)return Math.floor(sec/60)+'m';if(sec<86400)return Math.floor(sec/3600)+'h';return Math.floor(sec/86400)+'d';}
async function api(url,method='GET',body=null){
  const o={method,credentials:'same-origin',headers:{Accept:'application/json'}};
  if(body){o.headers['Content-Type']='application/json';o.body=JSON.stringify(body);}
  const r=await fetch(url,o);
  if(r.status===401){openAuthModal();throw new Error('unauth');}
  if(!r.ok)throw new Error('api '+r.status);
  return r.json();
}

// ── SVG ICONS ──
const SVG={
  heart:`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`,
  comment:`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  share:`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>`,
  mic:`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>`,
  bookmark:`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>`,
  soundOn:`<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14" stroke="currentColor" stroke-width="2" fill="none"/></svg>`,
  soundOff:`<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19"/><line x1="23" y1="9" x2="17" y2="15" stroke="currentColor" stroke-width="2"/><line x1="17" y1="9" x2="23" y2="15" stroke="currentColor" stroke-width="2"/></svg>`,
  play:`<svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21" fill="white"/></svg>`,
};

// ── FEED ──
function renderFeed(){
  const feed=document.getElementById('feed');
  if(!FEED.length){
    feed.innerHTML=`<div class="vslide"><div class="vplaceholder"><div class="vplaceholder-icon">🎬</div><p class="vplaceholder-title">No videos yet</p><p class="vplaceholder-sub">Be the first to upload</p></div></div>`;
    return;
  }
  FEED.forEach((item,idx)=>{
    const slide=document.createElement('div');
    slide.className='vslide';slide.dataset.idx=idx;
    if(item.kind==='hot_thread'){
      slide.innerHTML=`<div class="ht-slide"><span class="ht-label">🔥 Hot Thread</span><h2 class="ht-title">${esc(item.title||'')}</h2><p class="ht-meta">${fmtNum(item.reply_count)} replies · ${esc(item.creator||'')}</p><p class="ht-meta">${esc(item.caption||'')}</p><a class="ht-cta" href="${esc(item.target_url||'#')}">${esc(item.cta_text||'Join Discussion')}</a></div>`;
    } else {
      slide.dataset.videoid=item.id;
      const hasV=item.video_url&&item.video_url!=='null';
      // idx 0: eager src + preload=auto so first frame is ready before user scrolls
      const isFirst=idx===0;
      slide.innerHTML=`
        ${hasV&&item.thumbnail_url?`<img class="vid-bg" src="${esc(item.thumbnail_url)}" alt="" aria-hidden="true">`:''}
        ${hasV?`
        <video class="slide-vid" ${isFirst?'preload="auto"':'preload="metadata"'} playsinline loop muted ${isFirst?`src="${esc(item.video_url)}"` : `data-src="${esc(item.video_url)}"`}></video>`:''}
        ${!hasV?`<div class="vplaceholder"><div class="vplaceholder-icon">🎬</div><p class="vplaceholder-title">${esc(item.title||'Video')}</p><p class="vplaceholder-sub">${esc(item.caption||'')}</p></div>`:''}
        <div class="grad-top"></div><div class="grad-bot"></div>
        <div class="play-flash" id="pf-${idx}"><div class="play-circle">${SVG.play}</div></div>
        <div class="heart-burst" id="hb-${idx}"><span>❤️</span></div>
        <button class="sound-btn" onclick="toggleMute(event)">${S.muted?SVG.soundOff:SVG.soundOn}</button>
        ${creatorInfoBlock(item)}
        ${actionBarBlock(item)}
        <div class="vprogress"><div class="vprogress-fill" id="progfill-${idx}"></div></div>`;
      attachGestures(slide,item,idx);
    }
    feed.appendChild(slide);
  });
  initIntersectionObserver();
}

function goToProfile(username,e){
  if(e)e.stopPropagation();
  if(!username)return;
  location.href='/profile/'+encodeURIComponent(username);
}

function captionBlock(v){
  const full=v.caption||v.title||'';
  if(!full)return '';
  if(full.length<=90)return `<p class="vcaption">${esc(full)}</p>`;
  const short=esc(full.slice(0,90).trimEnd());
  return `<p class="vcaption" data-full="${esc(full)}" data-state="short">${short}… <span class="vcap-more" onclick="toggleCaption(this,event)">more</span></p>`;
}

function toggleCaption(el,e){
  e.stopPropagation();
  const p=el.parentElement;
  const full=p.dataset.full||'';
  if(p.dataset.state==='short'){
    p.innerHTML=`${esc(full)} <span class="vcap-more" onclick="toggleCaption(this,event)">less</span>`;
    p.dataset.state='full';
  } else {
    p.innerHTML=`${esc(full.slice(0,90).trimEnd())}… <span class="vcap-more" onclick="toggleCaption(this,event)">more</span>`;
    p.dataset.state='short';
  }
}

function creatorInfoBlock(v){
  const username=v.creator_username||v.creator||'';
  return `<div class="creator-info">
      <div class="creator-row">
        <button type="button" class="cavatar" onclick="goToProfile('${esc(username)}',event)" aria-label="Open profile">${fmtInit(v.creator||'?')}</button>
        <button type="button" class="cname" onclick="goToProfile('${esc(username)}',event)">@${esc(username||'unknown')}</button>
        ${v.can_follow_creator?`<button type="button" class="follow-pill${v.creator_is_followed?' following':''}" data-creator="${esc(username)}" onclick="followUser(this,event)">${v.creator_is_followed?'Following':'Follow'}</button>`:''}
        <button type="button" class="options-dot" onclick="openOptionsMenu(${v.id},'${esc(username)}',event)" aria-label="More options">···</button>
      </div>
      ${captionBlock(v)}
      ${v.topic?`<span class="vtags">#${esc(v.topic)} #${esc(v.region||'')}</span>`:''}
      ${v.voice_replies>0?`<span class="voice-badge">🎤 ${fmtNum(v.voice_replies)} voice ${v.voice_replies===1?'reply':'replies'}</span>`:''}
    </div>`;
}

function actionBarBlock(v){
  const liked=S.liked.has(v.id),saved=S.saved.has(v.id);
  const username=v.creator_username||v.creator||'';
  const followDot=v.can_follow_creator&&!v.creator_is_followed
    ?`<div class="ab-follow-dot"><svg viewBox="0 0 10 10"><path d="M5 1v8M1 5h8" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/></svg></div>`:''
  ;
  return `<div class="action-bar">
      <button type="button" class="abtn ab-creator-btn" onclick="goToProfile('${esc(username)}',event)" aria-label="View profile">
        <div class="ab-av">${fmtInit(v.creator||'?')}</div>${followDot}
      </button>
      <button type="button" class="abtn" onclick="likeVideo(${v.id},this)"><div class="abtn-icon${liked?' liked':''}">${SVG.heart}</div><span class="abtn-count">${fmtNum(v.likes)}</span></button>
      <button type="button" class="abtn" onclick="openComments(${v.id},this)"><div class="abtn-icon">${SVG.comment}</div><span class="abtn-count">${fmtNum((v.text_comments_count||0)+(v.voice_replies||0))}</span></button>
      <button type="button" class="abtn" onclick="shareVideo(${v.id})"><div class="abtn-icon">${SVG.share}</div><span class="abtn-count">${fmtNum(v.shares_count)}</span></button>
      <button type="button" class="abtn" onclick="openVoicePanelForVideo(${v.id},this)"><div class="abtn-icon">${SVG.mic}</div><span class="abtn-count">${fmtNum(v.voice_replies)}</span></button>
      <button type="button" class="abtn" onclick="saveVideo(${v.id},this)"><div class="abtn-icon${saved?' saved':''}">${SVG.bookmark}</div><span class="abtn-count">${fmtNum(v.saves_count)}</span></button>
    </div>`;
}

function attachGestures(slide,item,idx){
  let tapTimer=null,tapCount=0;
  slide.addEventListener('touchend',e=>{
    if(e.target.closest('.action-bar,.sound-btn,.follow-pill,.options-dot,.vcaption,.vcap-more,.cavatar,.cname'))return;
    tapCount++;
    if(tapCount===1){tapTimer=setTimeout(()=>{tapCount=0;togglePlay(idx);},250);}
    else if(tapCount>=2){clearTimeout(tapTimer);tapCount=0;doubleTapLike(item.id,idx);}
  },{passive:true});
}

function initIntersectionObserver(){
  const obs=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      const slide=entry.target,idx=parseInt(slide.dataset.idx),vid=slide.querySelector('video');
      if(entry.isIntersecting&&entry.intersectionRatio>=0.6){
        S.currentIdx=idx;
        if(vid&&!vid.src&&vid.dataset.src){
          vid.src=vid.dataset.src;vid.load();
          vid.onerror=()=>{
            if(!slide.querySelector('.vplaceholder')){
              const ph=document.createElement('div');ph.className='vplaceholder';
              ph.innerHTML='<div class="vplaceholder-icon">📹</div><p class="vplaceholder-title">Video unavailable</p>';
              slide.insertBefore(ph,slide.querySelector('.grad-top'));
            }
          };
        }
        if(vid){vid.muted=S.muted;vid.play().catch(()=>{});}
        startProgress(idx,vid);preloadAdj(idx);
      } else {
        if(vid){vid.pause();vid.currentTime=0;}
        stopProgress();
      }
    });
  },{threshold:[0.6]});
  document.querySelectorAll('.vslide').forEach(s=>obs.observe(s));
}

function preloadAdj(idx){
  [1,2,-1].forEach(d=>{
    const next=document.querySelector(`.vslide[data-idx="${idx+d}"]`);
    if(!next)return;const vid=next.querySelector('video');
    if(vid&&!vid.src&&vid.dataset.src){vid.src=vid.dataset.src;vid.preload='auto';vid.load();}
  });
}

function startProgress(idx,vid){
  stopProgress();if(!vid)return;
  const fill=document.getElementById('progfill-'+idx);if(!fill)return;
  function tick(){if(vid.duration)fill.style.width=(vid.currentTime/vid.duration*100)+'%';S.progressAF=requestAnimationFrame(tick);}
  S.progressAF=requestAnimationFrame(tick);
}
function stopProgress(){if(S.progressAF){cancelAnimationFrame(S.progressAF);S.progressAF=null;}}

function togglePlay(idx){
  const vid=document.querySelector(`.vslide[data-idx="${idx}"] video`);if(!vid)return;
  const flash=document.getElementById('pf-'+idx);
  if(vid.paused){vid.play();}else{vid.pause();flash?.classList.add('show');setTimeout(()=>flash?.classList.remove('show'),600);}
}
function pauseCurrentVideo(){document.querySelector(`.vslide[data-idx="${S.currentIdx}"] video`)?.pause();}
function resumeCurrentVideo(){document.querySelector(`.vslide[data-idx="${S.currentIdx}"] video`)?.play().catch(()=>{});}

function toggleMute(e){
  e.stopPropagation();S.muted=!S.muted;
  document.querySelectorAll('video').forEach(v=>v.muted=S.muted);
  document.querySelectorAll('.sound-btn').forEach(b=>b.innerHTML=S.muted?SVG.soundOff:SVG.soundOn);
}

// ── VIDEO OVERLAY ──
function videoSlideInner(v){
  const hasV=v.video_url&&v.video_url!=='null';
  return `
    ${hasV&&v.thumbnail_url?`<img class="vid-bg" src="${esc(v.thumbnail_url)}" alt="" aria-hidden="true">`:''}
    ${hasV?`
    <video class="slide-vid" preload="metadata" playsinline loop ${S.muted?'muted':''} data-src="${esc(v.video_url)}"></video>`:''}
    ${!hasV?`<div class="vplaceholder"><div class="vplaceholder-icon">🎬</div><p class="vplaceholder-title">${esc(v.title||'Video')}</p><p class="vplaceholder-sub">${esc(v.caption||'')}</p></div>`:''}
    <div class="grad-top"></div><div class="grad-bot"></div>
    <div class="play-flash"><div class="play-circle">${SVG.play}</div></div>
    <div class="heart-burst"><span>❤️</span></div>
    <button type="button" class="sound-btn" onclick="toggleMute(event)" aria-label="Toggle sound">${S.muted?SVG.soundOff:SVG.soundOn}</button>
    ${creatorInfoBlock(v)}
    ${actionBarBlock(v)}
    <div class="vprogress"><div class="vprogress-fill"></div></div>`;
}

async function resolveVideoEntry(entry){
  if(entry&&typeof entry==='object')return entry.id!=null?entry:null;
  const id=entry;
  if(id==null)return null;
  if(_pvgCache[id])return _pvgCache[id];
  try{return await api('/api/videos/'+id);}catch(e){return null;}
}

async function openVideoFeed(list,startId){
  const resolved=(await Promise.all((list||[]).map(resolveVideoEntry))).filter(Boolean);
  if(!resolved.length){toast('Could not load video');return;}
  resolved.forEach(v=>_pvgCache[v.id]=v);
  let startIdx=resolved.findIndex(v=>v.id===startId);
  if(startIdx<0)startIdx=0;
  renderVideoFeedOverlay(resolved,startIdx);
}

let _voObserver=null,_voProgressAF=null,_voProgressSlide=null,_voActiveVideo=null;

function renderVideoFeedOverlay(videos,startIdx){
  pauseCurrentVideo();
  const wrap=document.getElementById('vo-feed');
  if(_voObserver){_voObserver.disconnect();_voObserver=null;}
  wrap.innerHTML='';
  document.getElementById('vo').classList.add('open');
  videos.forEach(v=>{
    const slide=document.createElement('div');
    slide.className='vslide';
    slide.dataset.voId=v.id;
    slide.innerHTML=videoSlideInner(v);
    attachVoGestures(slide,v);
    wrap.appendChild(slide);
  });
  const slides=[...wrap.children];
  wrap.scrollTop=startIdx*wrap.clientHeight;
  _voObserver=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      const vid=entry.target.querySelector('video');
      if(vid&&!vid.src&&vid.dataset.src){vid.src=vid.dataset.src;vid.load();}
      if(entry.isIntersecting&&entry.intersectionRatio>=0.6){
        _voActiveVideo=vid||null;
        if(vid){vid.muted=S.muted;vid.play().catch(()=>{});}
        _voStartProgress(entry.target,vid);
      } else {
        if(_voActiveVideo===vid)_voActiveVideo=null;
        if(vid){vid.pause();}
        _voStopProgress(entry.target);
      }
    });
  },{root:wrap,threshold:[0.6]});
  slides.forEach(s=>_voObserver.observe(s));
}

function _voStartProgress(slideEl,vid){
  if(!vid)return;
  _voStopProgress(null);
  _voProgressSlide=slideEl;
  const fill=slideEl.querySelector('.vprogress-fill');
  function tick(){
    if(fill&&vid.duration)fill.style.width=(vid.currentTime/vid.duration*100)+'%';
    _voProgressAF=requestAnimationFrame(tick);
  }
  _voProgressAF=requestAnimationFrame(tick);
}

function _voStopProgress(slideEl){
  if(slideEl&&_voProgressSlide!==slideEl)return;
  if(_voProgressAF)cancelAnimationFrame(_voProgressAF);
  _voProgressAF=null;_voProgressSlide=null;
}

function attachVoGestures(slideEl,v){
  let lastTap=0,tapTimer=null;
  slideEl.addEventListener('click',e=>{
    if(e.target.closest('.action-bar,.sound-btn,.follow-pill,.options-dot,.vcaption,.vcap-more,.cavatar,.cname,.vo-back'))return;
    const now=Date.now();
    if(now-lastTap<300){
      clearTimeout(tapTimer);lastTap=0;
      const burst=slideEl.querySelector('.heart-burst');
      if(burst){burst.classList.remove('fire');void burst.offsetWidth;burst.classList.add('fire');}
      if(ME&&!S.liked.has(v.id)){
        const btn=slideEl.querySelector('.abtn');
        if(btn)likeVideo(v.id,btn);
      }
    } else {
      lastTap=now;
      tapTimer=setTimeout(()=>{
        const vid=slideEl.querySelector('video');if(!vid)return;
        const flash=slideEl.querySelector('.play-flash');
        if(vid.paused){vid.play();}else{vid.pause();flash?.classList.add('show');setTimeout(()=>flash?.classList.remove('show'),600);}
      },300);
    }
  });
}

function closeVideoOverlay(){
  document.getElementById('vo').classList.remove('open');
  if(_voObserver){_voObserver.disconnect();_voObserver=null;}
  _voActiveVideo=null;
  _voStopProgress(null);
  const wrap=document.getElementById('vo-feed');
  wrap.querySelectorAll('video').forEach(v=>v.pause());
  wrap.innerHTML='';
  if(S.screen==='home')resumeCurrentVideo();
}

function initFeedTabs(){
  document.querySelectorAll('.feed-tab').forEach(b=>{
    b.addEventListener('click',()=>{
      const tab=b.dataset.feed;
      if(tab===S.feedTab)return;
      document.querySelectorAll('.feed-tab').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');S.feedTab=tab;
      if(tab==='following'){
        if(!ME){openAuthModal();return;}
        const has=FEED.some(i=>i.kind==='video'&&i.creator_is_followed);
        if(!has)toast('Follow creators to see their videos here');
      }
    });
  });
}

// ── ACTIONS ──
async function likeVideo(id,btn){
  if(!ME){openAuthModal();return;}
  const icon=btn.querySelector('.abtn-icon'),count=btn.querySelector('.abtn-count'),isLiked=S.liked.has(id);
  isLiked?S.liked.delete(id):S.liked.add(id);
  icon.classList.toggle('liked',!isLiked);
  btnFeedback(icon,'like-pop');
  try{const r=await api('/api/videos/'+id+'/like','POST');if(r&&count)count.textContent=fmtNum(r.likes||r.likes_count||0);}
  catch(e){isLiked?S.liked.add(id):S.liked.delete(id);icon.classList.toggle('liked',isLiked);toast('Could not like — try again');}
}

function doubleTapLike(id,idx){
  const burst=document.getElementById('hb-'+idx);
  if(burst){burst.classList.remove('fire');void burst.offsetWidth;burst.classList.add('fire');}
  if(!S.liked.has(id)&&ME){const btn=document.querySelector(`[onclick="likeVideo(${id},this)"]`);if(btn)likeVideo(id,btn);}
}

async function saveVideo(id,btn){
  if(!ME){openAuthModal();return;}
  const icon=btn.querySelector('.abtn-icon'),isSaved=S.saved.has(id);
  isSaved?S.saved.delete(id):S.saved.add(id);
  icon.classList.toggle('saved',!isSaved);
  btnFeedback(icon,'save-pop');
  if(!isSaved)toast('Saved');
  try{await api('/api/videos/'+id+'/save','POST');}
  catch(e){isSaved?S.saved.add(id):S.saved.delete(id);icon.classList.toggle('saved',isSaved);}
}

function shareVideo(id){
  S.shareVideoId=id;
  openSheet('share-sheet');
  api('/api/videos/'+id+'/share','POST').catch(()=>{});
}

function _fallbackCopy(txt){
  const ta=document.createElement('textarea');ta.value=txt;
  ta.style.cssText='position:fixed;top:-9999px;left:-9999px;opacity:0';
  document.body.appendChild(ta);ta.focus();ta.select();
  try{document.execCommand('copy');toast('Link copied!');}catch(e){toast('Could not copy link');}
  ta.remove();
}

function shareOpt(method){
  const url=location.origin+'/video/'+(S.shareVideoId||'');
  closeSheet('share-sheet');
  if(method==='copy'){
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(url).then(()=>toast('Link copied!')).catch(()=>_fallbackCopy(url));
    } else {_fallbackCopy(url);}
  } else if(method==='whatsapp'){
    window.open('https://wa.me/?text='+encodeURIComponent('Watch this on MV Pulse: '+url),'_blank');
  } else if(method==='twitter'){
    window.open('https://twitter.com/intent/tweet?text='+encodeURIComponent('Watch this on MV Pulse 🎥')+'&url='+encodeURIComponent(url),'_blank');
  } else if(method==='native'){
    navigator.share({title:'MV Pulse',url}).catch(()=>{});
  }
}

async function followUser(btn,e){
  e.stopPropagation();if(!ME){openAuthModal();return;}
  const username=btn.dataset.creator,following=btn.classList.contains('following');
  btn.textContent=following?'+ Follow':'Following';btn.classList.toggle('following',!following);
  try{await api('/api/profile/'+username+'/follow','POST');}
  catch(e){btn.textContent=following?'Following':'+ Follow';btn.classList.toggle('following',following);}
}

// ── TRUST & SAFETY ──
function openOptionsMenu(videoId,creator,e){
  e?.stopPropagation();
  S.optionsVideoId=videoId;S.optionsCreator=creator;
  const label=`@${creator||'creator'}`;
  document.getElementById('opt-creator-name').textContent=label;
  document.querySelectorAll('.opt-creator-ref').forEach(el=>el.textContent=label);
  openSheet('options-sheet');
}

function openReportSheet(){
  document.getElementById('options-sheet')?.classList.remove('open');
  S.openSheet=null;
  setTimeout(()=>{
    document.getElementById('report-sheet')?.classList.add('open');
    S.openSheet='report-sheet';
  },320);
}

function submitReport(reason){
  api('/api/videos/'+(S.optionsVideoId||0)+'/report','POST',{reason}).catch(()=>{});
  closeSheet('report-sheet');
  toast('Report submitted — thank you');
}

function blockCreator(){
  if(!S.optionsCreator)return;
  api('/api/profile/'+S.optionsCreator+'/block','POST').catch(()=>{});
  closeSheet('options-sheet');
  toast(`@${S.optionsCreator} blocked`);
}

function muteCreator(){
  if(!S.optionsCreator)return;
  api('/api/profile/'+S.optionsCreator+'/mute','POST').catch(()=>{});
  closeSheet('options-sheet');
  toast(`@${S.optionsCreator} muted`);
}

function notInterested(){
  const slide=document.querySelector(`.vslide[data-videoid="${S.optionsVideoId}"]`);
  if(slide){slide.style.opacity='0';setTimeout(()=>slide.remove(),350);}
  closeSheet('options-sheet');
  toast('Got it — fewer like this');
}

// ── AI SUMMARY ──
let _aiLoaded=false,_aiVideoId=null;
function toggleAiSummary(){
  const card=document.getElementById('ai-summary-card');
  if(!card)return;
  const wasOpen=card.classList.contains('vis');
  card.classList.toggle('vis',!wasOpen);
  if(wasOpen)return;
  if(!S.commentVideoId)return;
  if(_aiLoaded&&_aiVideoId===S.commentVideoId)return;
  _aiLoaded=false;_aiVideoId=S.commentVideoId;
  const loading=document.getElementById('ai-sum-loading');
  const text=document.getElementById('ai-sum-text');
  if(loading)loading.classList.remove('hidden');
  if(text)text.classList.add('hidden');
  api('/api/thread/'+S.commentVideoId+'/summary')
    .then(r=>{
      if(_aiVideoId!==S.commentVideoId)return;
      _aiLoaded=true;
      if(loading)loading.classList.add('hidden');
      if(text){
        text.textContent=r.summary_text||'No discussion summary yet — check back after more replies.';
        text.classList.remove('hidden');
      }
    })
    .catch(()=>{
      if(loading)loading.classList.add('hidden');
      if(text){text.textContent='Could not load summary — try again.';text.classList.remove('hidden');}
    });
}

function initCommentInput(){
  const el=document.getElementById('comment-input');
  if(!el)return;
  el.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submitComment();}});
}

// ── COMMENTS ──
function initCommentTabs(){
  document.querySelectorAll('#comment-tabs .stab').forEach(t=>{
    t.addEventListener('click',()=>{
      document.querySelectorAll('#comment-tabs .stab').forEach(b=>b.classList.remove('active'));
      t.classList.add('active');S.commentTab=t.dataset.tab;loadComments(S.commentVideoId);
    });
  });
}

function openComments(id,btn){
  btnFeedback(btn?.querySelector('.abtn-icon'),'tap-pop');
  S.commentVideoId=id;S.commentTab='comments';
  document.querySelectorAll('#comment-tabs .stab').forEach((b,i)=>b.classList.toggle('active',i===0));
  // reset AI summary
  document.getElementById('ai-summary-card')?.classList.remove('vis');
  openSheet('comments-sheet');loadComments(id);
}

async function loadComments(id){
  if(!id)return;
  const body=document.getElementById('comments-body');
  body.innerHTML='<div class="empty-msg">Loading…</div>';
  try{
    if(S.commentTab==='comments'){
      const r=await api('/api/videos/'+id+'/comments');const items=r.items||[];
      if(!items.length){body.innerHTML='<div class="empty-msg"><div class="empty-msg-icon">💬</div>No comments yet. Be first!</div>';return;}
      body.innerHTML=items.map(c=>`<div class="cmt-item"><div class="cmt-av">${fmtInit(c.username)}</div><div class="cmt-body"><span class="cmt-user">${esc(c.username)}</span><p class="cmt-text">${esc(c.content)}</p><span class="cmt-time">${timeAgo(c.created_at)}</span></div></div>`).join('');
    } else {
      const r=await api('/api/video/'+id+'/replies');const items=r.replies||[];
      if(!items.length){body.innerHTML='<div class="empty-msg"><div class="empty-msg-icon">🎤</div>No voice replies yet</div>';return;}
      body.innerHTML=items.map(vr=>`<div class="vr-item"><button class="vr-play" onclick="playVoiceReply('${esc(vr.audio_url||'')}',this)"><svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21" fill="white"/></svg></button><div class="vr-meta"><span class="vr-user">${esc(vr.username)}</span><p class="vr-trans">${esc(vr.transcript||'(voice reply)')}</p><span class="vr-dur">${vr.duration?(vr.duration|0)+'s':''}</span></div></div>`).join('');
    }
  }catch(e){console.error('loadComments:',e);body.innerHTML='<div class="empty-msg">Failed to load. Try again.</div>';}
}

async function submitComment(){
  if(!ME){openAuthModal();return;}
  const input=document.getElementById('comment-input'),content=input.value.trim();
  if(!content||!S.commentVideoId)return;input.value='';
  try{await api('/api/videos/'+S.commentVideoId+'/comments','POST',{content});toast('Comment posted!');await loadComments(S.commentVideoId);}
  catch(e){console.error('submitComment:',e);toast('Could not post comment');}
}

let vrAudio=null,vrActiveBtn=null;
const VR_PLAY='<svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21" fill="white"/></svg>';
const VR_PAUSE='<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16" fill="white"/><rect x="14" y="4" width="4" height="16" fill="white"/></svg>';
function playVoiceReply(url,btn){
  const isSame=btn===vrActiveBtn;
  if(vrAudio){
    vrAudio.pause();vrAudio=null;
    if(vrActiveBtn){vrActiveBtn.innerHTML=VR_PLAY;vrActiveBtn=null;}
    if(isSame)return;
  }
  if(!url)return;
  vrAudio=new Audio(url);vrActiveBtn=btn;
  vrAudio.play().catch(()=>{});
  if(btn)btn.innerHTML=VR_PAUSE;
  vrAudio.onended=()=>{
    vrAudio=null;
    if(vrActiveBtn){vrActiveBtn.innerHTML=VR_PLAY;vrActiveBtn=null;}
  };
}

// ── VOICE RECORDING ──

// IndexedDB draft persistence — a single global draft slot (one in-progress voice reply at a time)
const IDB_NAME='mvp_voice_drafts',IDB_STORE='drafts',IDB_KEY='current';
function idbOpen(){
  return new Promise((resolve,reject)=>{
    const req=indexedDB.open(IDB_NAME,1);
    req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains(IDB_STORE))req.result.createObjectStore(IDB_STORE);};
    req.onsuccess=()=>resolve(req.result);
    req.onerror=()=>reject(req.error);
  });
}
async function idbPutDraft(draft){
  try{
    const db=await idbOpen();
    await new Promise((resolve,reject)=>{
      const tx=db.transaction(IDB_STORE,'readwrite');
      tx.objectStore(IDB_STORE).put(draft,IDB_KEY);
      tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);
    });
    db.close();
  }catch(e){/* IndexedDB unavailable — autosave is best-effort */}
}
async function idbGetDraft(){
  try{
    const db=await idbOpen();
    const draft=await new Promise((resolve,reject)=>{
      const tx=db.transaction(IDB_STORE,'readonly');
      const req=tx.objectStore(IDB_STORE).get(IDB_KEY);
      req.onsuccess=()=>resolve(req.result||null);
      req.onerror=()=>reject(req.error);
    });
    db.close();
    return draft;
  }catch(e){return null;}
}
async function idbDeleteDraft(){
  try{
    const db=await idbOpen();
    await new Promise((resolve,reject)=>{
      const tx=db.transaction(IDB_STORE,'readwrite');
      tx.objectStore(IDB_STORE).delete(IDB_KEY);
      tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);
    });
    db.close();
  }catch(e){}
}
async function persistCurrentAsDraft(){
  if(!S.recordedChunks.length||!S.commentVideoId)return;
  const mimeType=(S.mediaRecorder&&S.mediaRecorder.mimeType)||S.draftMimeType||'audio/webm';
  const blob=new Blob(S.recordedChunks,{type:mimeType});
  await idbPutDraft({videoId:S.commentVideoId,blob,mimeType,duration:S.recordSeconds,savedAt:Date.now()});
}
function startAutosave(){
  stopAutosave();
  S.autosaveTimer=setInterval(()=>{persistCurrentAsDraft();flashStatusBadge('💾 Draft Saved');},15000);
}
function stopAutosave(){clearInterval(S.autosaveTimer);S.autosaveTimer=null;}

// ── ACTIVE VIDEO PAUSE/RESUME ──
function getActiveVideoEl(){
  if(document.getElementById('vo')?.classList.contains('open'))return _voActiveVideo;
  return document.querySelector(`.vslide[data-idx="${S.currentIdx}"] video`)||null;
}
function pauseActiveVideoForRecording(){
  const vid=getActiveVideoEl();
  S.recVideoEl=vid||null;
  if(vid){vid.pause();vid.muted=true;}
}
function resumeActiveVideoAfterRecording(){
  const vid=S.recVideoEl;S.recVideoEl=null;
  if(!vid||getActiveVideoEl()!==vid)return;
  vid.muted=S.muted;
  vid.play().catch(()=>{});
}

// ── STATUS BADGE ──
const VP_STATUS_LABEL={recording:'🔴 Recording',paused:'⏸ Paused',sending:'📤 Uploading',sent:'✅ Sent','send-failed':'⚠️ Failed'};
function updateStatusBadge(state){
  const el=document.getElementById('vp-status-badge');if(!el)return;
  el.textContent=VP_STATUS_LABEL[state]||'';
}
function flashStatusBadge(text){
  const el=document.getElementById('vp-status-badge');if(!el)return;
  el.textContent=text;
  clearTimeout(S.statusFlashTimer);
  S.statusFlashTimer=setTimeout(()=>updateStatusBadge(S.voiceState),1500);
}

// ── DRAFT BANNER ──
function fmtDuration(sec){
  sec=sec||0;const m=String(Math.floor(sec/60)).padStart(2,'0');const s=String(Math.floor(sec%60)).padStart(2,'0');return m+':'+s;
}
async function showDraftBanner(){
  const bar=document.getElementById('voice-draft-bar');if(!bar)return;
  if(S.voiceState!=='idle'||document.getElementById('voice-panel')?.classList.contains('open')){bar.hidden=true;return;}
  const draft=await idbGetDraft();
  if(!draft){bar.hidden=true;return;}
  const title=document.getElementById('vdb-title');
  const videoTitle=_pvgCache[draft.videoId]?.title;
  if(title)title.textContent=videoTitle?('Reply to "'+videoTitle+'"'):'Voice Reply Draft';
  const sub=document.getElementById('vdb-sub');
  if(sub)sub.textContent='Recorded '+fmtDuration(draft.duration)+' · Saved '+timeAgo(new Date(draft.savedAt).toISOString())+' ago';
  bar.hidden=false;
}
function hideDraftBanner(){
  const bar=document.getElementById('voice-draft-bar');if(bar)bar.hidden=true;
}
async function resumeDraftFromBanner(){
  const draft=await idbGetDraft();
  if(!draft){hideDraftBanner();return;}
  S.commentVideoId=draft.videoId;
  resetRecordingInMemoryOnly();
  S.recordedChunks=[draft.blob];
  S.recordSeconds=draft.duration||0;
  S.draftMimeType=draft.mimeType||'audio/webm';
  if(S.playbackAudio)S.playbackAudio.pause();
  S.playbackAudio=new Audio(URL.createObjectURL(draft.blob));
  S.playbackPlaying=false;
  S.playbackAudio.onended=()=>{
    S.playbackPlaying=false;
    document.getElementById('playback-ring')?.classList.remove('playing');
    const ps=document.getElementById('playback-status');if(ps)ps.textContent='Tap to preview';
    const pi=document.getElementById('pb-icon');if(pi)pi.innerHTML='<polygon points="5 3 19 12 5 21"/>';
  };
  const pd=document.getElementById('playback-duration');if(pd)pd.textContent=fmtDuration(draft.duration);
  const ps=document.getElementById('playback-status');if(ps)ps.textContent='Tap to preview';
  hideDraftBanner();
  pauseActiveVideoForRecording();
  setVoiceState('done');
  openSheet('voice-panel');
}
async function deleteDraftFromBanner(){
  await idbDeleteDraft();
  hideDraftBanner();
  toast('Draft deleted');
}
async function sendDraftFromBanner(){
  const draft=await idbGetDraft();
  if(!draft){hideDraftBanner();return;}
  hideDraftBanner();
  toast('Sending voice reply…');
  const mimeType=draft.mimeType||'audio/webm';
  const ext=mimeType.includes('mp4')?'mp4':mimeType.includes('ogg')?'ogg':'webm';
  const fd=new FormData();fd.append('audio',draft.blob,'voice_reply.'+ext);fd.append('video_id',draft.videoId);fd.append('duration',draft.duration||0);fd.append('language_code','en');
  try{
    const r=await fetch('/voice/reply',{method:'POST',body:fd,credentials:'same-origin'});
    if(r.ok){await idbDeleteDraft();toast('Voice reply sent!');}
    else{toast('Could not send — try again');showDraftBanner();}
  }catch(e){toast('Network error');showDraftBanner();}
}

// ── PANEL OPEN / STATE ──
function openVoicePanel(){
  document.getElementById('comments-sheet')?.classList.remove('open');
  S.openSheet=null;
  setTimeout(()=>openVoicePanelForVideo(S.commentVideoId),300);
}
async function openVoicePanelForVideo(id,btn){
  if(!ME){openAuthModal();return;}
  btnFeedback(btn?.querySelector('.abtn-icon'),'tap-pop');
  const busy=hasUnsavedRecording();
  if(busy&&S.commentVideoId!==id){
    S.pendingSwitchVideoId=id;
    if(S.voiceState==='recording')pauseRecording();
    S.preConfirmState=S.voiceState;
    openSheet('voice-panel');
    setVoiceState('switch-confirm');
    return;
  }
  if(busy&&S.commentVideoId===id){
    openSheet('voice-panel');
    return;
  }
  // V1: only one draft at a time — a persisted draft (even from a previous session) blocks starting a new recording
  const draft=await idbGetDraft();
  if(draft&&draft.videoId===id){
    await resumeDraftFromBanner();
    return;
  }
  if(draft){
    S.pendingSwitchVideoId=id;
    const dcTitle=document.getElementById('dc-video-title');
    if(dcTitle)dcTitle.textContent='Video: '+(_pvgCache[draft.videoId]?.title||'Untitled');
    const dcDur=document.getElementById('dc-duration');
    if(dcDur)dcDur.textContent=fmtDuration(draft.duration);
    openSheet('voice-panel');
    setVoiceState('draft-conflict');
    return;
  }
  hideDraftBanner();
  S.commentVideoId=id;
  resetRecordingInMemoryOnly();
  pauseActiveVideoForRecording();
  setVoiceState('idle');
  openSheet('voice-panel');
  startRecording();
}

async function resumeFromDraftConflict(){
  S.pendingSwitchVideoId=null;
  await resumeDraftFromBanner();
}

async function discardDraftAndStartNew(){
  const id=S.pendingSwitchVideoId;S.pendingSwitchVideoId=null;
  if(id==null)return;
  await idbDeleteDraft();
  hideDraftBanner();
  S.commentVideoId=id;
  resetRecordingInMemoryOnly();
  pauseActiveVideoForRecording();
  setVoiceState('idle');
  startRecording();
}

function setVoiceState(state){
  S.voiceState=state;
  const el=document.getElementById('vpbody');
  if(el)el.dataset.state=state;
  updateStatusBadge(state);
}

function hasUnsavedRecording(){
  return S.voiceState==='recording'||S.voiceState==='paused'||S.voiceState==='send-failed'||(S.voiceState==='done'&&S.recordedChunks.length>0);
}

function resetRecordingInMemoryOnly(){
  if(S.mediaRecorder&&typeof S.mediaRecorder.state==='string'&&S.mediaRecorder.state!=='inactive'){try{S.mediaRecorder.stop();}catch(e){}}
  stopAutosave();clearInterval(S.recordTimer);
  S.recording=false;S.recordedChunks=[];S.recordSeconds=0;S.mediaRecorder=null;S.mediaStream=null;S.draftMimeType=null;
  if(S.playbackAudio){S.playbackAudio.pause();S.playbackAudio=null;}
  S.playbackPlaying=false;
  const t=document.getElementById('record-timer');if(t)t.textContent='00:00';
  const pt=document.getElementById('paused-timer');if(pt)pt.textContent='00:00';
  const st=document.getElementById('idle-status');if(st)st.textContent='Preparing microphone…';
}

function discardRecordingNow(){
  resetRecordingInMemoryOnly();
  closeSheet('voice-panel');
  resumeActiveVideoAfterRecording();
  idbDeleteDraft();
  hideDraftBanner();
}

function cancelRecording(){
  if(S.voiceState==='sending')return;
  if(S.voiceState==='draft-conflict'){
    S.pendingSwitchVideoId=null;
    setVoiceState('idle');
    closeSheet('voice-panel');
    return;
  }
  if(hasUnsavedRecording()){
    if(S.voiceState==='recording')pauseRecording();
    S.preConfirmState=S.voiceState;
    setVoiceState('discard-confirm');
    return;
  }
  discardRecordingNow();
}

function resumeFromConfirm(){
  if(S.preConfirmState==='recording'){
    setVoiceState('paused');
    resumeRecording();
  } else {
    setVoiceState(S.preConfirmState||'idle');
  }
}

function saveDraftAndCloseFromConfirm(){
  const wasRecordingLike=S.preConfirmState==='recording'||S.preConfirmState==='paused';
  if(wasRecordingLike&&S.mediaRecorder&&S.mediaRecorder.state!=='inactive'){
    S.stopIntent='saveDraft';
    try{S.mediaRecorder.stop();}catch(e){}
  } else {
    persistCurrentAsDraft().then(finishCloseAfterDraftSave);
  }
}

function finishCloseAfterDraftSave(){
  resetRecordingInMemoryOnly();
  closeSheet('voice-panel');
  resumeActiveVideoAfterRecording();
  toast('Saved as draft');
  showDraftBanner();
}

async function proceedToPendingSwitch(){
  resetRecordingInMemoryOnly();
  const id=S.pendingSwitchVideoId;S.pendingSwitchVideoId=null;
  if(id==null)return;
  S.commentVideoId=id;
  setVoiceState('idle');
  pauseActiveVideoForRecording();
  startRecording();
}

function resumeFromSwitchConfirm(){
  S.pendingSwitchVideoId=null;
  if(S.preConfirmState==='recording'){
    setVoiceState('paused');
    resumeRecording();
  } else {
    setVoiceState(S.preConfirmState||'done');
  }
}

function saveDraftAndSwitch(){
  const wasRecordingLike=S.voiceState==='switch-confirm'&&(S.preConfirmState==='recording'||S.preConfirmState==='paused');
  if(wasRecordingLike&&S.mediaRecorder&&S.mediaRecorder.state!=='inactive'){
    S.stopIntent='saveDraftThenSwitch';
    try{S.mediaRecorder.stop();}catch(e){}
  } else {
    persistCurrentAsDraft().then(()=>{showDraftBanner();proceedToPendingSwitch();});
  }
}

function discardAndSwitch(){
  if(S.mediaRecorder&&S.mediaRecorder.state!=='inactive'){
    S.stopIntent='discardThenSwitch';
    try{S.mediaRecorder.stop();}catch(e){}
  } else {
    idbDeleteDraft();hideDraftBanner();
    proceedToPendingSwitch();
  }
}

// ── RECORDING ──
async function startRecording(){
  const st=document.getElementById('idle-status');if(st)st.textContent='Preparing microphone…';
  if(!navigator.mediaDevices?.getUserMedia){
    const msg='Voice recording requires a secure connection (HTTPS)';
    toast(msg);if(st)st.textContent=msg;
    setVoiceState('idle');resumeActiveVideoAfterRecording();return;
  }
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    S.mediaStream=stream;
    S.mediaRecorder=new MediaRecorder(stream);S.recordedChunks=[];
    S.mediaRecorder.ondataavailable=e=>{if(e.data.size)S.recordedChunks.push(e.data);};
    S.mediaRecorder.onstop=async()=>{
      stream.getTracks().forEach(t=>t.stop());
      S.mediaStream=null;
      const blob=S.recordedChunks.length?new Blob(S.recordedChunks,{type:S.mediaRecorder.mimeType||'audio/webm'}):null;
      if(blob){
        if(S.playbackAudio)S.playbackAudio.pause();
        S.playbackAudio=new Audio(URL.createObjectURL(blob));
        S.playbackPlaying=false;
        S.playbackAudio.onended=()=>{
          S.playbackPlaying=false;
          document.getElementById('playback-ring')?.classList.remove('playing');
          const ps=document.getElementById('playback-status');if(ps)ps.textContent='Tap to preview';
          const pi=document.getElementById('pb-icon');if(pi)pi.innerHTML='<polygon points="5 3 19 12 5 21"/>';
        };
      }
      const intent=S.stopIntent;S.stopIntent='preview';
      if(intent==='saveDraft'){
        if(blob)await persistCurrentAsDraft();
        finishCloseAfterDraftSave();
      } else if(intent==='saveDraftThenSwitch'){
        if(blob)await persistCurrentAsDraft();
        showDraftBanner();
        proceedToPendingSwitch();
      } else if(intent==='discardThenSwitch'){
        await idbDeleteDraft();hideDraftBanner();
        proceedToPendingSwitch();
      } else if(intent==='sendImmediately'){
        sendVoiceReply();
      } else {
        const m=String(Math.floor(S.recordSeconds/60)).padStart(2,'0');
        const s=String(S.recordSeconds%60).padStart(2,'0');
        const dur=m+':'+s;
        const pd=document.getElementById('playback-duration');if(pd)pd.textContent=dur;
        const ps=document.getElementById('playback-status');if(ps)ps.textContent='Tap to preview';
        setVoiceState('done');
      }
    };
    S.mediaRecorder.start(100);S.recording=true;
    S.recordSeconds=0;
    const t=document.getElementById('record-timer');if(t)t.textContent='00:00';
    setVoiceState('recording');
    clearInterval(S.recordTimer);
    S.recordTimer=setInterval(()=>{
      S.recordSeconds++;
      const m=String(Math.floor(S.recordSeconds/60)).padStart(2,'0');
      const s=String(S.recordSeconds%60).padStart(2,'0');
      const t=document.getElementById('record-timer');if(t)t.textContent=m+':'+s;
      if(S.recordSeconds>=60)stopRecording();
    },1000);
    startAutosave();
  }catch(err){
    const msg=err.name==='NotAllowedError'?'Microphone access denied — enable it in browser settings':
              err.name==='NotFoundError'?'No microphone found on this device':
              'Could not start recording';
    toast(msg);
    const st2=document.getElementById('idle-status');if(st2)st2.textContent=msg;
    setVoiceState('idle');
    resumeActiveVideoAfterRecording();
  }
}

function stopRecording(){
  if(S.voiceState!=='recording')return;
  S.stopIntent='preview';
  S.recording=false;clearInterval(S.recordTimer);stopAutosave();
  try{S.mediaRecorder.stop();}catch(e){}
}

function pauseRecording(){
  if(S.voiceState!=='recording')return;
  clearInterval(S.recordTimer);stopAutosave();
  if(S.mediaRecorder&&typeof S.mediaRecorder.pause==='function'&&S.mediaRecorder.state==='recording'){
    try{S.mediaRecorder.pause();}catch(e){}
    const m=String(Math.floor(S.recordSeconds/60)).padStart(2,'0');
    const s=String(S.recordSeconds%60).padStart(2,'0');
    const pt=document.getElementById('paused-timer');if(pt)pt.textContent=m+':'+s;
    setVoiceState('paused');
    persistCurrentAsDraft();
  } else {
    S.stopIntent='preview';S.recording=false;
    try{S.mediaRecorder.stop();}catch(e){}
  }
}

function resumeRecording(){
  if(S.voiceState!=='paused')return;
  if(S.mediaRecorder&&S.mediaRecorder.state==='paused'){
    try{S.mediaRecorder.resume();}catch(e){}
  }
  S.recording=true;
  setVoiceState('recording');
  clearInterval(S.recordTimer);
  S.recordTimer=setInterval(()=>{
    S.recordSeconds++;
    const m=String(Math.floor(S.recordSeconds/60)).padStart(2,'0');
    const s=String(S.recordSeconds%60).padStart(2,'0');
    const t=document.getElementById('record-timer');if(t)t.textContent=m+':'+s;
    if(S.recordSeconds>=60)stopRecording();
  },1000);
  startAutosave();
}

function requestSend(){
  if(S.voiceState==='paused'||S.voiceState==='recording'){
    S.stopIntent='sendImmediately';
    clearInterval(S.recordTimer);stopAutosave();S.recording=false;
    setVoiceState('sending');
    try{S.mediaRecorder.stop();}catch(e){}
  } else if(S.voiceState==='done'){
    sendVoiceReply();
  }
}

function reRecord(){
  resetRecordingInMemoryOnly();
  idbDeleteDraft();hideDraftBanner();
  setVoiceState('idle');
  pauseActiveVideoForRecording();
  startRecording();
}

function togglePlayback(){
  if(!S.playbackAudio)return;
  const ring=document.getElementById('playback-ring');
  const status=document.getElementById('playback-status');
  const icon=document.getElementById('pb-icon');
  if(S.playbackPlaying){
    S.playbackAudio.pause();S.playbackPlaying=false;
    ring?.classList.remove('playing');
    if(status)status.textContent='Tap to preview';
    if(icon)icon.innerHTML='<polygon points="5 3 19 12 5 21"/>';
  } else {
    S.playbackAudio.currentTime=0;S.playbackAudio.play();S.playbackPlaying=true;
    ring?.classList.add('playing');
    if(status)status.textContent='▐▐  Playing…';
    if(icon)icon.innerHTML='<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
  }
}

function sendVoiceReply(){
  if(!S.recordedChunks.length||!S.commentVideoId)return;
  setVoiceState('sending');
  const fillEl=document.getElementById('upload-bar-fill');
  const pctEl=document.getElementById('upload-pct');
  if(fillEl)fillEl.style.width='0%';
  if(pctEl)pctEl.textContent='0%';
  const mimeType=(S.mediaRecorder&&S.mediaRecorder.mimeType)||S.draftMimeType||'audio/webm';
  const ext=mimeType.includes('mp4')?'mp4':mimeType.includes('ogg')?'ogg':'webm';
  const blob=new Blob(S.recordedChunks,{type:mimeType});
  const fd=new FormData();fd.append('audio',blob,'voice_reply.'+ext);fd.append('video_id',S.commentVideoId);fd.append('duration',S.recordSeconds);fd.append('language_code','en');
  const xhr=new XMLHttpRequest();
  xhr.open('POST','/voice/reply');
  xhr.withCredentials=true;
  xhr.upload.onprogress=e=>{
    if(!e.lengthComputable)return;
    const pct=Math.round((e.loaded/e.total)*100);
    if(fillEl)fillEl.style.width=pct+'%';
    if(pctEl)pctEl.textContent=pct+'%';
  };
  xhr.onload=async()=>{
    if(xhr.status>=200&&xhr.status<300){
      if(fillEl)fillEl.style.width='100%';
      if(pctEl)pctEl.textContent='100%';
      setVoiceState('sent');
      await idbDeleteDraft();hideDraftBanner();
      setTimeout(()=>{
        resetRecordingInMemoryOnly();
        closeSheet('voice-panel');
        resumeActiveVideoAfterRecording();
      },1000);
    } else {
      setVoiceState('send-failed');
    }
  };
  xhr.onerror=()=>{setVoiceState('send-failed');};
  xhr.send(fd);
}

function retrySend(){
  sendVoiceReply();
}

function saveDraftAndCloseFromFailed(){
  persistCurrentAsDraft().then(finishCloseAfterDraftSave);
}

// ── INTERRUPTION HANDLING ──
function initVoiceInterruptionHandlers(){
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden&&S.voiceState==='recording')pauseRecording();
  });
  window.addEventListener('pagehide',()=>{
    if(S.voiceState==='recording'||S.voiceState==='paused')persistCurrentAsDraft();
  });
  window.addEventListener('beforeunload',e=>{
    if(S.voiceState==='recording'||S.voiceState==='paused')persistCurrentAsDraft();
    if(hasUnsavedRecording()){e.preventDefault();e.returnValue='';return '';}
  });
  window.addEventListener('popstate',()=>{
    if(S.voiceState==='recording')pauseRecording();
  });
}

// ── UPLOAD ──
function initUploadInput(){
  document.getElementById('vid-file').addEventListener('change',function(){
    const file=this.files[0];if(!file)return;
    const url=URL.createObjectURL(file);
    document.getElementById('upload-preview').src=url;
    document.getElementById('upload-zone').classList.add('hidden');
    document.getElementById('upload-form').classList.remove('hidden');
  });
}

async function submitUpload(){
  const title=document.getElementById('up-title').value.trim();
  const file=document.getElementById('vid-file').files[0];
  if(!title){toast('Please add a title');return;}if(!file){toast('Please select a video');return;}
  const btn=document.getElementById('upload-submit');btn.disabled=true;btn.textContent='Uploading…';
  const fd=new FormData();fd.append('video',file);fd.append('title',title);fd.append('caption',document.getElementById('up-caption').value.trim());fd.append('topic',document.getElementById('up-topic').value);fd.append('region',document.getElementById('up-region').value);
  try{
    const r=await fetch('/upload',{method:'POST',body:fd,credentials:'same-origin'});
    if(r.ok||r.redirected){closeSheet('upload-modal');toast('Uploaded! Refreshing…');setTimeout(()=>location.reload(),1200);}
    else{toast('Upload failed');btn.disabled=false;btn.textContent='Post Video';}
  }catch(e){toast('Network error');btn.disabled=false;btn.textContent='Post Video';}
}

// ── DISCOVER ──
const TOPICS=['Sports','Music','Comedy','News','Politics','Education','Fashion','Food','Tech','Travel'];
function initDiscoverScreen(){
  const wrap=document.getElementById('topic-chips');
  TOPICS.forEach(t=>{const c=document.createElement('button');c.className='chip';c.textContent=t;c.onclick=()=>{document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));c.classList.add('active');searchVideos(t.toLowerCase());};wrap.appendChild(c);});
  let debounce;
  document.getElementById('search-input').addEventListener('input',function(){
    clearTimeout(debounce);debounce=setTimeout(()=>{this.value.trim()?searchVideos(this.value.trim()):showDefaultDiscover();},400);
  });
  renderDiscoverGrid();
}

let _gridVideos=[];
function renderDiscoverGrid(){
  const grid=document.getElementById('discover-grid');
  const videos=FEED.filter(i=>i.kind==='video').slice(0,18);
  videos.forEach(v=>_pvgCache[v.id]=v);
  _gridVideos=videos;
  grid.innerHTML=videos.map(v=>`<div class="dgrid-thumb" onclick="openVideoFeed(_gridVideos,${v.id})">${v.thumbnail_url?`<img src="${esc(v.thumbnail_url)}" loading="lazy" alt="">`:'<div class="dgrid-placeholder"></div>'}<span class="dgrid-views">▶ ${fmtNum(v.views)}</span></div>`).join('');
}

function showDefaultDiscover(){document.getElementById('search-results-sec').classList.add('hidden');document.getElementById('topic-section').classList.remove('hidden');}

async function searchVideos(q){
  document.getElementById('topic-section').classList.add('hidden');
  document.getElementById('search-results-sec').classList.remove('hidden');
  document.getElementById('search-results-title').textContent=`Results for "${q}"`;
  const el=document.getElementById('search-results');el.innerHTML='<div class="empty-msg">Searching…</div>';
  try{
    const r=await api('/api/discovery?q='+encodeURIComponent(q));const items=r.items||[];
    if(!items.length){el.innerHTML='<div class="empty-msg">No results found</div>';return;}
    _gridVideos=items.map(it=>Object.assign({},it,{id:it.id||it.video_id}));
    el.innerHTML=items.map(it=>`<div class="dres-item" onclick="openVideoFeed(_gridVideos,${it.id||it.video_id||0})">${it.thumbnail_url?`<div class="dres-thumb"><img src="${esc(it.thumbnail_url)}" loading="lazy" alt=""></div>`:'<div class="dres-thumb dres-thumb-empty"></div>'}<div><p class="dres-title">${esc(it.title||it.query||'')}</p><p class="dres-meta">${esc(it.creator||'')} · ${fmtNum(it.views||0)} views</p></div></div>`).join('');
  }catch(e){el.innerHTML='<div class="empty-msg">Search failed</div>';}
}

// ── NOTIFICATIONS ──
function initNotifScreen(){
  renderNotifs('all');
  document.querySelectorAll('.ntab').forEach(t=>t.addEventListener('click',()=>{document.querySelectorAll('.ntab').forEach(b=>b.classList.remove('active'));t.classList.add('active');renderNotifs(t.dataset.kind);}));
}

async function loadNotifs(){
  if(!ME)return;
  try{
    const r=await api('/api/notifications');
    NOTIFS=r.items||[];
    const activeKind=document.querySelector('.ntab.active')?.dataset.kind||'all';
    renderNotifs(activeKind);
    api('/api/notifications/read','POST')
      .then(()=>document.getElementById('notif-badge')?.classList.add('hidden'))
      .catch(()=>{});
  }catch(e){console.error('loadNotifs:',e);}
}

function renderNotifs(kind){
  const list=document.getElementById('notifs-list');
  const filtered=kind==='all'?NOTIFS:NOTIFS.filter(n=>n.kind===kind);
  if(!filtered.length){list.innerHTML='<div class="empty-msg"><div class="empty-msg-icon">🔔</div>No notifications here yet</div>';return;}
  const icons={video_like:'❤️',voice_reply_like:'❤️',text_comment:'💬',voice_reply:'🎤',follow:'👤',share:'↗️',mention:'@'};
  list.innerHTML=filtered.map(n=>{
    const actor=n.actor||'';
    const initials=actor?actor[0].toUpperCase():'';
    const thumb=n.thumbnail_url
      ?`<div class="ni-thumb"><img src="${esc(n.thumbnail_url)}" alt="" loading="lazy"></div>`
      :n.video_id?`<div class="ni-thumb" style="font-size:18px">🎬</div>`:'';
    const target=String(n.target_url||'').replace(/'/g,"\\'");
    return `<div class="notif-item${n.is_read===false?' unread':''}" onclick="onNotifTap(this,${n.id},'${target}',${n.video_id||'null'})" role="button" tabindex="0">
      <div class="nav2">${icons[n.kind]||'🔔'}</div>
      ${initials?`<div class="ni-av">${esc(initials)}</div>`:''}
      <div class="ni-body"><p class="ni-msg">${actor?`<strong>${esc(actor)}</strong> `:''}${esc(n.message||n.body||'')}</p><span class="ni-time">${timeAgo(n.created_at)}</span></div>
      ${thumb}
    </div>`;
  }).join('');
}

function onNotifTap(el,id,targetUrl,videoId){
  el.classList.remove('unread');
  api('/api/notifications/read','POST',{notification_ids:[id]}).catch(()=>{});
  if(videoId!=null){openVideoFeed([videoId],videoId);return;}
  if(targetUrl&&targetUrl!=='/notifications')location.href=targetUrl;
}

// ── PROFILE ──
function renderProfileScreen(){
  const el=document.getElementById('profile-content');
  if(!ME&&!PROF_USER){
    el.innerHTML=`<div class="signin-prompt"><div class="sp-icon">👤</div><h2 class="sp-title">Sign in to MV Pulse</h2><p class="sp-sub">Upload videos, voice reply, and follow creators.</p><button class="btn-signin" onclick="openAuthModal()">Sign In / Sign Up</button></div>`;return;
  }
  const username=ME?.username||PROF_USER||'User';
  const stats=PROF_STATS;
  el.innerHTML=`<div class="prof-cover"></div>
    <div class="prof-header">
      <div class="prof-toprow">
        <div class="prof-pic">${PROF_AVATAR?`<img src="${esc(PROF_AVATAR)}" alt="">`:fmtInit(username)}</div>
        <div><p class="prof-dname">${esc(username)}</p><p class="prof-handle">@${esc(username)}</p></div>
      </div>
      <div class="prof-stats">
        <div class="pstat"><span class="pstat-num">${fmtNum(stats.videos||0)}</span><span class="pstat-lbl">Videos</span></div>
        <div class="pstat"><span class="pstat-num">${fmtNum(stats.followers||0)}</span><span class="pstat-lbl">Followers</span></div>
        <div class="pstat"><span class="pstat-num">${fmtNum(stats.following||0)}</span><span class="pstat-lbl">Following</span></div>
        <div class="pstat"><span class="pstat-num">${fmtNum(stats.replies||0)}</span><span class="pstat-lbl">Voice</span></div>
      </div>
      <div class="prof-actions">
        ${PROF_IS_OWNER?`<button class="btn-follow ing" onclick="location.href='/profile/${esc(username)}'">Edit Profile</button>`:
          `<button class="btn-follow${IS_FOLLOWING?' ing':''}" id="pfb" onclick="toggleProfileFollow()">${IS_FOLLOWING?'Following':'Follow'}</button>`}
        <button class="btn-share-p" onclick="shareProfile()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg></button>
      </div>
    </div>
    <div class="prof-content-tabs">
      <button class="ptab active" data-ptab="videos"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1" fill="currentColor"/><rect x="14" y="3" width="7" height="7" rx="1" fill="currentColor"/><rect x="3" y="14" width="7" height="7" rx="1" fill="currentColor"/><rect x="14" y="14" width="7" height="7" rx="1" fill="currentColor"/></svg></button>
      <button class="ptab" data-ptab="liked"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg></button>
      <button class="ptab" data-ptab="saved"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg></button>
    </div>
    <div class="pvgrid" id="pvgrid"></div>`;

  renderPVGrid(PROF_VIDEOS);
  document.querySelectorAll('.ptab').forEach(t=>t.addEventListener('click',()=>{
    document.querySelectorAll('.ptab').forEach(b=>b.classList.remove('active'));t.classList.add('active');
    const tab=t.dataset.ptab;
    if(tab==='videos')renderPVGrid(PROF_VIDEOS);
    else if(tab==='liked')loadLiked();
    else if(tab==='saved')loadSaved();
  }));
}

function renderPVGrid(videos){
  const grid=document.getElementById('pvgrid');if(!grid)return;
  if(!videos.length){grid.innerHTML='<div class="empty-msg pvgrid-empty">No videos yet</div>';return;}
  videos.forEach(v=>_pvgCache[v.id]=v);
  _gridVideos=videos;
  grid.innerHTML=videos.map(v=>`<div class="pvthumb" onclick="openVideoFeed(_gridVideos,${v.id})">${v.thumbnail_url?`<img src="${esc(v.thumbnail_url)}" loading="lazy" alt="">`:`<div class="pvph">🎬</div>`}<span class="pvviews">▶ ${fmtNum(v.views)}</span></div>`).join('');
}

async function loadLiked(){
  const grid=document.getElementById('pvgrid');if(!grid)return;
  if(!ME){grid.innerHTML='<div class="empty-msg pvgrid-empty">Sign in to see liked videos</div>';return;}
  grid.innerHTML='<div class="empty-msg pvgrid-empty">Loading…</div>';
  try{const r=await api('/api/me/likes');renderPVGrid(r.items||[]);}catch(e){grid.innerHTML='<div class="empty-msg pvgrid-empty">Could not load</div>';}
}

async function loadSaved(){
  const grid=document.getElementById('pvgrid');if(!grid)return;
  if(!ME){grid.innerHTML='<div class="empty-msg pvgrid-empty">Sign in to see saved videos</div>';return;}
  grid.innerHTML='<div class="empty-msg pvgrid-empty">Loading…</div>';
  try{const r=await api('/api/me/saved/videos');renderPVGrid(r.items||[]);}catch(e){grid.innerHTML='<div class="empty-msg pvgrid-empty">Could not load</div>';}
}

async function toggleProfileFollow(){
  if(!ME){openAuthModal();return;}
  const btn=document.getElementById('pfb');if(!btn)return;
  const following=btn.classList.contains('ing');
  btn.textContent=following?'Follow':'Following';btn.classList.toggle('ing',!following);
  try{await api('/api/profile/'+PROF_USER+'/follow','POST');}
  catch(e){btn.textContent=following?'Following':'Follow';btn.classList.toggle('ing',following);}
}

function shareProfile(){
  const url=location.origin+'/profile/'+(PROF_USER||(ME?.username||''));
  if(navigator.share)navigator.share({title:'MV Pulse Profile',url}).catch(()=>{});
  else navigator.clipboard.writeText(url).then(()=>toast('Profile link copied!'));
}

// ── SHEETS ──
function openSheet(id){
  if(S.openSheet&&S.openSheet!==id)closeSheet(S.openSheet);
  document.getElementById(id)?.classList.add('open');
  document.getElementById('backdrop').classList.add('vis');
  S.openSheet=id;
}
function closeSheet(id){
  document.getElementById(id)?.classList.remove('open');
  document.getElementById('backdrop').classList.remove('vis');
  if(S.openSheet===id)S.openSheet=null;
  if(id==='comments-sheet'&&vrAudio){vrAudio.pause();vrAudio=null;if(vrActiveBtn){vrActiveBtn.innerHTML=VR_PLAY;vrActiveBtn=null;}}
}
function closeAllSheets(){
  if(document.getElementById('voice-panel')?.classList.contains('open')){cancelRecording();return;}
  document.querySelectorAll('.sheet.open').forEach(s=>s.classList.remove('open'));document.getElementById('backdrop').classList.remove('vis');S.openSheet=null;
}

function initSheetGestures(){
  document.querySelectorAll('.sheet').forEach(sheet=>{
    let startY=0,dragging=false;
    const h=sheet.querySelector('.shandle');if(!h)return;
    const trigger=sheet.querySelector('.sheader')||h;
    trigger.addEventListener('touchstart',e=>{startY=e.touches[0].clientY;dragging=true;sheet.style.transition='none';},{passive:true});
    trigger.addEventListener('touchmove',e=>{if(!dragging)return;const dy=e.touches[0].clientY-startY;if(dy>0)sheet.style.transform=`translateY(${dy}px)`;},{passive:true});
    trigger.addEventListener('touchend',e=>{const dy=e.changedTouches[0].clientY-startY;sheet.style.transition='';sheet.style.transform='';if(dy>80){if(sheet.id==='voice-panel')cancelRecording();else closeSheet(sheet.id);}dragging=false;},{passive:true});
  });
}

// ── SETTINGS / ACCESSIBILITY ──
function initTheme(){
  const theme=localStorage.getItem('mvp_theme')||'dark';
  const size=localStorage.getItem('mvp_size')||'normal';
  _setThemeClass(theme);_setSizeClass(size);
}

function applyTheme(theme){
  _setThemeClass(theme);
  localStorage.setItem('mvp_theme',theme);
  document.querySelectorAll('[data-theme]').forEach(c=>c.classList.toggle('active',c.dataset.theme===theme));
}

function applyTextSize(size){
  _setSizeClass(size);
  localStorage.setItem('mvp_size',size);
  document.querySelectorAll('[data-size]').forEach(c=>c.classList.toggle('active',c.dataset.size===size));
}

function _setThemeClass(theme){
  document.body.classList.remove('light','hi-contrast');
  if(theme==='light')document.body.classList.add('light');
  if(theme==='hi-contrast')document.body.classList.add('hi-contrast');
  document.querySelectorAll('[data-theme]').forEach(c=>c.classList.toggle('active',c.dataset.theme===theme));
}

function _setSizeClass(size){
  document.body.classList.remove('text-lg','text-xl');
  if(size==='large')document.body.classList.add('text-lg');
  if(size==='xlarge')document.body.classList.add('text-xl');
  document.querySelectorAll('[data-size]').forEach(c=>c.classList.toggle('active',c.dataset.size===size));
}

// ── AUTH ──
function openAuthModal(){
  if(window.CURRENT_USER)return;
  openSheet('auth-modal');
}

function initAuthTabs(){
  document.querySelectorAll('.atab').forEach(t=>t.addEventListener('click',()=>{
    document.querySelectorAll('.atab').forEach(b=>b.classList.remove('active'));t.classList.add('active');
    const form=t.dataset.aform;
    document.getElementById('login-form').classList.toggle('hidden',form!=='login');
    document.getElementById('signup-form').classList.toggle('hidden',form!=='signup');
  }));
  if(!window.CURRENT_USER&&window.AUTH_MESSAGE)setTimeout(()=>openSheet('auth-modal'),200);
}

// ── PWA INSTALL ──
(()=>{
  let _prompt=null;
  if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
  const bar=document.getElementById('install-bar');
  const btn=document.getElementById('pwa-install-btn');
  const ibTitle=document.getElementById('ib-title');
  const ibSub=document.getElementById('ib-sub');
  if(sessionStorage.getItem('mvp_no_install'))return;

  // iOS detection — Safari on iPhone/iPad cannot trigger beforeinstallprompt;
  // show instructions banner directing users to the native Share -> Add to Home Screen flow
  const isIos=/iPhone|iPad|iPod/i.test(navigator.userAgent)&&!('MSStream' in window);
  const isStandalone=window.navigator.standalone===true;
  if(isIos&&!isStandalone){
    if(ibTitle)ibTitle.textContent='Add to Home Screen';
    if(ibSub)ibSub.textContent='Tap the Share button then "Add to Home Screen"';
    if(btn)btn.hidden=true;
    if(bar)bar.removeAttribute('hidden');
  }

  // Android / desktop Chrome & Edge — standard install prompt
  window.addEventListener('beforeinstallprompt',e=>{
    e.preventDefault();_prompt=e;
    if(bar)bar.removeAttribute('hidden');
  });
  window.addEventListener('appinstalled',()=>{_prompt=null;bar?.setAttribute('hidden','');});
  btn?.addEventListener('click',async()=>{
    if(!_prompt)return;
    _prompt.prompt();
    await _prompt.userChoice.catch(()=>null);
    _prompt=null;bar?.setAttribute('hidden','');
  });
  window.dismissInstall=function(){
    bar?.setAttribute('hidden','');
    sessionStorage.setItem('mvp_no_install','1');
  };
})();
