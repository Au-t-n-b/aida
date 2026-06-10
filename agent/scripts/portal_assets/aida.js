/* ============================================================
   AIDA 门户 · 交互与动效
   路由 / 时间轴导航 / 滚动联动 / 进度 / 键盘 / 揭示 / 幕布
   ============================================================ */
(function(){
  'use strict';
  document.documentElement.classList.add('js');

  var NAVH = 64;
  var doors = Array.prototype.slice.call(document.querySelectorAll('[data-door]'));
  var roleTabs = Array.prototype.slice.call(document.querySelectorAll('.nav-role'));
  var STORE = 'aida-portal-done';
  var reduce = window.matchMedia('(prefers-reduced-motion:reduce)').matches;

  /* ---------- 持久化 ---------- */
  function load(){ try{ return JSON.parse(localStorage.getItem(STORE)) || {}; }catch(e){ return {}; } }
  function save(o){ try{ localStorage.setItem(STORE, JSON.stringify(o)); }catch(e){} }

  /* ---------- 构建侧栏时间轴（由步骤生成）---------- */
  function buildTimelines(){
    doors.forEach(function(d){
      if(d.id === 'home') return;
      var ol = d.querySelector('[data-tl]');
      if(!ol) return;
      var steps = Array.prototype.slice.call(d.querySelectorAll('.step'));
      ol.innerHTML = '';
      steps.forEach(function(step, i){
        var key = step.getAttribute('data-step');
        var titleEl = step.querySelector('.step-title');
        var raw = titleEl ? titleEl.textContent : ('步骤 ' + (i+1));
        // 去掉前导「N · 」编号，时间轴自带序号
        var name = raw.replace(/^\s*\d+\s*[·.]\s*/, '');
        var li = document.createElement('li');
        li.className = 'tl-node';
        li.setAttribute('data-jump', key);
        li.innerHTML = '<span class="tl-dot"><span class="num">' + (i+1) +
          '</span><svg class="i"><use href="#i-check"></use></svg></span>' +
          '<span class="tl-name"></span>';
        li.querySelector('.tl-name').textContent = name;
        li.addEventListener('click', function(){ jumpToStep(d, key); });
        ol.appendChild(li);
      });
    });
  }

  /* ---------- 进度刷新 ---------- */
  function refresh(){
    doors.forEach(function(d){
      if(d.id === 'home') return;
      var steps = Array.prototype.slice.call(d.querySelectorAll('.step'));
      var total = steps.length, done = 0;
      steps.forEach(function(s){ if(s.classList.contains('is-done')) done++; });
      var pctVal = total ? done/total : 0;
      var complete = total>0 && done===total;

      var ring = d.querySelector('.rail-ring');
      if(ring){
        var prog = ring.querySelector('.prog');
        if(prog){ var C = 126; prog.style.strokeDashoffset = (C - C*pctVal).toFixed(1); }
        ring.classList.toggle('complete', complete);
      }
      var mini = d.querySelector('.pct-mini');
      if(mini) mini.textContent = complete ? '✓' : Math.round(pctVal*100);
      var count = d.querySelector('.rail-count');
      if(count) count.innerHTML = done + ' <em>/ ' + total + '</em>';

      // 时间轴节点完成态
      var nodes = d.querySelectorAll('.tl-node');
      steps.forEach(function(s, i){
        if(nodes[i]) nodes[i].classList.toggle('done', s.classList.contains('is-done'));
      });
      // 完成庆祝条
      var clear = d.querySelector('.door-clear');
      if(clear) clear.classList.toggle('show', total>0 && done===total);

      // 首页角色卡进度文案
      var go = document.querySelector('.role-card[href="#'+d.id+'"] .role-go .txt');
      if(go) go.textContent = done>0 ? (done+'/'+total+' · 继续') : (total+' 步 · 进入');
    });
  }

  function applySaved(){
    var state = load();
    document.querySelectorAll('.step').forEach(function(step){
      var input = step.querySelector('.done input');
      if(input && state[step.getAttribute('data-step')]){ input.checked = true; step.classList.add('is-done'); }
    });
    refresh();
  }

  /* ---------- 滚动揭示 ---------- */
  function inView(el, ratio){
    var r = el.getBoundingClientRect();
    var h = window.innerHeight || document.documentElement.clientHeight;
    return r.top < h * (ratio || 0.92) && r.bottom > -40;
  }
  function checkReveals(){
    document.querySelectorAll('.reveal:not(.in)').forEach(function(el){
      var door = el.closest('[data-door]');
      if(door && !door.classList.contains('show')) return;
      if(inView(el)) el.classList.add('in');
    });
  }
  function armReveals(scope){
    try{
      scope.querySelectorAll('[data-stagger]').forEach(function(group){
        Array.prototype.slice.call(group.children).forEach(function(child, i){
          var target = child.classList.contains('reveal') ? child : child.querySelector('.reveal');
          if(target) target.style.setProperty('--i', Math.min(i, 8));
        });
      });
    }catch(e){}
    requestAnimationFrame(checkReveals);
    setTimeout(checkReveals, 90);
    setTimeout(checkReveals, 360);
  }

  function syncAfterLayoutChange(){
    var run = function(){
      checkReveals();
      updateActiveStep();
    };
    if(window.requestAnimationFrame) requestAnimationFrame(run);
    else run();
    setTimeout(run, 80);
    setTimeout(run, 260);
    setTimeout(run, 620);
  }

  /* ---------- 滚动联动：高亮当前步骤 + 时间轴 ---------- */
  function updateActiveStep(){
    if(current === 'home') return;
    var d = document.getElementById(current);
    if(!d) return;
    var steps = Array.prototype.slice.call(d.querySelectorAll('.step'));
    if(!steps.length) return;
    var nodes = d.querySelectorAll('.tl-node');
    var threshold = (window.innerHeight || 800) * 0.34;
    var activeIdx = 0;
    steps.forEach(function(s, i){
      if(s.getBoundingClientRect().top - threshold <= 0) activeIdx = i;
    });
    steps.forEach(function(s, i){ s.classList.toggle('is-active', i === activeIdx); });
    nodes.forEach(function(n, i){ n.classList.toggle('active', i === activeIdx); });
  }

  function scrollToStep(step){
    var y = window.scrollY + step.getBoundingClientRect().top - (NAVH + 16);
    window.scrollTo({ top: Math.max(0, y), behavior: reduce ? 'auto' : 'smooth' });
  }
  function jumpToStep(door, key){
    var step = door.querySelector('.step[data-step="'+key+'"]');
    if(!step) return;
    step.classList.add('open');
    scrollToStep(step);
  }

  /* ---------- 路由：门切换 ---------- */
  var curtain = document.querySelector('.curtain');
  var current = null;
  var homeStage = 'hero';
  var homeSnapInProgress = false;

  function showDoor(id){
    var found = false;
    doors.forEach(function(d){
      var on = d.id === id;
      if(on){
        d.classList.add('show'); d.classList.remove('enter');
        void d.offsetWidth;
        if(!reduce) d.classList.add('enter');
        found = true;
      } else { d.classList.remove('show','enter'); }
    });
    if(!found){ var home = document.getElementById('home'); if(home){ home.classList.add('show'); } id='home'; }
    roleTabs.forEach(function(t){ t.classList.toggle('active', t.dataset.role === id); });
    current = id;

    document.documentElement.style.scrollBehavior = 'auto';
    window.scrollTo(0,0);
    requestAnimationFrame(function(){ window.scrollTo(0,0); document.documentElement.style.scrollBehavior = ''; });

    if(id === 'home'){ setHomeStage('hero'); litHero(); }
    var active = document.getElementById(id) || document.getElementById('home');
    if(active) armReveals(active);
    try{ refresh(); }catch(e){}
    updateActiveStep();
  }

  function route(playCurtain){
    var id = (location.hash || '#home').slice(1);
    if(id === current){ return; }
    if(playCurtain && !reduce && curtain){
      curtain.classList.remove('play'); void curtain.offsetWidth; curtain.classList.add('play');
      setTimeout(function(){ showDoor(id); }, 380);
    } else { showDoor(id); }
  }
  window.addEventListener('hashchange', function(){ route(true); });

  /* ---------- Hero 标题逐行揭示 ---------- */
  function litHero(){
    var t = document.querySelector('.hero-title');
    if(t){ setTimeout(function(){ t.classList.add('lit'); }, 40); }
  }

  function setHomeStage(stage){
    if(homeStage === stage && document.documentElement.classList.contains('home-stage-' + stage)) return;
    homeStage = stage;
    var root = document.documentElement;
    root.classList.remove('home-stage-hero','home-stage-transitioning','home-stage-roles');
    root.classList.add('home-stage-' + stage);
    if(stage === 'hero' && heroInner && (window.scrollY || document.documentElement.scrollTop || 0) < 80){
      heroInner.style.opacity = '1';
      heroInner.style.transform = 'translateY(0px)';
    }
  }

  function playRoleCardPop(){
    if(reduce) return;
    var root = document.documentElement;
    root.classList.remove('home-cards-popping');
    void root.offsetWidth;
    root.classList.add('home-cards-popping');
    setTimeout(function(){ root.classList.remove('home-cards-popping'); }, 760);
  }

  function syncHomeStageFromScroll(st){
    if(current !== 'home' || reduce || homeSnapInProgress) return;
    var hero = document.querySelector('#home .hero');
    var boundary = hero ? Math.round(hero.offsetHeight) : window.innerHeight;
    if(st < 80) setHomeStage('hero');
    else if(st >= boundary - 120) setHomeStage('roles');
  }

  /* ---------- 首页轻滚分页：Hero ⇄ Roles ---------- */
  function installHomePageSnap(){
    var snapping = false;
    var lastSnap = 0;
    function homeRoleSection(){
      return document.querySelector('#home > .section:first-of-type');
    }
    function homeHero(){
      return document.querySelector('#home .hero');
    }
    function homePageBoundary(){
      var hero = homeHero();
      return hero ? Math.round(hero.offsetHeight) : window.innerHeight;
    }
    function snapTo(y, stageAfter){
      snapping = true;
      homeSnapInProgress = true;
      lastSnap = Date.now();
      var target = Math.max(0, y);
      if(!reduce) setHomeStage('transitioning');
      if(stageAfter === 'roles') playRoleCardPop();
      window.scrollTo({ top: target, behavior: reduce ? 'auto' : 'smooth' });
      setTimeout(function(){
        window.scrollTo({ top: target, behavior: 'auto' });
        snapping = false;
        homeSnapInProgress = false;
        setHomeStage(stageAfter || 'hero');
        syncAfterLayoutChange();
      }, reduce ? 80 : 360);
    }
    function snapToRoles(){
      snapTo(homePageBoundary(), 'roles');
    }
    function snapToHomeTop(){
      snapTo(0, 'hero');
    }
    function onHomeWheel(e){
      if(current !== 'home' || e.ctrlKey || e.metaKey) return;
      var dy = e.deltaY || 0;
      if(Math.abs(dy) < 12) return;
      var now = Date.now();
      if(snapping){ e.preventDefault(); return; }
      if(now - lastSnap < 520) return;
      var roles = homeRoleSection();
      if(!roles) return;
      var y = window.scrollY || document.documentElement.scrollTop || 0;
      var pageTop = homePageBoundary();
      if(dy > 0 && y < pageTop - 80){
        e.preventDefault();
        snapToRoles();
      } else if(dy < 0 && y > 80 && y <= pageTop + 220){
        e.preventDefault();
        snapToHomeTop();
      }
    }
    window.addEventListener('wheel', onHomeWheel, {passive:false});
  }

  /* ---------- Hero 视差 ---------- */
  var glow = document.querySelector('.hero-glow');
  var heroInner = document.querySelector('.hero-inner');
  if(!reduce){
    window.addEventListener('mousemove', function(e){
      if(current !== 'home' || !glow) return;
      var x = (e.clientX / window.innerWidth - .5);
      var y = (e.clientY / window.innerHeight - .5);
      glow.style.transform = 'translateX(-50%) translate('+(x*40)+'px,'+(y*30)+'px)';
    }, {passive:true});
  }

  /* ---------- 滚动进度线 + 联动 + 回顶 ---------- */
  var scrollbar = document.querySelector('.scrollbar');
  var totop = document.querySelector('.totop');
  var ticking = false;
  function onScroll(){
    if(ticking) return; ticking = true;
    var run = function(){
      var st = window.scrollY || document.documentElement.scrollTop;
      var h = document.documentElement.scrollHeight - window.innerHeight;
      var p = h>0 ? st/h : 0;
      if(scrollbar) scrollbar.style.width = (p*100)+'%';
      if(totop) totop.classList.toggle('show', st > 360);
      syncHomeStageFromScroll(st);
      checkReveals();
      updateActiveStep();
      if(current === 'home' && heroInner && !reduce && homeStage !== 'transitioning'){
        heroInner.style.transform = 'translateY('+(st*0.18)+'px)';
        heroInner.style.opacity = Math.max(0, 1 - st/620);
      }
      ticking = false;
    };
    if(window.requestAnimationFrame){ requestAnimationFrame(run); setTimeout(function(){ if(ticking) run(); }, 60); }
    else { run(); }
  }
  window.addEventListener('scroll', onScroll, {passive:true});

  /* ---------- 角色卡鼠标流光 ---------- */
  document.querySelectorAll('.role-card').forEach(function(card){
    card.addEventListener('mousemove', function(e){
      var r = card.getBoundingClientRect();
      card.style.setProperty('--mx', (e.clientX - r.left)+'px');
      card.style.setProperty('--my', (e.clientY - r.top)+'px');
    }, {passive:true});
  });

  /* ---------- 步骤交互 ---------- */
  window.toggleStep = function(head){ head.closest('.step').classList.toggle('open'); syncAfterLayoutChange(); };
  window.stepKey = function(e, head){
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); window.toggleStep(head); }
  };
  window.toggleDone = function(input){
    var step = input.closest('.step');
    var state = load(), key = step.getAttribute('data-step');
    if(input.checked){
      state[key] = 1; step.classList.add('is-done');
      // 标记完成 → 自动展开并滚到下一步（引导式流程）
      var next = step.nextElementSibling;
      while(next && !next.classList.contains('step')) next = next.nextElementSibling;
      if(next && !next.classList.contains('is-done')){
        next.classList.add('open');
        setTimeout(function(){ scrollToStep(next); syncAfterLayoutChange(); }, 80);
      }
    } else { delete state[key]; step.classList.remove('is-done'); }
    save(state); refresh(); syncAfterLayoutChange();
  };
  window.expandAll = function(btn){
    btn.closest('[data-door]').querySelectorAll('.step').forEach(function(s){ s.classList.add('open'); });
    syncAfterLayoutChange();
  };
  window.collapseAll = function(btn){
    btn.closest('[data-door]').querySelectorAll('.step').forEach(function(s){ s.classList.remove('open'); });
    syncAfterLayoutChange();
  };

  /* ---------- 键盘导航（门内）---------- */
  document.addEventListener('keydown', function(e){
    if(current === 'home') return;
    var tag = (e.target.tagName || '').toLowerCase();
    if(tag === 'input' || tag === 'textarea' || e.metaKey || e.ctrlKey || e.altKey) return;
    var d = document.getElementById(current); if(!d) return;
    var steps = Array.prototype.slice.call(d.querySelectorAll('.step'));
    if(!steps.length) return;
    var idx = 0;
    steps.forEach(function(s, i){ if(s.classList.contains('is-active')) idx = i; });
    var k = e.key.toLowerCase();
    if(k === 'j'){ e.preventDefault(); goStep(steps[Math.min(idx+1, steps.length-1)]); }
    else if(k === 'k'){ e.preventDefault(); goStep(steps[Math.max(idx-1, 0)]); }
    else if(k === 'x'){
      e.preventDefault();
      var cb = steps[idx].querySelector('.done input');
      if(cb){ cb.checked = !cb.checked; window.toggleDone(cb); }
    }
  });
  function goStep(step){ if(!step) return; step.classList.add('open'); scrollToStep(step); syncAfterLayoutChange(); }

  /* ---------- 复制 ---------- */
  window.copyBlock = function(btn){
    var pre = btn.closest('.block').querySelector('pre');
    if(!pre) return;
    var txt = pre.textContent;
    var ok = function(){
      var o = btn.textContent; btn.textContent = '已复制 ✓'; btn.classList.add('done-btn');
      setTimeout(function(){ btn.textContent = o; btn.classList.remove('done-btn'); }, 1400);
    };
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(txt).then(ok, function(){ fallback(txt); ok(); });
    } else { fallback(txt); ok(); }
  };
  function fallback(txt){
    var ta = document.createElement('textarea'); ta.value = txt;
    ta.style.position='fixed'; ta.style.opacity='0';
    document.body.appendChild(ta); ta.select();
    try{ document.execCommand('copy'); }catch(e){} document.body.removeChild(ta);
  }

  /* ---------- 回到顶部 ---------- */
  if(totop){ totop.addEventListener('click', function(){ window.scrollTo({top:0, behavior:'smooth'}); }); }

  /* ---------- 动效可用性探针 ---------- */
  function motionProbe(){
    if(reduce){ document.documentElement.classList.add('no-motion'); return; }
    var t = document.createElement('div');
    t.style.cssText = 'position:fixed;left:-9999px;top:0;width:2px;height:2px;opacity:0;transition:opacity .05s linear;pointer-events:none';
    document.body.appendChild(t);
    requestAnimationFrame(function(){ t.style.opacity = '1'; });
    setTimeout(function(){
      var ok = parseFloat(getComputedStyle(t).opacity) > 0.2;
      if(!ok) document.documentElement.classList.add('no-motion');
      if(t.parentNode) t.parentNode.removeChild(t);
    }, 240);
  }

  /* ---------- 初始化 ---------- */
  buildTimelines();
  applySaved();
  motionProbe();
  installHomePageSnap();
  showDoor((location.hash || '#home').slice(1));
  onScroll();
})();
