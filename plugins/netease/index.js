(() => {
    let socket=null, store=null, config=null, position=0, playId='', lastSent=0, lastLyrics='', lastSong='', fetchSong='', lastState='';
    let enabled=localStorage.getItem('floatingLyrics.enabled') !== 'false';
    let status='正在连接桌面歌词…', launching=false, nextLaunch=0, pendingShow=false;
    const buttons=new Set();
    function updateStatus(value) {
        status=value;
        for(const item of buttons) {
            if(item.title!==status) item.title=status;
            const text=enabled?'跳动的词 ✓':'跳动的词';
            if(item.textContent!==text) item.textContent=text;
        }
    }
    function reportError(error) {updateStatus(error.message || String(error)); console.warn('[FloatingLyrics]',status);}
    function send(force=false, seek=false) {
        if (!store || socket?.readyState !== WebSocket.OPEN) return;
        const now=Date.now();
        if (!force && now-lastSent<100) return;
        try {
            const state=store.getState(), p=state.playing;
            if (!p) return;
            if (p.playId !== playId) {playId=p.playId; position=0;}
            const data=FloatingLyricsAdapter.snapshot(state,position,enabled);
            const transportState=JSON.stringify([data.song.id,data.playing,data.enabled,data.duration_ms]);
            lastState=transportState;
            const key=data.song.id, lyrics=JSON.stringify(data.lyrics);
            if (key===lastSong && lyrics===lastLyrics) delete data.lyrics;
            else {lastLyrics=lyrics;lastSong=key;}
            data.token=config.token;
            data.seek=seek;
            socket.send(JSON.stringify(data));
            lastSent=now;
            updateStatus(enabled?'已连接 · 右键打开歌词设置':'歌词效果已关闭 · 点击开启');
            if (enabled && key && key!==fetchSong) {
                fetchSong=key;
                store.dispatch({type:'async:lyric/fetchLyric',payload:{force:true}});
            }
        } catch(error) {reportError(error);}
    }
    async function launch() {
        if (launching || Date.now()<nextLaunch) return;
        launching=true;nextLaunch=Date.now()+30000;
        try {if (!await betterncm.app.exec(config.command, false, false)) throw new Error('桌面歌词启动失败，请检查插件安装位置');}
        catch(error) {reportError(error);}
        finally {launching=false;}
    }
    function connect() {
        if (!config || socket && socket.readyState<2) return;
        socket=new WebSocket('ws://127.0.0.1:38473');
        socket.onopen=()=>{
            lastLyrics='';lastSong='';send(true);
            if(pendingShow){pendingShow=false;socket.send(JSON.stringify({kind:'show',token:config.token}));}
        };
        socket.onmessage=event=>{
            try {if(JSON.parse(event.data).kind==='shutdown'){enabled=false;localStorage.setItem('floatingLyrics.enabled','false');updateStatus('已退出 · 点击启用');}} catch (_) {}
        };
        socket.onclose=()=>{socket=null;updateStatus('桌面歌词未连接 · 点击重试');};
        socket.onerror=()=>{if(enabled||pendingShow) launch();};
    }
    function showSettings() {
        if(socket?.readyState===WebSocket.OPEN) socket.send(JSON.stringify({kind:'show',token:config.token}));
        else {pendingShow=true;launch();connect();}
    }
    function installButtons() {
        for (const anchor of document.querySelectorAll('[data-testid="tid_playbar_lyric_btn"]')) {
            if(anchor.parentElement.querySelector('.floating-lyrics-entry')) continue;
            const button=document.createElement('button');
            button.className='floating-lyrics-entry';
            button.style.cssText='border:0;border-radius:8px;padding:6px 9px;margin:0 4px;background:#ff3656;color:white;font-size:12px;cursor:pointer;white-space:nowrap';
            button.onclick=()=>{enabled=!enabled;localStorage.setItem('floatingLyrics.enabled',String(enabled));if(enabled){nextLaunch=0;connect();}send(true);updateStatus(status);};
            button.oncontextmenu=event=>{event.preventDefault();showSettings();};
            anchor.insertAdjacentElement('afterend',button);buttons.add(button);
        }
        for(const button of buttons) if(!button.isConnected) buttons.delete(button);
        updateStatus(status);
    }
    plugin.onLoad(async () => {
        try {
            if(betterncm.ncm.getNCMVersion()!=='3.1.41') throw new Error('跳动的歌词目前适配网易云 3.1.41');
            config=JSON.parse(await betterncm.fs.readFileText(plugin.pluginPath+'/bridge-config.json'));
            const events=new FloatingLyricsAdapter.PlaybackEvents(()=>window.legacyNativeCmder,
                ()=>store?.getState().playing,(id,milliseconds,seek)=>{
                    playId=id;position=milliseconds;send(seek,seek);
                });
            const attach=()=>{
                if(!store) {
                    store=FloatingLyricsAdapter.findStore(document.querySelector('[data-testid="tid_playbar_play_btn"]'));
                    if(store) store.subscribe(()=>{
                        const p=store.getState().playing;
                        const current=JSON.stringify([String(p.resourceTrackId||''),p.playingState===2,enabled,Math.round(p.resourceDuration*1000)]);
                        send(current!==lastState);
                    });
                }
                events.attach();
            };
            // Both layouts remain mounted in 3.1.41; add entries to each one.
            const observer=new MutationObserver(()=>{attach();installButtons();});
            observer.observe(document.body,{childList:true,subtree:true});
            attach();installButtons();connect();
            setInterval(()=>{attach();installButtons();if(enabled||pendingShow)connect();send();},1000);
            window.addEventListener('beforeunload',()=>socket?.close());
        } catch(error) {reportError(error);}
    });
    plugin.onConfig(()=>{
        const section=document.createElement('div');
        section.style.cssText='padding:20px;line-height:1.8';
        const title=document.createElement('h2');title.textContent='跳动的歌词';section.append(title);
        const info=document.createElement('p');info.textContent='音乐由网易云播放。播放栏点击“跳动的词”开关效果，右键打开设置。';section.append(info);
        const note=document.createElement('p');note.textContent=status;section.append(note);
        const button=document.createElement('button');button.textContent='打开歌词效果设置';button.onclick=showSettings;section.append(button);
        return section;
    });
})();
