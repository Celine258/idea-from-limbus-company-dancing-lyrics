/* The 3.1.41 adapter reads only the current playback and lyric fields. */
(function(root) {
    function findStore(element) {
        if (!element) return null;
        const key = Object.keys(element).find(k => k.startsWith('__reactInternalInstance') || k.startsWith('__reactFiber'));
        for (let fiber=element[key], i=0; fiber && i<50; fiber=fiber.return, i++) {
            const store=fiber.memoizedProps?.value?.store;
            if (typeof store?.getState === 'function' && typeof store?.subscribe === 'function') return store;
        }
        return null;
    }
    function parseYrc(raw, offsetMs=0) {
        if (typeof raw!=='string' || raw.length>262144 || !Number.isFinite(offsetMs)) return [];
        const rows=[];
        for (const line of raw.split(/\r?\n/)) {
            const prefix=line.trim().match(/^\[(\d+),(\d+)\]/);
            if(!prefix)continue;
            const body=line.trim().slice(prefix[0].length), tokens=[...body.matchAll(/\((\d+),(\d+),0\)/g)];
            if(!tokens.length || tokens.length>2048)continue;
            let text=body.slice(0,tokens[0].index), words=[];
            for(let i=0;i<tokens.length;i++){
                const token=tokens[i], part=body.slice(token.index+token[0].length,tokens[i+1]?.index??body.length);
                const start=Array.from(text).length;
                text+=part;
                const begin=Math.max(0,Number(token[1])-offsetMs),end=Math.max(0,Number(token[1])+Number(token[2])-offsetMs);
                if(part.trim()&&Number.isFinite(begin)&&end>begin&&end<=86400000)
                    words.push({start_ms:Math.round(begin),end_ms:Math.round(end),text_start:start,text_end:Array.from(text).length});
            }
            const leading=Array.from(text).length-Array.from(text.trimStart()).length, trimmed=text.trim();
            words=words.map(word=>({...word,text_start:Math.max(0,word.text_start-leading),
                text_end:Math.min(Array.from(trimmed).length,word.text_end-leading)})).filter(word=>word.text_end>word.text_start);
            rows.push({time_ms:Math.max(0,Number(prefix[1])-offsetMs),text:trimmed,words});
        }
        return rows;
    }
    function attachWordTimings(lines, raw, offsetMs=0) {
        const rows=parseYrc(raw,offsetMs), byText=new Map();
        for(const row of rows){const list=byText.get(row.text)||[];list.push(row);byText.set(row.text,list);}
        return lines.map(line=>{
            const candidates=(byText.get(line.text.trim())||[]).filter(row=>Math.abs(row.time_ms-line.time_ms)<=250)
                .sort((a,b)=>Math.abs(a.time_ms-line.time_ms)-Math.abs(b.time_ms-line.time_ms));
            if(!candidates.length || candidates[1]&&Math.abs(candidates[0].time_ms-line.time_ms)===Math.abs(candidates[1].time_ms-line.time_ms))return line;
            const row=candidates[0],leading=Array.from(line.text).length-Array.from(line.text.trimStart()).length;
            const words=row.words.map(word=>({...word,text_start:word.text_start+leading,text_end:word.text_end+leading}));
            return words.length?{...line,words}:line;
        });
    }
    function attachTranslations(lines, translations, offsetMs=0) {
        if(!Array.isArray(translations)||translations.length>5000)return lines;
        const rows=translations.filter(row=>Number.isFinite(row?.time)&&typeof row.lyric==='string'
            &&row.lyric.length<=4096&&/[\u3400-\u9fff\u{20000}-\u{3134f}]/u.test(row.lyric))
            .map(row=>({time_ms:Math.max(0,Math.round(row.time*1000-offsetMs)),text:row.lyric.trim()}));
        const sorted=rows.sort((a,b)=>a.time_ms-b.time_ms);
        let cursor=0;
        return lines.map(line=>{
            if(!line.text.trim())return line;
            while(cursor<sorted.length&&sorted[cursor].time_ms<line.time_ms-250)cursor++;
            const candidates=[];
            for(let i=cursor;i<sorted.length&&sorted[i].time_ms<=line.time_ms+250;i++)candidates.push(sorted[i]);
            candidates.sort((a,b)=>Math.abs(a.time_ms-line.time_ms)-Math.abs(b.time_ms-line.time_ms));
            if(!candidates.length||candidates[1]&&Math.abs(candidates[0].time_ms-line.time_ms)===Math.abs(candidates[1].time_ms-line.time_ms))return line;
            return {...line,translation:candidates[0].text};
        });
    }
    let lyricCache=null, lyricSong='', lyricResult=[], lyricFields=[];
    function lyricsFor(state, songId) {
        const lyric=state['async:lyric'];
        if (!lyric || String(lyric.resourceTrackId) !== songId || lyric.displayType !== 'default') return [];
        const fields=[lyric.lyricLines,lyric.yrcInfo?.yrc,lyric.offset,lyric.scrollable,lyric.tlyricLines];
        if(lyric===lyricCache&&songId===lyricSong&&fields.every((field,index)=>field===lyricFields[index]))return lyricResult;
        const lines=(lyric.lyricLines || []).filter(x => Number.isFinite(x.time) && typeof x.lyric === 'string')
            .map(x => ({time_ms: Math.round(Math.max(0,x.time*1000)), text:x.lyric}));
        const offset=lyric.scrollable&&Number.isFinite(lyric.offset)?Math.round(lyric.offset*1000):0;
        lyricResult=attachTranslations(attachWordTimings(lines,lyric.yrcInfo?.yrc,offset),lyric.tlyricLines,offset);
        lyricCache=lyric;lyricSong=songId;lyricFields=fields;
        return lyricResult;
    }
    function snapshot(state, position, enabled) {
        const p=state.playing;
        if (!p || !Number.isFinite(p.resourceDuration) || typeof p.resourceName !== 'string') throw new Error('网易云播放器接口已改变');
        const songId=String(p.resourceTrackId || '');
        return {protocol:1, client:'3.1.41', kind:'snapshot', enabled,
            song:{id:songId,title:p.resourceName,artist:(p.resourceArtists||[]).map(x=>x.name).filter(Boolean).join(' / ')},
            duration_ms:Math.round(Math.max(0,p.resourceDuration*1000)),
            position_ms:Math.round(Math.max(0,Number.isFinite(position)?position:0)),
            playing:p.playingState===2, lyrics:lyricsFor(state,songId)};
    }
    let runtime=null;
    function playbackStreams(host=root) {
        if (!runtime && typeof host.webpackJsonp?.push==='function') {
            const id='floating_lyrics_playback_runtime';
            host.webpackJsonp.push([[id],{[id]:(_module,_exports,require)=>{runtime=require;}},[[id]]]);
        }
        // Subscribe through the client's own command instance. A separate legacy
        // instance has its own callback map and can replace the client's native slot.
        return Object.values(runtime?.c||{}).map(module=>module.exports).find(exports=>
            typeof exports?.audioPlayerPlayProgress$?.subscribe==='function' &&
            typeof exports?.audioPlayerSeek$?.subscribe==='function') || null;
    }
    class PlaybackEvents {
        constructor(getStreams,getPlaying,onUpdate,onError=()=>{}) {
            this.getStreams=getStreams;this.getPlaying=getPlaying;this.onUpdate=onUpdate;this.onError=onError;
            this.bound=null;this.subscriptions=[];
        }
        attach() {
            if(!this.getPlaying()) return;
            const streams=this.getStreams();
            if(!streams || streams===this.bound) return;
            this.close();this.bound=streams;
            const guarded=handler=>args=>{try{handler(args);}catch(error){this.onError(error);}};
            try {
                this.subscriptions.push(streams.audioPlayerPlayProgress$.subscribe(guarded(([id,seconds])=>{
                    const playing=this.getPlaying();
                    // Native callbacks queued before pause can arrive after the pause state.
                    if(playing?.playId===id && playing.playingState===2 && Number.isFinite(seconds)) this.onUpdate(id,seconds*1000,false);
                }),this.onError));
                this.subscriptions.push(streams.audioPlayerSeek$.subscribe(guarded(([id,_seek,code,seconds])=>{
                    if(code===0 && this.getPlaying()?.playId===id && Number.isFinite(seconds)) this.onUpdate(id,seconds*1000,true);
                }),this.onError));
            } catch(error) {this.close();this.onError(error);}
        }
        close() {
            for(const subscription of this.subscriptions) subscription.unsubscribe();
            this.subscriptions=[];this.bound=null;
        }
    }
    const api={findStore,lyricsFor,snapshot,playbackStreams,PlaybackEvents,parseYrc,attachWordTimings,attachTranslations};
    if (typeof module!=='undefined' && module.exports) module.exports=api;
    else root.FloatingLyricsAdapter=api;
})(typeof window==='undefined' ? globalThis : window);
