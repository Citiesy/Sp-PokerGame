let gid=null,myHand=[],sel=new Set(),curP=-1,free=false,busy=false;

const N=['你','电脑B','电脑C','电脑D'];
const SC={diamond:'var(--s-dia)',club:'var(--s-clb)',heart:'var(--s-hrt)',spade:'var(--s-spd)'};
const SS={
    diamond:'<svg viewBox="0 0 40 40"><polygon points="20,5 35,20 20,35 5,20" fill="var(--s-dia)"/></svg>',
    club:'<svg viewBox="0 0 40 40"><circle cx="20" cy="11" r="6.5" fill="var(--s-clb)"/><circle cx="12" cy="21" r="6.5" fill="var(--s-clb)"/><circle cx="28" cy="21" r="6.5" fill="var(--s-clb)"/><rect x="18" y="24" width="4" height="11" rx="1.5" fill="var(--s-clb)"/></svg>',
    heart:'<svg viewBox="0 0 40 40"><path d="M20 34C11 27 3 19 3 13A8.5 8.5 0 0 1 20 10 8.5 8.5 0 0 1 37 13C37 19 29 27 20 34Z" fill="var(--s-hrt)"/></svg>',
    spade:'<svg viewBox="0 0 40 40"><path d="M20 4C11 13 3 17 3 23A8.5 8.5 0 0 0 17 26L15 36H25L23 26A8.5 8.5 0 0 0 37 23C37 17 29 13 20 4Z" fill="var(--s-spd)"/></svg>'
};
const SN={diamond:'方块',club:'梅花',heart:'红心',spade:'黑桃'};
const TN={
    single:'单张',pair:'对子',triple:'三条',triple_two:'三带二',
    straight:'顺子',consecutive_pairs:'连对',bomb:'炸弹',
    airplane:'飞机',airplane_pure:'飞机'
};

const AI_STEP_DELAY=1000;
const AI_FINAL_DELAY=500;

const $=id=>document.getElementById(id);

/* ==== Theme ==== */
function detectTheme(){
    const s=localStorage.getItem('pk-theme');
    if(s) return s;
    return matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';
}
function applyTheme(t){
    document.documentElement.setAttribute('data-theme',t);
    localStorage.setItem('pk-theme',t);
    $('ico-sun').classList.toggle('hidden',t==='light');
    $('ico-moon').classList.toggle('hidden',t==='dark');
}
function toggleTheme(){
    const c=document.documentElement.getAttribute('data-theme')||'light';
    applyTheme(c==='dark'?'light':'dark');
}
applyTheme(detectTheme());
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',e=>{
    if(!localStorage.getItem('pk-theme')) applyTheme(e.matches?'dark':'light');
});

/* ==== AI msg ==== */
function aiMsg(a){
    const name=N[a.player];
    if(a.action==='pass') return name+' 不出';
    const ht=a.hand_type;
    if(!ht||ht==='single'){
        if(a.cards&&a.cards.length===1){
            return name+' 出了 '+SN[a.cards[0][0]]+a.cards[0][1];
        }
        return name+' 出牌';
    }
    const tn=TN[ht]||'出牌';
    if(ht==='bomb') return name+' 出了'+tn+' !';
    return name+' 出了'+tn;
}

