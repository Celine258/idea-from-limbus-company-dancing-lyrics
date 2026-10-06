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
let native={appendRegisterCall:()=>{throw new Error('bound before the player was ready')}},playing=null;
const callbacks={},updates=[];
const reader=new adapter.PlaybackEvents(()=>native,()=>playing,(...args)=>updates.push(args));
reader.attach();
native={appendRegisterCall:(name,_prefix,callback)=>{callbacks[name]=callback;}};
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
