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
    function lyricsFor(state, songId) {
        const lyric=state['async:lyric'];
        if (!lyric || String(lyric.resourceTrackId) !== songId || lyric.displayType !== 'default') return [];
        return (lyric.lyricLines || []).filter(x => Number.isFinite(x.time) && typeof x.lyric === 'string')
            .map(x => ({time_ms: Math.round(Math.max(0,x.time*1000)), text:x.lyric}));
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
    const api={findStore,lyricsFor,snapshot,playbackStreams,PlaybackEvents};
    if (typeof module!=='undefined' && module.exports) module.exports=api;
    else root.FloatingLyricsAdapter=api;
})(typeof window==='undefined' ? globalThis : window);
