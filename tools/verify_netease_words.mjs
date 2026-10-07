// Development-only native-client regression. No new lyric service or callback hook.
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {regressionChecks,seekFinishes} from './word_regression_checks.mjs';
const directory=resolve(process.argv[2]||'artifacts/netease-word-regression');
const pages=await(await fetch('http://127.0.0.1:9229/json/list')).json();
const page=pages.find(p=>p.url.startsWith('orpheus://orpheus/pub/app.html'));
if(!page)throw new Error('NetEase main page not found');
const socket=new WebSocket(page.webSocketDebuggerUrl);
await new Promise((yes,no)=>{socket.onopen=yes;socket.onerror=no;});
let counter=0;const pending=new Map();
socket.onmessage=event=>{const data=JSON.parse(event.data),request=pending.get(data.id);if(request){pending.delete(data.id);clearTimeout(request.timer);request.resolve(data);}};
socket.onclose=()=>{for(const request of pending.values()){clearTimeout(request.timer);request.reject(new Error('Client closed'));}pending.clear();};
function request(expression){return new Promise((resolve,reject)=>{const id=++counter,timer=setTimeout(()=>{pending.delete(id);reject(new Error('Native client request timed out'));},20000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method:'Runtime.evaluate',params:{expression,awaitPromise:true,returnByValue:true}}));});}

