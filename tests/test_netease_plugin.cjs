const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const adapter=require('../plugins/netease/adapter.js');
(async()=>{
    let loaded,observe,textWrites=0,launches=0;
    const entries=[],registered={},sent=[];
    const state={playing:{playId:'live',resourceTrackId:'42',resourceName:'原创测试',resourceDuration:60,
        resourceArtists:[],playingState:2},'async:lyric':{resourceTrackId:'42',displayType:'default',lyricLines:[{time:1,lyric:'原创歌词'}]}};
    const store={getState:()=>state,subscribe:()=>{},dispatch:()=>{}};
    const streams={audioPlayerPlayProgress$:{subscribe:callback=>{registered.PlayProgress=(...args)=>callback(args);return {unsubscribe:()=>{}};}},
        audioPlayerSeek$:{subscribe:callback=>{registered.Seek=(...args)=>callback(args);return {unsubscribe:()=>{}};}}};
    const player={'__reactInternalInstance$test':{memoizedProps:{value:{store}}}};
    const anchor={parentElement:{querySelector:()=>entries[0]},insertAdjacentElement:(_position,button)=>entries.push(button)};
    function element(){let text='';return {style:{},isConnected:true,title:'',insertAdjacentElement:(_position,button)=>entries.push(button),get textContent(){return text;},set textContent(value){textWrites++;text=value;}};}
    class Socket {
        static OPEN=1;
        constructor(){this.readyState=0;Socket.current=this;}
        send(text){sent.push(JSON.parse(text));}
        close(){this.readyState=3;}
    }
    const context={FloatingLyricsAdapter:{...adapter,playbackStreams:()=>streams},plugin:{pluginPath:'plugin',onLoad:fn=>loaded=fn,onConfig:()=>{}},
        betterncm:{ncm:{getNCMVersion:()=> '3.1.41'},fs:{readFileText:async()=>JSON.stringify({token:'a'.repeat(64),command:'test'})},app:{exec:async()=>{launches++;return true;}}},
        legacyNativeCmder:{appendRegisterCall:()=>{throw new Error('不得重注册网易云原生回调');}},
        document:{body:{},querySelector:()=>player,querySelectorAll:()=>[anchor],createElement:element},
        MutationObserver:class {constructor(callback){observe=callback;}observe(){}},
        localStorage:{getItem:()=>null,setItem:()=>{}},WebSocket:Socket,setInterval:()=>{},Date,console,Promise,
        addEventListener:()=>{}};
    context.window=context;
    vm.runInNewContext(fs.readFileSync(require.resolve('../plugins/netease/index.js'),'utf8'),context);
    await loaded();
    assert.equal(entries.length,2);
    const toggle=entries[0],settings=entries[1];
    assert.equal(settings.textContent,'设置');
    const writes=textWrites;
    for(let i=0;i<10;i++) observe();
    assert.equal(entries.length,2);
    assert.equal(textWrites,writes,'观察 DOM 时不能反复改写按钮，造成事件循环饥饿');
    Socket.current.readyState=1;Socket.current.onopen();
    registered.Seek('live','seek',0,12.5);
    assert.equal(sent.at(-1).position_ms,12500);
    assert.equal(sent.at(-1).seek,true);
    assert.equal('lyrics' in sent.at(-1),false,'暂停或跳转不能重新随机排布未变化的歌词');
    registered.PlayProgress('old-song',50);
    assert.equal(sent.at(-1).position_ms,12500);
    let prevented=0,stopped=0;
    toggle.oncontextmenu({preventDefault:()=>prevented++,stopPropagation:()=>stopped++});
    assert.equal(prevented,1);
    assert.equal(stopped,1);
    assert.equal(sent.at(-1).kind,'show');
    settings.onclick({stopPropagation:()=>stopped++});
    assert.equal(sent.at(-1).kind,'show');
    assert.equal(toggle.textContent,'都市回响 ✓','打开设置不能关闭歌词或修改播放状态');
    Socket.current.onmessage({data:JSON.stringify({kind:'shutdown'})});
    assert.equal(entries[0].textContent,'都市回响');
    Socket.current.readyState=3;
    settings.onclick({stopPropagation:()=>{}});
    await Promise.resolve();
    assert.equal(launches,1,'引擎退出后，设置入口应启动它');
    Socket.current.readyState=1;Socket.current.onopen();
    assert.equal(sent.at(-1).kind,'show','重新连接后必须补发设置请求');
    assert.equal(sent.filter(x=>x.kind==='snapshot').at(-1).enabled,false,'打开设置不应偷偷启用歌词');
    console.log('Plugin lifecycle, settings entries, reconnect, idempotent DOM, seek and shutdown passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
