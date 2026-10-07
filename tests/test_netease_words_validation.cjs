const assert=require('node:assert/strict');
(async()=>{
    const {regressionChecks,seekFinishes}=await import('../tools/word_regression_checks.mjs');
    assert(seekFinishes([{position:92.943,seekLoading:0}],93.405));
    assert(!seekFinishes([{position:0,seekLoading:0}],93.405));
    assert(!seekFinishes([{position:93.4,seekLoading:1}],93.405));
    const cases=[{timedLines:8,freeze:true,seekFinishes:true,progresses:true},
        {timedLines:19,freeze:true,seekFinishes:true,progresses:true},
        {timedLines:0,lyricCount:70,progresses:true},
        {displayType:'pure',timedLines:0,progresses:true}];
    const songs=Array.from({length:3},()=>({staysSelected:true,progresses:true,lyricMatches:true}));
    assert(Object.values(regressionChecks(cases,songs)).every(Boolean));
    assert(!regressionChecks(cases,[]).threeNextSongsProgress);
    assert(!regressionChecks(cases.map((c,i)=>i===3?{...c,progresses:false}:c),songs).allSelectedSongsProgress);
    assert(!regressionChecks(cases,songs.map((s,i)=>i===1?{...s,staysSelected:false}:s)).threeNextCommandsStaySelected);
    assert(!regressionChecks(cases.map((c,i)=>i===0?{...c,timedLines:0}:c),songs).realEnglishWords);
    console.log('Native word regression evidence checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