/* ==== Game ==== */
function startGame(){
    $('overlay').classList.add('hidden');
    $('title-screen').classList.add('hidden');
    $('board').classList.remove('hidden');
    sel.clear();busy=false;
    for(let i=0;i<4;i++) $('zone-'+i).innerHTML='';
    msg('');

    fetch('/api/new_game',{method:'POST',headers:{'Content-Type':'application/json'}})
    .then(r=>r.json()).then(data=>{
        gid=data.game_id;
        sync(data,true);
        if(data.ai_actions&&data.ai_actions.length){
            busy=true;
            let d=600;
            data.ai_actions.forEach((a)=>{
                setTimeout(()=>{
                    showZone(a.player,a.cards,a.action==='pass');
                    msg(aiMsg(a));
                    if(a.other_counts){
                        for(let j=0;j<4;j++) $('cnt-'+j).textContent=a.other_counts[j];
                    }
                    for(let j=0;j<4;j++) $('seat-'+j).classList.toggle('on',j===a.player);
                },d);
                d+=AI_STEP_DELAY;
            });
            setTimeout(()=>{
                sync(data);
                msg('轮到你出牌');
                busy=false;
            },d+AI_FINAL_DELAY);
        }else{
            msg('你有方块3，请出牌');
        }
    });
}

function sync(s,deal){
    myHand=s.hand.map(c=>({s:c[0],r:c[1]}));
    curP=s.current_player;free=s.is_free;
    sel.clear();
    renderHand(deal);
    for(let i=0;i<4;i++) $('cnt-'+i).textContent=s.other_counts[i];
    $('turn-info').textContent='当前: '+N[curP];
    $('btn-play').disabled=curP!==0||s.winner!=null;
    $('btn-pass').disabled=curP!==0||s.winner!=null||free||s.first_turn;
    for(let i=0;i<4;i++){
        $('seat-'+i).classList.toggle('on',i===curP);
    }
}

/* ==== Card ==== */
function mkCard(suit,rank){
    const el=document.createElement('div');
    el.className='cd';
    const c=SC[suit];
    el.innerHTML=
        `<div class="inner-oval"></div>`+
        `<div class="rt" style="color:${c}">${rank}</div>`+
        `<div class="sm">${SS[suit]}</div>`+
        `<div class="rb" style="color:${c}">${rank}</div>`;
    return el;
}

function renderHand(deal){
    const box=$('hand');
    box.innerHTML='';
    myHand.forEach((c,i)=>{
        const el=mkCard(c.s,c.r);
        el.dataset.idx=i;
        if(deal){
            el.classList.add('deal');
            el.style.animationDelay=(i*40)+'ms';
        }
        el.addEventListener('click',()=>{if(!busy)toggle(i,el)});
        box.appendChild(el);
    });
}

function toggle(i,el){
    if(sel.has(i)){sel.delete(i);el.classList.remove('sel');}
    else{sel.add(i);el.classList.add('sel');}
}

function showZone(pid,cards,pass){
    const z=$('zone-'+pid);
    z.innerHTML='';
    if(pass){
        const b=document.createElement('div');
        b.className='bubble';b.textContent='不出';
        z.appendChild(b);
    } else if(cards&&cards.length){
        cards.forEach((c,i)=>{
            const el=mkCard(c[0],c[1]);
            el.style.animationDelay=(i*50)+'ms';
            z.appendChild(el);
        });
    }
}

function msg(t){
    const el=$('msg');el.textContent=t;
    clearTimeout(el._t);
    if(t)el._t=setTimeout(()=>{if(el.textContent===t)el.textContent=''},4500);
}

