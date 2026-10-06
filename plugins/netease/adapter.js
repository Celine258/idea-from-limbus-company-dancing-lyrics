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
    class PlaybackEvents {
        constructor(getNative,getPlaying,onUpdate) {
            this.getNative=getNative;this.getPlaying=getPlaying;this.onUpdate=onUpdate;this.bound=null;
        }
        attach() {
            // 3.1.41 replaces the early bridge while its React application starts.
            if(!this.getPlaying()) return;
            const native=this.getNative();
            if(!native || native===this.bound || typeof native.appendRegisterCall!=='function') return;
            this.bound=native;
            native.appendRegisterCall('PlayProgress','audioplayer',(id,seconds)=>{
                const playing=this.getPlaying();
                // Native callbacks queued before pause can arrive after the pause state.
                if(playing?.playId===id && playing.playingState===2 && Number.isFinite(seconds)) this.onUpdate(id,seconds*1000,false);
            });
            native.appendRegisterCall('Seek','audioplayer',(id,_seek,code,seconds)=>{
                if(code===0 && this.getPlaying()?.playId===id && Number.isFinite(seconds)) this.onUpdate(id,seconds*1000,true);
            });
        }
    }
    const api={findStore,lyricsFor,snapshot,PlaybackEvents};
    if (typeof module!=='undefined' && module.exports) module.exports=api;
    else root.FloatingLyricsAdapter=api;
})(typeof window==='undefined' ? globalThis : window);
