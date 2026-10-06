const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../tools/verify_netease_host.mjs'),'utf8');
const clientStep=source.slice(source.indexOf('function clientStep('),source.indexOf('async function remote('));
const exercise=source.slice(source.indexOf('async function exercise(){'),source.indexOf('\ntry {\n'));
async function simulate({frozen=false,skips=false}={}){
    let clock=0,id=1,playing=true,anchor=0,at=0,selectedAt=0,skipPending=false;
    const position=()=>frozen?0:anchor+(playing?(clock-at)/1000:0);
    const click=()=>{anchor=position();at=clock;playing=!playing;};
    const store={getState:()=>({playing:{resourceTrackId:String(id),resourceName:'song '+id,resourceType:'track',
        resourceDuration:120,playingState:playing?2:1,loadingSeekDuration:0},
        'async:lyric':{resourceTrackId:String(id),lyricLines:['test']}}),
        dispatch:action=>{assert.equal(action.type,'playing/setPlayingPosition');anchor=action.payload.duration;at=clock;}};
    const button={click,getBoundingClientRect:()=>({width:10})};
    const next={getBoundingClientRect:button.getBoundingClientRect,click:()=>{id++;anchor=0;at=clock;selectedAt=clock;skipPending=true;}};
    const entry={textContent:'跳动的词 ✓',getBoundingClientRect:button.getBoundingClientRect};
    const context=vm.createContext({FloatingLyricsAdapter:{findStore:()=>store},
        document:{querySelector:selector=>selector.includes('input')?{value:position()}:button,
            querySelectorAll:selector=>selector.includes('next_btn')?[next]:selector==='.floating-lyrics-entry'?[entry]:[button]},
        Date:{now:()=>clock},setTimeout:(callback,ms)=>{
            clock+=ms;
            if(skips&&skipPending&&clock-selectedAt>=2000){id++;anchor=0;at=clock;skipPending=false;}
            callback();
        }});
    // NetEase's bundled Chromium does not implement Array.prototype.at.
    vm.runInContext('Array.prototype.at=undefined;',context);
    vm.runInContext(clientStep,context);
    context.remote=async(operation,payload)=>{context.operation=operation;context.payload=payload;return vm.runInContext('clientStep(operation,payload)',context);};
    return await vm.runInContext(exercise+'\nexercise();',context);
}
(async()=>{
    const healthy=await simulate();
    assert.equal(healthy.passed,true);
    assert.equal(healthy.songs.length,3);
    const frozen=await simulate({frozen:true});
    assert.equal(frozen.passed,false);
    assert.equal(frozen.checks.hostProgressMoves,false);
    assert.equal(frozen.checks.threeNextSongsPlay,false);
    const skipping=await simulate({skips:true});
    assert.equal(skipping.passed,false);
    assert.equal(skipping.checks.threeNextCommandsStaySelected,false);
    console.log('Host validator rejects frozen progress and automatic skips; old Chromium compatibility passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
