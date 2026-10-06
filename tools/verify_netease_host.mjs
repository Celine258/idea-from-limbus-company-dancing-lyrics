// Real-client regression check. Start NetEase with --remote-debugging-port=9229.
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const output=resolve(process.argv[2]||'artifacts/netease-host-regression');
const pages=await(await fetch('http://127.0.0.1:9229/json/list')).json();
const page=pages.find(p=>p.url.startsWith('orpheus://orpheus/pub/app.html'));
if(!page)throw new Error('NetEase main page not found');
const socket=new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let nextId=0;
const pending=new Map();
socket.onmessage=event=>{
    const message=JSON.parse(event.data),request=pending.get(message.id);
    if(request){pending.delete(message.id);clearTimeout(request.timer);request.resolve(message);}
};
socket.onclose=()=>{for(const request of pending.values()){clearTimeout(request.timer);request.reject(new Error('Client closed'));}pending.clear();};
function call(method,params={}){
    return new Promise((resolve,reject)=>{
        const id=++nextId,timer=setTimeout(()=>{pending.delete(id);reject(new Error('Client check timed out'));},15000);
        pending.set(id,{resolve,reject,timer});
        socket.send(JSON.stringify({id,method,params}));
    });
}
function clientStep(operation,payload){
    const visible=selector=>[...document.querySelectorAll(selector)].find(e=>e.getBoundingClientRect().width>0);
    const store=typeof FloatingLyricsAdapter!=='undefined' ? FloatingLyricsAdapter.findStore(document.querySelector('[data-testid="tid_playbar_play_btn"]')) : null;
    if(operation==='ready')return !!(store&&visible('[data-testid="tid_playbar_play_btn"]')&&visible('.floating-lyrics-entry'));
    if(!store)throw new Error('Playback store not found');
    if(operation==='play'){
        const entry=visible('.floating-lyrics-entry');
        if(!entry)throw new Error('Plugin entry not found');
        if(!entry.textContent.includes('✓'))entry.click();
        if((store.getState().playing.playingState===2)!==payload)visible('[data-testid="tid_playbar_play_btn"]').click();
    } else if(operation==='seek'){
        store.dispatch({type:'playing/setPlayingPosition',payload:{duration:payload}});
    } else if(operation==='next'){
        const next=visible('[data-testid="tid_playbar_next_btn"]');
        if(!next)throw new Error('Next-song button not found');
        const previous=String(store.getState().playing.resourceTrackId);
        next.click();return previous;
    }
    const p=store.getState().playing;
    const range=document.querySelector('[aria-label="播放进度调节"] input[type="range"]');
    return {phase:payload,at:Date.now(),id:String(p.resourceTrackId),title:p.resourceName,
        type:p.resourceType,playing:p.playingState===2,position:range?Number(range.value):null,
        duration:p.resourceDuration,seekLoading:p.loadingSeekDuration,
        lyricSong:String(store.getState()['async:lyric']?.resourceTrackId||''),
        lyricCount:store.getState()['async:lyric']?.lyricLines?.length||0};
}
async function remote(operation,payload){
    const response=await call('Runtime.evaluate',{expression:`(${clientStep.toString()})(${JSON.stringify(operation)},${JSON.stringify(payload)})`,returnByValue:true});
    if(response.error||response.result?.exceptionDetails)throw new Error(JSON.stringify(response.error||response.result.exceptionDetails));
    return response.result.result.value;
}
async function exercise(){
    // Node drives the timing. A minimized CEF window throttles browser timers.
    const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    const last=items=>items[items.length-1];
    const timeline=[];
    const sample=async phase=>{
        const data=await remote('sample',phase);
        timeline.push(data);return data;
    };
    async function collect(phase,count=12){const samples=[];for(let i=0;i<count;i++){await delay(400);samples.push(await sample(phase));}return samples;}
    await remote('play',true);
    const playing=await collect('playing');
    await remote('play',false);await delay(700);
    const paused=await collect('paused',4);
    await remote('play',true);await delay(700);
    const duration=last(playing).duration;
    const seekTarget=Math.min(25,duration*.25);
    await remote('seek',seekTarget);
    const sought=await collect('seek',6);
    const songs=[];
    for(let i=0;i<3;i++){
        const previous=await remote('next',null);
        const samples=await collect('next-'+i,15);
        const selected=samples.filter(s=>s.id!==previous);
        const ids=[...new Set(selected.map(s=>s.id))];
        const active=selected.filter(s=>s.playing&&s.position!==null);
        songs.push({previous,ids,title:last(active)?.title,
            progresses:active.length>2&&last(active).position-active[0].position>.75,
            staysSelected:ids.length===1,
            lyricMatches:last(active)?.lyricSong===last(active)?.id});
    }
    const checks={hostProgressMoves:last(playing).position-playing[0].position>1,
        hostPauseFreezes:paused.every(s=>!s.playing)&&Math.max(...paused.map(s=>s.position))-Math.min(...paused.map(s=>s.position))<.05,
        hostSeekFinishes:last(sought).position>=seekTarget&&last(sought).position<seekTarget+5&&last(sought).seekLoading===0,
        threeNextCommandsStaySelected:songs.every(s=>s.staysSelected),
        threeNextSongsPlay:songs.every(s=>s.progresses),
        switchedLyricsBelongToSong:songs.every(s=>s.lyricMatches),
        multipleRealSongs:new Set(timeline.map(s=>s.id)).size>=3};
    return {passed:Object.values(checks).every(Boolean),checks,songs,timeline};
}
try {
    let ready=false;
    for(let i=0;i<40&&!ready;i++){
        ready=await remote('ready',null);
        if(!ready)await new Promise(resolve=>setTimeout(resolve,250));
    }
    if(!ready)throw new Error('NetEase playback page did not finish loading');
    const report=await exercise();
    await mkdir(output,{recursive:true});
    await writeFile(resolve(output,'host-report.json'),JSON.stringify(report,null,2));
    process.stdout.write(JSON.stringify({passed:report.passed,checks:report.checks,songs:report.songs,output},null,2)+'\n');
    if(!report.passed)process.exitCode=1;
} finally {socket.close();}
