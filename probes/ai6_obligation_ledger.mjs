// SPDX-License-Identifier: GPL-3.0-or-later
// Pure scratch model; no runtime imports or policy registration.
function makeLedger() {
 const MAX=(1n<<64n)-1n, LIMIT=4096n;
 const uint=x=>typeof x==="bigint"&&x>=0n&&x<=MAX;
 const token=x=>typeof x==="string"&&x.length>0;
 const object=x=>x!==null&&typeof x==="object"&&!Array.isArray(x);
 const dense=(a,max=8192)=>Array.isArray(a)&&a.length<=max&&Array.from({length:a.length},(_,i)=>Object.hasOwn(a,i)).every(Boolean);
 const only=(x,fields)=>object(x)&&Object.keys(x).every(k=>fields.includes(k));
 const fields=["domain","recording","epoch","run","ordinal","source","destination","generation"];
 function key(k){return object(k)&&fields.every(f=>Object.hasOwn(k,f)&&token(k[f]))?JSON.stringify(fields.map(f=>k[f])):null;}
 function rows(x){
  if(!x||![x.row,x.rows,x.pitch,x.offset,x.capacity,x.staging].every(uint)||x.row===0n||x.rows===0n||x.rows>LIMIT||x.pitch<x.row)return null;
  const hp=((x.row+255n)/256n)*256n;
  const end=x.offset+x.pitch*(x.rows-1n)+x.row;
  if(hp>0xffffffffn||hp*x.rows>MAX||hp*x.rows>x.staging||end>MAX||end>x.capacity)return null;
  return Array.from({length:Number(x.rows)},(_,i)=>[x.offset+BigInt(i)*x.pitch,x.offset+BigInt(i)*x.pitch+x.row]);
 }
 function normalize(spans){
  if(!dense(spans))return null;
  if(!spans.every(s=>dense(s,2)&&s.length===2&&s.every(uint)&&s[0]<s[1]))return null;
  const sorted=spans.map(s=>s.slice()).sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:0), out=[];
  for(const s of sorted){const last=out.at(-1);if(last&&s[0]<last[1])return null;if(last&&s[0]===last[1])last[1]=s[1];else out.push(s);}
  return out;
 }
 function coverage(expected,observed){
  const a=normalize(expected),b=normalize(observed);
  return a!==null&&b!==null&&a.length===b.length&&a.every((s,i)=>s[0]===b[i][0]&&s[1]===b[i][1]);
 }
 function marker(expected,proof){
  if(!object(expected)||!object(proof)||!token(expected.owner)||!token(expected.generation)||!uint(expected.address)||![4,8].includes(expected.width)||!uint(expected.value)||!uint(expected.ordinal))return false;
  const cap=1n<<BigInt(expected.width*8);
  if(expected.address+BigInt(expected.width)>MAX||expected.value>=cap||proof.owner!==expected.owner||proof.generation!==expected.generation||proof.final!==expected.value||proof.complete!==true||!dense(proof.writes))return false;
  let found=false,last=-1n;
  for(const w of proof.writes){
   if(!object(w)||!["value","gpu-timestamp","system-timestamp"].includes(w.kind)||!uint(w.ordinal)||w.ordinal<=last||!uint(w.address)||![4,8].includes(w.width)||!uint(w.value)||w.address+BigInt(w.width)>MAX||w.value>=(1n<<BigInt(w.width*8)))return false;
   last=w.ordinal;
   if(w.ordinal===expected.ordinal){
    if(w.kind!=="value"||w.address!==expected.address||w.width!==expected.width||w.value!==expected.value)return false;
    found=true;
   }else if(w.ordinal>expected.ordinal&&w.address<expected.address+BigInt(expected.width)&&expected.address<w.address+BigInt(w.width))return false;
  }
  return found;
 }
 function admission(input){
  const deny=reason=>({admit:false,reason});
  if(!object(input))return deny("malformed-input");
  const {relation,eligible,retired,inventoryComplete,intents,receipts,expectedMarker,markerProof,event}=input;
  if(eligible!==true)return deny("not-eligible");
  if(!object(event)||!token(event.id)||event.relation!==relation||!dense(event.required)||!event.required.every(token)||new Set(event.required).size!==event.required.length||!dense(intents)||!dense(receipts))return deny("invalid-contract");
  if(relation==="independent"){
   if(event.route!=="nonmarker"||event.required.length||intents.length||receipts.length||expectedMarker!==undefined||markerProof!==undefined||event.markerOwner!==undefined||event.markerGeneration!==undefined)return deny("contradictory-independent");
   return {admit:true,reason:"independent"};
  }
  if(relation!=="related")return deny("unknown-relation");
  if(retired!==true)return deny("gpu-unconfirmed");
  if(inventoryComplete!==true||!intents.length)return deny("unknown-inventory");
  if(event.route==="marker"){
   if(!object(expectedMarker)||!object(markerProof)||!event.required.includes(event.markerOwner)||!token(event.markerGeneration)||expectedMarker.owner!==event.markerOwner||expectedMarker.generation!==event.markerGeneration||expectedMarker.event!==event.id||markerProof.event!==event.id||!marker(expectedMarker,markerProof))return deny("marker");
  }else if(event.route!=="nonmarker"||expectedMarker!==undefined||markerProof!==undefined||event.markerOwner!==undefined||event.markerGeneration!==undefined)return deny("invalid-route");
  const expected=new Map(), actual=new Map();
  for(const i of intents){const k=key(i?.key),span=rows(i?.layout);if(k===null||span===null||expected.has(k))return deny("invalid-intent");expected.set(k,{i,span});}
  if(event.required.length!==expected.size||event.required.some(k=>!expected.has(k)))return deny("inventory-binding");
  for(const r of receipts){
   const k=key(r?.key);
   if(k===null||actual.has(k)||!expected.has(k))return deny("invalid-receipt");
   if(r.status==="delivered"&&!only(r,["key","status","spans"]))return deny("invalid-receipt");
   if(r.status==="superseded"&&!only(r,["key","status","replacement"]))return deny("invalid-receipt");
   if(!["delivered","superseded"].includes(r.status))return deny("incomplete");
   actual.set(k,r);
  }
  if(actual.size!==expected.size)return deny("missing-receipt");
  for(const [k,{i,span}] of expected){
   const r=actual.get(k);
   if(r.status==="delivered"){if(!coverage(span,r.spans))return deny("coverage");continue;}
   if(r.status!=="superseded")return deny("incomplete");
   // This is a fixture-supplied, explicit ordered replacement contract, not an inferred alias.
   const successor=key(i.replacement), replacement=expected.get(successor), rr=actual.get(successor);
   if(!replacement||successor===k||!rr||rr.status!=="delivered"||r.replacement!==successor||
      i.key.domain!==replacement.i.key.domain||i.key.destination!==replacement.i.key.destination||
      i.key.generation!==replacement.i.key.generation||i.key.source!==replacement.i.key.source||
      !uint(i.sequence)||!uint(replacement.i.sequence)||replacement.i.sequence<=i.sequence||
      !coverage(span,replacement.span)||!coverage(span,rr.spans))return deny("unproved-supersession");
  }
  return {admit:true,reason:"complete"};
 }
 return {key,rows,coverage,marker,admission};
}
export { makeLedger };
