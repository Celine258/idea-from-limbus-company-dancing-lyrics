const assert = require('node:assert/strict');
const adapter = require('../plugins/netease/adapter.js');
const state = {playing:{resourceTrackId:'42',resourceName:'测试歌曲',resourceDuration:120,
    resourceArtists:[{name:'测试歌手'}],playingState:2},
    'async:lyric':{resourceTrackId:'42',displayType:'default',offset:.5,
        lyricLines:[{time:1.5,lyric:'已含客户端偏移的测试歌词'}, {time:30,lyric:''}]}};
const data = adapter.snapshot(state,1250,true);
assert.equal(data.position_ms,1250);
assert.equal(data.duration_ms,120000);
assert.equal(data.playing,true);
assert.equal(data.lyrics[0].time_ms,1500); // Do not apply NetEase's offset twice.
assert.equal(data.lyrics[1].text,'');
assert.equal(data.song.artist,'测试歌手');
assert.equal(adapter.snapshot({...state,playing:{...state.playing,playingState:1}},1500,true).playing,false);
assert.deepEqual(adapter.lyricsFor(state,'another song'),[]);
assert.deepEqual(adapter.lyricsFor({...state,'async:lyric':{...state['async:lyric'],displayType:'noLyric'}},'42'),[]);
assert.equal(adapter.findStore(null),null);
const store={getState:()=>state,subscribe:()=>{}};
const element={'__reactInternalInstance$test':{memoizedProps:{},return:{memoizedProps:{value:{store}}}}};
assert.equal(adapter.findStore(element),store);
assert.throws(()=>adapter.snapshot({playing:{}},0,true),/接口/);
let streams=null,playing=null;
const callbacks={},updates=[];
const reader=new adapter.PlaybackEvents(()=>streams,()=>playing,(...args)=>updates.push(args));
reader.attach();
streams={audioPlayerPlayProgress$:{subscribe:callback=>{callbacks.PlayProgress=(...args)=>callback(args);return {unsubscribe:()=>{}};}},
    audioPlayerSeek$:{subscribe:callback=>{callbacks.Seek=(...args)=>callback(args);return {unsubscribe:()=>{}};}}};
playing={playId:'current',playingState:2};
reader.attach();
callbacks.PlayProgress('stale',10);
assert.equal(updates.length,0);
callbacks.PlayProgress('current',12.5);
assert.deepEqual(updates.pop(),['current',12500,false]);
callbacks.Seek('current','seek',0,3.25);
assert.deepEqual(updates.pop(),['current',3250,true]);
callbacks.Seek('current','seek',-1,50);
assert.equal(updates.length,0);
playing.playingState=1;
callbacks.PlayProgress('current',13);
assert.equal(updates.length,0,'暂停后迟到的进度回调不能移动歌词');
callbacks.Seek('current','paused-seek',0,5);
assert.deepEqual(updates.pop(),['current',5000,true]);
console.log('NetEase 3.1.41 adapter contract passed');

const yrc='[2000,1000](2000,300,0)你(2300,300,0)好吗\n[4000,900](4000,400,0)Hello (4400,500,0)music';
const timed=adapter.attachWordTimings([{time_ms:1500,text:'你好吗'},{time_ms:3500,text:'Hello music'},
    {time_ms:8000,text:'歌词不相同'}],yrc,500);
assert.deepEqual(timed[0].words,[{start_ms:1500,end_ms:1800,text_start:0,text_end:1},
    {start_ms:1800,end_ms:2100,text_start:1,text_end:3}]);
assert.deepEqual(timed[1].words[1],{start_ms:3900,end_ms:4400,text_start:6,text_end:11});
assert.equal('words' in timed[2],false);
assert.equal('words' in adapter.attachWordTimings([{time_ms:2501,text:'你好吗'}],yrc)[0],false);
assert.equal('words' in adapter.attachWordTimings([{time_ms:2250,text:'你好吗'}],yrc)[0],true);
const unicode=adapter.parseYrc('[1000,600](1000,200,0)👩‍💻(1200,200,0)é(1400,200,0)中');
assert.equal(unicode[0].words[1].text_start,3,'协议使用 Unicode 码点，不使用 UTF-16 索引');
assert.equal(unicode[0].words[2].text_start,5);
const late={...state,'async:lyric':{resourceTrackId:'42',displayType:'default',scrollable:true,offset:.5,
    lyricLines:[{time:1.5,lyric:'你好吗'}]}};
assert.equal('words' in adapter.lyricsFor(late,'42')[0],false);
late['async:lyric'].yrcInfo={yrc};
assert.equal(adapter.lyricsFor(late,'42')[0].words[0].start_ms,1500);
assert.strictEqual(adapter.lyricsFor(late,'42'),adapter.lyricsFor(late,'42'),'暖更新复用解析结果');
assert.deepEqual(adapter.parseYrc('broken'),[]);
assert.deepEqual(adapter.parseYrc('[1000,200](1000,0,0)甲')[0].words,[]);
console.log('Optional YRC word timing contract passed');
