// SPDX-License-Identifier: GPL-3.0-or-later
import { makeLedger } from '../probes/ai6_obligation_ledger.mjs';
function runCases(api){
 const {key,rows,coverage,marker,admission}=api;let count=0;const check=(name,got,want)=>{if(got!==want)throw Error(name+": "+got+" != "+want);count++;};
 const k={domain:"fenceA",recording:"L",epoch:"1",run:"1",ordinal:"0",source:"S",destination:"D",generation:"g1"};
 const layout={row:32n,rows:2n,pitch:40n,offset:4n,capacity:88n,staging:512n};
 const span=[[4n,36n],[44n,76n]],i={key:k,layout,sequence:1n},r={key:k,status:"delivered",spans:span};
 const b={relation:"related",eligible:true,retired:true,inventoryComplete:true,intents:[i],receipts:[r]};
 const gate=(name,delta,want)=>check(name,admission({...b,...delta}).admit,want);
 check("exact spans",coverage(rows(layout),span),true);
 check("tight end",rows({...layout,capacity:76n})!==null,true);
 for(const [name,delta] of [["short dest",{capacity:75n}],["short staging",{staging:511n}],["overlapping rows",{pitch:31n}],["zero row",{row:0n}],["zero rows",{rows:0n}],["bound",{rows:4097n}],["u64 offset overflow",{offset:(1n<<64n)-2n}],["u32 host pitch",{row:0xffffffffn,pitch:0xffffffffn,capacity:(1n<<64n)-1n,staging:(1n<<64n)-1n}]])check(name,rows({...layout,...delta})===null,true);
 gate("normal",{},true);gate("gpu unknown",{retired:false},false);gate("not eligible",{eligible:false},false);
 gate("independent",{relation:"independent",retired:false,inventoryComplete:false,receipts:[]},true);
 gate("unknown relation",{relation:"unknown"},false);gate("unknown inventory",{inventoryComplete:false},false);gate("empty related",{intents:[],receipts:[]},false);
 gate("missing receipt",{receipts:[]},false);gate("duplicate receipt",{receipts:[r,r]},false);gate("duplicate intent",{intents:[i,i]},false);
 for(const field of ["epoch","run","ordinal","generation","domain","destination","source","recording"])gate("wrong "+field,{receipts:[{...r,key:{...k,[field]:"other"}}]},false);
 gate("unknown generation",{intents:[{...i,key:{...k,generation:null}}]},false);
 for(const status of ["pending","record-refused","map-refused","partial","unknown","unrecognized"])gate(status,{receipts:[{...r,status}]},false);
 for(const [name,spans,want] of [["padding",[[4n,76n]],false],["missing byte",[[4n,35n],[44n,76n]],false],["duplicate interval",[...span,span[0]],false],["split interval",[[4n,20n],[20n,36n],[44n,76n]],true],["reordered",span.slice().reverse(),true],["extra byte",[[3n,36n],[44n,76n]],false]])gate(name,{receipts:[{...r,spans}]},want);
 const k2={...k,run:"2"},i2={...i,key:k2,sequence:2n},r2={...r,key:k2};
 gate("later success cannot erase first",{intents:[i,i2],receipts:[{...r,status:"record-refused"},r2]},false);
 gate("two exact runs",{intents:[i,i2],receipts:[r,r2]},true);
 const sup={...r,status:"superseded",replacement:key(k2)};
 gate("explicit replacement",{intents:[{...i,replacement:k2},i2],receipts:[sup,r2]},true);
 gate("unproved replacement",{intents:[i,i2],receipts:[sup,r2]},false);
 gate("wrong replacement order",{intents:[{...i,replacement:k2},{...i2,sequence:0n}],receipts:[sup,r2]},false);
 gate("replacement incomplete",{intents:[{...i,replacement:k2},i2],receipts:[sup,{...r2,status:"partial"}]},false);
 const m={owner:"producer1",generation:"g1",address:100n,width:8,value:0xfedcba9876543210n,ordinal:1n};
 const w={ordinal:1n,address:100n,width:8,value:m.value,kind:"value"},p={owner:m.owner,generation:m.generation,final:m.value,writes:[w]};
 gate("marker exact",{expectedMarker:m,markerProof:p},true);
 for(const [name,proof] of [["wrong owner",{...p,owner:"old"}],["wrong gen",{...p,generation:"old"}],["wrong final",{...p,final:0x1234567876543210n}],["low half",{...p,writes:[{...w,width:4,value:0x76543210n}]}],["wrong ordinal",{...p,writes:[{...w,ordinal:2n}]}],["timestamp",{...p,writes:[{...w,kind:"timestamp"}]}],["overlap after",{...p,writes:[w,{...w,ordinal:2n,address:104n,width:4,value:0x12345678n}]}],["duplicate ordinal",{...p,writes:[w,w]}]])gate(name,{expectedMarker:m,markerProof:proof},false);
 gate("unrelated later write",{expectedMarker:m,markerProof:{...p,writes:[w,{...w,ordinal:2n,address:108n,width:4,value:0n}]}},true);
 return count;
}
console.log(`${runCases(makeLedger())} scoped ledger checks passed`);
