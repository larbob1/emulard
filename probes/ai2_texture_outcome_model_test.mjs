// SPDX-License-Identifier: GPL-3.0-or-later
import * as api from './ai2_texture_outcome_model.mjs';

function runTests(api) {
    const {activeOffsets,fixtureBytes,classifyTexture,publicationDecision}=api;
    let tests=0, failures=[];
    function check(name,value) {tests++;if(!value) failures.push(name);}
    const key={domain:"owned",allocation:"A",source:"texture",recording:"list-A",generation:1,epoch:1,run:1,ordinal:1};
    const intent={key,layout:"owned-r8-7x3-array2-mip2",backing:"owned_stable",seed:19,relation:"related"};
    const {before,expected}=fixtureBytes();
    const good={key,layout:intent.layout,backing:intent.backing,stage:"landed",transfer:"complete",coverage:activeOffsets(),bytes:expected};
    const related={relation:"related",provenance:"explicit_dependency",required:[key]};
    const inv={complete:true,intents:[intent]};
    const decide=(event=related,inventory=inv,receipts=[good],retired="confirmed")=>publicationDecision(event,inventory,receipts,retired);
    const refuse=stage=>({...good,stage,transfer:"not_attempted",bytes:before});
    check("coverage 48 distinct",new Set(activeOffsets()).size===48);
    check("independent full byte fixture",expected.reduce((n,v,i)=>n+(v!==before[i]),0)===48);
    check("successful transfer",classifyTexture(intent,good).delivered);
    check("admit complete related",decide()==="admit_scoped");
    for(const stage of ["target_refused","record_refused","preserve_read_refused","map_refused","tile_refused","pre_copy_refused"]) {
        let a=refuse(stage), v=classifyTexture(intent,a);
        check(stage+" exact untouched",v.status===stage&&v.mutation==="none_by_scoped_operation"&&!v.delivered);
        check(stage+" withhold",decide(related,inv,[a])==="withhold_unresolved");
        check(stage+" no false untouched",classifyTexture(intent,{...a,transfer:"unknown"}).mutation==="unknown");
    }
    for(const off of activeOffsets()){
        let coverage=good.coverage.filter(x=>x!==off);
        check("omitted coverage "+off,!classifyTexture(intent,{...good,coverage}).delivered);
        let bytes=expected.slice();bytes[256+off]=before[256+off];
        check("omitted byte "+off,!classifyTexture(intent,{...good,bytes}).delivered);
    }
    for(const off of [0,255,256+4,256+255,256+2559,2816,65535]){
        let bytes=expected.slice();bytes[off]^=1;
        check("padding or guard mutation "+off,!classifyTexture(intent,{...good,bytes}).delivered);
    }
    check("duplicate coverage",!classifyTexture(intent,{...good,coverage:[...good.coverage.slice(1),good.coverage[1]]}).delivered);
    for(const p of ["generation","epoch","run","ordinal","domain","allocation","source","recording"]){
        let k={...key,[p]:typeof key[p]==="number"?2:"other"};
        check("wrong "+p,!classifyTexture(intent,{...good,key:k}).delivered);
    }
    for(const transfer of ["partial","unknown","not_attempted"]){
        check("transfer "+transfer,!classifyTexture(intent,{...good,transfer}).delivered);
        check("transfer gate "+transfer,decide(related,inv,[{...good,transfer}])==="withhold_unresolved");
    }
    check("stale not superseded",!classifyTexture(intent,{...good,stage:"stale_unproved"}).delivered);
    check("asserted supersession rejected",!classifyTexture(intent,{...good,stage:"superseded",proved:true}).delivered);
    check("unknown backing",!classifyTexture(intent,{...good,backing:"unknown"}).delivered);
    check("unknown retirement",decide(related,inv,[good],"unknown")==="withhold_unresolved");
    check("no retirement",decide(related,inv,[good],"not_submitted")==="withhold_unresolved");
    check("missing receipt",decide(related,inv,[])==="withhold_unresolved");
    check("duplicate receipt",decide(related,inv,[good,good])==="withhold_unresolved");
    check("unknown inventory",decide(related,{...inv,complete:false})==="withhold_unresolved");
    check("empty inventory not success",decide({...related,required:[]},{complete:true,intents:[]},[])==="withhold_unresolved");
    check("unknown event",decide({relation:"unknown",required:[]})==="withhold_unresolved");
    check("claimed independence rejected",decide({relation:"independent",required:[]})==="withhold_unresolved");
    const independent={relation:"independent",provenance:"explicit_independent",required:[]};
    const independentInv={complete:true,intents:[{...intent,relation:"independent"}]};
    check("explicit independence preserved",decide(independent,independentInv,[refuse("record_refused")],"unknown")==="outside_scope_preserve");
    const key2={...key,run:2}, intent2={...intent,key:key2}, good2={...good,key:key2};
    const inv2={complete:true,intents:[intent,intent2]}, both={...related,required:[key,key2]};
    check("both delivered",decide(both,inv2,[good,good2])==="admit_scoped");
    check("later success cannot erase earlier refusal",decide(both,inv2,[refuse("record_refused"),good2])==="withhold_unresolved");
    check("omitted earlier dependency",decide({...related,required:[key2]},inv2,[good2])==="withhold_unresolved");
    check("duplicate intent",decide(related,{complete:true,intents:[intent,intent]},[good])==="withhold_unresolved");
    check("unknown relation",decide(related,{complete:true,intents:[{...intent,relation:"unknown"}]},[good])==="withhold_unresolved");
    check("explicit disjoint inventory",decide(related,{complete:true,intents:[intent,{...intent2,relation:"independent"}]},[good])==="admit_scoped");
    check("unexpected receipt",decide(related,inv,[good,good2])==="withhold_unresolved");
    const sparse=a=>{const v=a.slice();v.length++;return v;};
    check("sparse coverage",!classifyTexture(intent,{...good,coverage:sparse(good.coverage.slice(1))}).delivered);
    for(const [label,value] of [["hole",sparse([intent])],["null",[intent,null]],["undefined",[intent,undefined]],["scalar",[intent,1]],["array",[intent,[]]],["not array",{}]]){
        check("malformed inventory "+label,decide(related,{complete:true,intents:value},[good])==="withhold_unresolved");
    }
    for(const [label,value] of [["hole",sparse([key])],["null",[key,null]],["undefined",[key,undefined]],["scalar",[key,1]],["array",[key,[]]],["not array",{}]]){
        check("malformed required "+label,decide({...related,required:value})==="withhold_unresolved");
    }
    for(const [label,value] of [["hole",sparse([good])],["null",[good,null]],["undefined",[good,undefined]],["scalar",[good,1]],["array",[good,[]]],["not array",{}]]){
        check("malformed receipts "+label,decide(related,inv,value)==="withhold_unresolved");
    }
    const otherKey={...key,recording:"list-B"};
    const otherIntent={...intent,key:otherKey},otherGood={...good,key:otherKey};
    check("different recording same epoch distinct",decide({...related,required:[key,otherKey]},{complete:true,intents:[intent,otherIntent]},[good,otherGood])==="admit_scoped");
    check("different recording cannot discharge",decide(related,inv,[otherGood])==="withhold_unresolved");
    check("missing recording rejected",!classifyTexture(intent,{...good,key:{...key,recording:undefined}}).delivered);
    check("inherited recording rejected",!classifyTexture(intent,{...good,key:Object.assign(Object.create({recording:"list-A"}),Object.fromEntries(Object.entries(key).filter(([p])=>p!=="recording")))}).delivered);
    check("independent required key contradiction",decide({...independent,required:[key]},independentInv)==="withhold_unresolved");
    check("independent related inventory contradiction",decide(independent,inv)==="withhold_unresolved");
    check("independent unknown inventory relation",decide(independent,{complete:true,intents:[{...intent,relation:"unknown"}]})==="withhold_unresolved");
    check("independent sparse inventory",decide(independent,{complete:true,intents:sparse(independentInv.intents)})==="withhold_unresolved");
    check("independent sparse required",decide({...independent,required:new Array(1)},independentInv)==="withhold_unresolved");
    check("independent duplicate inventory",decide(independent,{complete:true,intents:[...independentInv.intents,...independentInv.intents]})==="withhold_unresolved");
    check("explicit independent without inventory",publicationDecision(independent,undefined,undefined,"unknown")==="outside_scope_preserve");
    return {tests,passed:tests-failures.length,failures};
}

const result=runTests(api);
console.log(JSON.stringify(result));
if(result.failures.length) throw new Error('texture outcome model failed');