/* ==== Touch swipe ==== */
(function(){
    let drag=false,last=-1,touched=new Set();
    function idx(x,y){
        const el=document.elementFromPoint(x,y);
        if(!el)return-1;
        const cd=el.closest('#hand .cd');
        if(!cd||cd.dataset.idx==null)return-1;
        return+cd.dataset.idx;
    }
    function hl(i){
        const el=document.querySelector(`#hand .cd[data-idx="${i}"]`);
        if(el)el.classList.add('dh');
    }
    function start(e){
        const h=$('hand');
        if(!h||!h.contains(e.target)||busy)return;
        drag=true;touched.clear();last=-1;
        const p=e.touches?e.touches[0]:e;
        const i=idx(p.clientX,p.clientY);
        if(i>=0){last=i;touched.add(i);hl(i);}
    }
    function move(e){
        if(!drag)return;
        const p=e.touches?e.touches[0]:e;
        const i=idx(p.clientX,p.clientY);
        if(i>=0&&i!==last){last=i;touched.add(i);hl(i);}
        if(e.cancelable)e.preventDefault();
    }
    function end(){
        if(!drag)return;drag=false;
        document.querySelectorAll('#hand .cd.dh').forEach(e=>e.classList.remove('dh'));
        if(touched.size>=2){
            touched.forEach(i=>{
                const el=document.querySelector(`#hand .cd[data-idx="${i}"]`);
                if(el)toggle(i,el);
            });
        }
        touched.clear();
    }
    document.addEventListener('touchstart',start,{passive:true});
    document.addEventListener('touchmove',move,{passive:false});
    document.addEventListener('touchend',end);
    document.addEventListener('touchcancel',end);
    document.addEventListener('mousedown',e=>{if(e.button===0)start(e)});
    document.addEventListener('mousemove',move);
    document.addEventListener('mouseup',end);
})();

/* ==== Play / Pass ==== */
function playCards(){
    if(busy||!sel.size)return;busy=true;
    const cards=[...sel].map(i=>[myHand[i].s,myHand[i].r]);
    fetch('/api/play',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({game_id:gid,cards})})
    .then(r=>r.json()).then(handle).catch(()=>{busy=false});
}
function passTurn(){
    if(busy)return;busy=true;
    fetch('/api/pass_turn',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({game_id:gid})})
    .then(r=>r.json()).then(handle).catch(()=>{busy=false});
}

function handle(data){
    if(data.error){msg(data.error);busy=false;return}
    sel.clear();

    for(let i=0;i<4;i++) $('zone-'+i).innerHTML='';

    const pa=data.player_action;
    if(pa) showZone(0,pa.cards,pa.action==='pass');

    if(data.state){
        myHand=data.state.hand.map(c=>({s:c[0],r:c[1]}));
        renderHand(false);
        $('cnt-0').textContent=data.state.other_counts[0];
    }

    if(data.ai_actions&&data.ai_actions.length){
        let d=700;
        data.ai_actions.forEach((a)=>{
            setTimeout(()=>{
                showZone(a.player,a.cards,a.action==='pass');
                msg(aiMsg(a));
                if(a.other_counts){
                    for(let i=0;i<4;i++) $('cnt-'+i).textContent=a.other_counts[i];
                }
                for(let i=0;i<4;i++) $('seat-'+i).classList.toggle('on',i===a.player);
            },d);
            d+=AI_STEP_DELAY;
        });
        setTimeout(()=>done(data),d+AI_FINAL_DELAY);
    }else done(data);
}

function done(data){
    sync(data.state);
    if(data.winner!=null){
        setTimeout(()=>showResult(data.winner),1000);
    }
    busy=false;
}

function showResult(w){
    const t=$('m-txt'),ic=$('m-ico');
    if(w===0){
        t.textContent='恭喜你赢了!';t.className='cw';
        ic.innerHTML='<svg viewBox="0 0 80 80" width="64"><circle cx="40" cy="40" r="34" fill="#f5c542" stroke="#d4a520" stroke-width="2.5"/><circle cx="29" cy="34" r="3" fill="#6b4c00"/><circle cx="51" cy="34" r="3" fill="#6b4c00"/><path d="M26 48Q40 57 54 48" stroke="#6b4c00" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg>';
    }else{
        t.textContent=N[w]+' 赢了';t.className='cl';
        ic.innerHTML='<svg viewBox="0 0 80 80" width="64"><circle cx="40" cy="40" r="34" fill="#5a6678" stroke="#47525f" stroke-width="2.5"/><circle cx="29" cy="34" r="3" fill="#1e2530"/><circle cx="51" cy="34" r="3" fill="#1e2530"/><path d="M28 52Q40 45 52 52" stroke="#1e2530" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg>';
    }
    $('overlay').classList.remove('hidden');
}