async function clientStep(action,payload){
    const visible=s=>[...document.querySelectorAll(s)].find(e=>e.getBoundingClientRect().width>0);
    const store=typeof FloatingLyricsAdapter==='undefined'?null:FloatingLyricsAdapter.findStore(visible('[data-testid="tid_playbar_play_btn"]'));
    if(action==='ready')return !!(store&&visible('.floating-lyrics-entry'));
    if(!store)throw new Error('Playback store unavailable');
    if(action==='prepare'){
        let require;const id='floating_word_regression_runtime';webpackJsonp.push([[id],{[id]:(_m,_e,r)=>{require=r}},[[id]]]);
        const state=store.getState(),p=state.playing,cur=p.curPlaying;
        const range=document.querySelector('[aria-label="播放进度调节"] input[type="range"]');
        const original={tracks:state.playingList.curPlayingList.map(x=>x.track?.track||x.track||x),id:String(p.resourceTrackId),
            position:Number(range?.value||0),playing:p.playingState===2,
            from:{resourceType:cur.resourceType,scene:cur.scene,href:cur.href,text:cur.text,fromInfo:cur.fromInfo}};
        const ids=['2058124989','1811921555','1330348068','4875932'];
        const tracks=await require(15).ji({c:JSON.stringify(ids.map(id=>({id}))) });
        if(!Array.isArray(tracks))throw new Error('Song metadata shape changed');
        window._flWordCheck={original,tracks,require};
        const entry=visible('.floating-lyrics-entry');if(!entry.textContent.includes('✓'))entry.click();
        return tracks.map(t=>({id:String(t.id),title:t.name}));
    }
    if(action==='select'||action==='restore'){
        const check=window._flWordCheck;if(!check)throw new Error('Regression not prepared');
        const tracks=action==='restore'?check.original.tracks:check.tracks;
        const id=action==='restore'?check.original.id:payload;
        store.dispatch({type:'playing/play',payload:{tracks,from:check.original.from,
            options:{clear:true,play:true,playId:id},triggerScene:'click'}});
        return id;
    }
    if(action==='play'){
        if((store.getState().playing.playingState===2)!==payload)visible('[data-testid="tid_playbar_play_btn"]').click();
    }else if(action==='seek')store.dispatch({type:'playing/setPlayingPosition',payload:{duration:payload}});
    else if(action==='next'){
        const previous=String(store.getState().playing.resourceTrackId);visible('[data-testid="tid_playbar_next_btn"]').click();return previous;
    }else if(action==='original')return {id:window._flWordCheck.original.id,position:window._flWordCheck.original.position,playing:window._flWordCheck.original.playing};
    const state=store.getState(),p=state.playing,l=state['async:lyric'],id=String(p.resourceTrackId);
    const lines=FloatingLyricsAdapter.lyricsFor(state,id),words=lines.flatMap(line=>line.words||[]);
    const longest=words.filter(word=>word.end_ms-word.start_ms>=100).sort((a,b)=>(b.end_ms-b.start_ms)-(a.end_ms-a.start_ms))[0];
    const range=document.querySelector('[aria-label="播放进度调节"] input[type="range"]');
    return {id,title:p.resourceName,playing:p.playingState===2,position:Number(range?.value||0),seekLoading:p.loadingSeekDuration,
        lyricSong:String(l?.resourceTrackId||''),displayType:l?.displayType,lyricCount:lines.length,
        timedLines:lines.filter(line=>line.words?.length).length,wordCount:words.length,
        wordTarget:longest?(longest.start_ms+longest.end_ms)/2000:null};
}
async function remote(action,payload=null){
    const response=await request(`(${clientStep.toString()})(${JSON.stringify(action)},${JSON.stringify(payload)})`);
    if(response.error||response.result?.exceptionDetails)throw new Error(JSON.stringify(response.error||response.result.exceptionDetails));
    return response.result.result.value;
}
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)),samples=[],cases=[],nextSongs=[];
async function collect(phase,count=8){const result=[];for(let i=0;i<count;i++){await wait(250);const sample={phase,...await remote('sample')};samples.push(sample);result.push(sample);}return result;}
let prepared=false,restored=false,report;
try{
    let ready=false;for(let i=0;i<40&&!ready;i++){ready=await remote('ready');if(!ready)await wait(250);}
    if(!ready)throw new Error('Plugin entry not ready');
    const metadata=await remote('prepare');prepared=true;
    for(const [id,kind] of [['2058124989','english'],['1811921555','chinese'],['1330348068','sentence'],['4875932','instrumental']]){
        await remote('select',id);
        let selected;
        for(let i=0;i<60;i++){await wait(250);selected=await remote('sample');if(selected.id===id&&selected.lyricSong===id&&selected.playing&&selected.position>.25)break;}
        if(selected.id!==id||!selected.playing||selected.lyricSong!==id||selected.position<=.25)throw new Error('Selected song has not started audio: '+id);
        let active=await collect(kind+'-playing');
        if(kind==='english'||kind==='chinese'){
            const target=active.at(-1).wordTarget;
            if(target===null)throw new Error('No usable real word interval: '+id);
            await remote('play',false);await wait(500);await remote('seek',target);
            const paused=await collect(kind+'-word-paused',8);
            cases.push({kind,id,title:selected.title,timedLines:paused.at(-1).timedLines,wordCount:paused.at(-1).wordCount,
                target,freeze:paused.slice(-5).every(s=>!s.playing)&&Math.max(...paused.slice(-5).map(s=>s.position))-Math.min(...paused.slice(-5).map(s=>s.position))<.05,
                seekPosition:paused.at(-1).position,seekErrorSeconds:Math.abs(paused.at(-1).position-target),
                seekFinishes:seekFinishes(paused,target)});
            await remote('play',true);active=await collect(kind+'-resumed',6);
        }else cases.push({kind,id,title:selected.title,timedLines:selected.timedLines,displayType:selected.displayType,lyricCount:selected.lyricCount});
        cases.at(-1).progresses=active.at(-1).position-active[0].position>.6;
    }
    for(let index=0;index<3;index++){
        const previous=await remote('next'),history=await collect('next-'+index,12);
        const selected=history.filter(s=>s.id!==previous),ids=[...new Set(selected.map(s=>s.id))];
        nextSongs.push({ids,title:selected.at(-1)?.title,staysSelected:ids.length===1,progresses:selected.length>2&&selected.at(-1).position-selected[0].position>.6,
            lyricMatches:selected.at(-1)?.lyricSong===selected.at(-1)?.id});
    }
    const checks=regressionChecks(cases,nextSongs);
    report={passed:Object.values(checks).every(Boolean),checks,metadata,cases,nextSongs,samples,wordTimingSource:'native NetEase yrcInfo.yrc'};
}finally{
    if(prepared){
        try{const original=await remote('original');await remote('restore');await wait(1800);await remote('seek',original.position);await wait(500);await remote('play',original.playing);restored=(await remote('sample')).id===original.id;}
        catch(error){if(report)report.restoreError=String(error);}
    }
    if(report){report.originalPlaylistRestored=restored;report.passed&&=restored;await mkdir(directory,{recursive:true});await writeFile(resolve(directory,'word-host-report.json'),JSON.stringify(report,null,2));}
    socket.close();
}
console.log(JSON.stringify({passed:report.passed,checks:report.checks,cases:report.cases,originalPlaylistRestored:restored},null,2));
if(!report.passed)process.exitCode=1;
