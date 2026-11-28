// SPDX-License-Identifier: GPL-3.0-or-later
// Pure owned-fixture model only. No runtime pointers, GPU work or terminal policy.

function activeOffsets() {
    const offsets = [];
    for (const [base, width, height] of [[512,7,3],[0,3,1],[1792,7,3],[1280,3,1]]) {
        for (let y=0;y<height;y++) for (let x=0;x<width;x++) offsets.push(base+256*y+x);
    }
    return offsets.sort((a,b)=>a-b);
}

function validKey(k) {
    return k !== null && typeof k === "object" &&
        ["domain","allocation","source"].every(p=>typeof k[p]==="string"&&k[p].length>0) &&
        ["generation","epoch","run","ordinal"].every(p=>Number.isSafeInteger(k[p])&&k[p]>0);
}

function keyString(k) {
    return validKey(k) ? JSON.stringify([k.domain,k.allocation,k.source,k.generation,k.epoch,k.run,k.ordinal]) : null;
}

function fixtureBytes(seed=19) {
    if (!Number.isSafeInteger(seed)||seed<0||seed>255) throw new Error("invalid fixture seed");
    const before = new Uint8Array(65536);
    for(let i=0;i<before.length;i++) before[i]=(i*17+seed)&255;
    const expected=before.slice();
    for (const [j,off] of activeOffsets().entries()) expected[256+off]=before[256+off]^((j%255)+1);
    return {before,expected};
}

function bytesEqual(a,b) {
    return a instanceof Uint8Array && b instanceof Uint8Array && a.length===65536 && b.length===65536 &&
        a.every((v,i)=>v===b[i]);
}

function exactActiveCoverage(offsets) {
    const expected=activeOffsets();
    return Array.isArray(offsets) && offsets.length===expected.length &&
        offsets.every(Number.isSafeInteger) && new Set(offsets).size===expected.length &&
        [...offsets].sort((a,b)=>a-b).every((v,i)=>v===expected[i]);
}

function classifyTexture(intent, receipt) {
    const result=(status,mutation,delivered=false)=>({status,mutation,delivered});
    if (!intent || !receipt || !validKey(intent.key) || keyString(intent.key)!==keyString(receipt.key))
        return result("identity_unknown","unknown");
    if (intent.layout!=="owned-r8-7x3-array2-mip2" || receipt.layout!==intent.layout ||
        !Number.isSafeInteger(intent.seed) || intent.seed<0 || intent.seed>255 ||
        intent.backing!=="owned_stable" || receipt.backing!==intent.backing)
        return result("scope_unknown","unknown");
    if (receipt.stage==="target_refused" || receipt.stage==="record_refused" ||
        receipt.stage==="preserve_read_refused" || receipt.stage==="map_refused" ||
        receipt.stage==="tile_refused" || receipt.stage==="pre_copy_refused") {
        // An explicit no-transfer witness is required; observed bytes alone
        // cannot prove that no operation wrote and subsequently restored them.
        const {before}=fixtureBytes(intent.seed);
        return receipt.transfer==="not_attempted" && bytesEqual(receipt.bytes,before)
            ?result(receipt.stage,"none_by_scoped_operation")
            :result("inconsistent_refusal","unknown");
    }
    if (receipt.stage==="stale_unproved") return result("stale_unproved","unknown");
    if (receipt.stage!=="landed") return result("unobserved","unknown");
    if (receipt.transfer==="partial") return result("partial","possible_partial");
    if (receipt.transfer!=="complete") return result("transfer_unknown","unknown");
    const {expected}=fixtureBytes(intent.seed);
    if (!exactActiveCoverage(receipt.coverage) || !bytesEqual(receipt.bytes,expected))
        return result("coverage_or_bytes_mismatch","unknown");
    return result("delivered","complete",true);
}

function publicationDecision(event, inventory, receipts, retirement) {
    // This is an abstract admission predicate, not terminal/recovery policy.
    if (!event || !["related","independent","unknown"].includes(event.relation))
        return "withhold_unresolved";
    if (event.relation==="independent") return event.provenance==="explicit_independent"
        ?"outside_scope_preserve":"withhold_unresolved";
    if (event.relation!=="related" || event.provenance!=="explicit_dependency" ||
        retirement!=="confirmed" || !inventory || inventory.complete!==true ||
        !Array.isArray(inventory.intents) || !Array.isArray(event.required) ||
        event.required.length===0 || !Array.isArray(receipts)) return "withhold_unresolved";
    const keys=inventory.intents.map(i=>keyString(i?.key));
    const expected=event.required.map(keyString);
    const actual=receipts.map(r=>keyString(r?.key));
    if ([...keys,...expected,...actual].includes(null) ||
        new Set(keys).size!==keys.length || new Set(expected).size!==expected.length ||
        new Set(actual).size!==actual.length || actual.some(k=>!keys.includes(k)) ||
        expected.some(k=>!keys.includes(k))) return "withhold_unresolved";
    // Explicit relation proof defines required keys. An event cannot omit an
    // inventory member known related or whose relation remains unknown.
    for (let i=0;i<keys.length;i++) {
        const relation=inventory.intents[i].relation;
        if (!["related","independent"].includes(relation) ||
            (relation==="related")!==expected.includes(keys[i])) return "withhold_unresolved";
    }
    for (const k of expected) {
        const intent=inventory.intents[keys.indexOf(k)];
        const receipt=receipts[actual.indexOf(k)];
        if (!classifyTexture(intent,receipt).delivered) return "withhold_unresolved";
    }
    // Supersession is deliberately not accepted until real provenance and
    // ordering semantics are specified; a boolean claim is insufficient.
    return "admit_scoped";
}

export {activeOffsets,fixtureBytes,classifyTexture,publicationDecision};
