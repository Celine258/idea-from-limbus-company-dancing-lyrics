// Development-only discovery: module IDs differ between 3.1.40 and 3.1.41.
function findSongDetails(runtime) {
    const id=Object.keys(runtime.m).find(id=>runtime.m[id].toString().includes('/api/v3/song/detail'));
    if(!id)throw new Error('Client song metadata module unavailable');
    const source=runtime.m[id].toString();
    const symbol=source.match(/([\w$]+)=Object\([^)]+\)\(\{url:"\/api\/v3\/song\/detail"/)?.[1];
    const key=[...source.matchAll(/\.d\(\w+,"([^"]+)",\(function\(\)\{return ([\w$]+)\}\)\)/g)].find(match=>match[2]===symbol)?.[1];
    const method=key&&runtime(id)[key];
    if(typeof method!=='function')throw new Error('Client song metadata export unavailable');
    return method;
}
function readPlaybackPosition(document, duration) {
    let input=document.querySelector('[aria-label="播放进度调节"] input[type="range"]');
    if(!input){
        const candidates=[...document.querySelectorAll('input[type="range"]')].filter(input=>
            Math.abs(Number(input.max)-duration)<1 && Number(input.min)===0 && input.getBoundingClientRect().width>0);
        if(candidates.length===1)input=candidates[0];
    }
    const value=input?Number(input.value):NaN;
    if(!Number.isFinite(value))throw new Error('Client playback position input unavailable');
    return value;
}
module.exports={findSongDetails,readPlaybackPosition};
