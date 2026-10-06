const assert=require('node:assert/strict');
const adapter=require('../plugins/netease/adapter.js');

// Each command instance keeps its own callbacks, but the native side has just
// one slot per event. This models the client's APPEND registration semantics.
const nativeSlots=new Map();
class Command {
    constructor(){this.callbacks=new Map();}
    append(name,callback){
        let queue=this.callbacks.get(name);
        if(!queue){queue=[];this.callbacks.set(name,queue);nativeSlots.set(name,args=>queue.forEach(fn=>fn(args)));}
        queue.push(callback);
        return {unsubscribe:()=>queue.splice(queue.indexOf(callback),1)};
    }
}
const client=new Command(),legacy=new Command();
let hostPosition=0,hostSeek=0;
client.append('progress',args=>hostPosition=args[1]);
client.append('seek',args=>hostSeek=args[3]);
// Demonstrate that a different instance's APPEND replaces the host's slot.
legacy.append('progress',()=>{});
nativeSlots.get('progress')(['song-a',2]);
assert.equal(hostPosition,0);
// Restore the original host queue for the corrected adapter's regression test.
nativeSlots.set('progress',args=>client.callbacks.get('progress').forEach(fn=>fn(args)));
const streams={audioPlayerPlayProgress$:{subscribe:fn=>client.append('progress',fn)},
    audioPlayerSeek$:{subscribe:fn=>client.append('seek',fn)}};
let captures=0;
const runtime={c:{app:{exports:streams}}};
const host={webpackJsonp:{push:chunk=>{captures++;chunk[1][chunk[0][0]]({}, {}, runtime);}},
    legacyNativeCmder:{appendRegisterCall:()=>{throw new Error('Must not register on a separate command instance');}}};
assert.equal(adapter.playbackStreams(host),streams);
assert.equal(adapter.playbackStreams(host),streams);
assert.equal(captures,1);
let playing={playId:'song-a',playingState:2},fail=false;
const updates=[],errors=[];
const reader=new adapter.PlaybackEvents(()=>adapter.playbackStreams(host),()=>playing,
    (...args)=>{if(fail)throw new Error('consumer failed');updates.push(args);},error=>errors.push(error));
reader.attach();
for(let i=0;i<10;i++)reader.attach();
assert.equal(client.callbacks.get('progress').length,2,'Only one plugin observer may be attached');
nativeSlots.get('progress')(['song-a',3.5]);
assert.equal(hostPosition,3.5,'NetEase progress must still update');
assert.deepEqual(updates.pop(),['song-a',3500,false]);
nativeSlots.get('seek')(['song-a','seek-1',0,25]);
assert.equal(hostSeek,25,'NetEase must still finish its seek');
assert.deepEqual(updates.pop(),['song-a',25000,true]);
playing={playId:'song-b',playingState:2};
nativeSlots.get('progress')(['song-a',40]);
assert.equal(updates.length,0,'Old song callbacks must not move the new lyrics');
nativeSlots.get('progress')(['song-b',1]);
assert.deepEqual(updates.pop(),['song-b',1000,false]);
let downstream=0;
client.append('progress',()=>downstream++);
fail=true;
nativeSlots.get('progress')(['song-b',2]);
assert.equal(downstream,1,'A plugin exception must not interrupt the host callback queue');
assert.equal(errors.length,1);
reader.close();
nativeSlots.get('progress')(['song-b',3]);
assert.equal(hostPosition,3,'Closing the plugin must leave client callbacks intact');
assert.equal(downstream,2);
assert.equal(client.callbacks.get('progress').length,2);
assert.equal(client.callbacks.get('seek').length,1);
console.log('Host progress, seek, song changes and callback isolation passed');
