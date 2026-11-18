"use strict";
const $=id=>document.getElementById(id);
let token=null;
let selectedMerchant=null;
function msg(t,isError=false){$("notice").textContent=t;$("notice").style.color=isError?"#a33e36":"#087c81"}
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=String(text);if(cls)el.className=cls;return el}
function link(url,label){const a=node("a",label||url);try{const u=new URL(url);if(!["https:","http:"].includes(u.protocol))throw Error("Unsafe URL");a.href=u.href;a.target="_blank";a.rel="noopener noreferrer"}catch{a.removeAttribute("href")}return a}
function labelInput(form,caption,name,type="text",required=false){const l=node("label",caption);form.append(l);const v=node("input");v.name=name;v.type=type;v.required=required;form.append(v);return v}
async function api(path,method="GET",body){
    if(!token)throw Error("يرجى تسجيل الدخول");
    const res=await fetch("/api/v2"+path,{method,headers:{"Authorization":"Bearer "+token,...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});
    const data=await res.json().catch(()=>({}));
    if(!res.ok)throw Error((data.detail||"Request failed")+" ("+res.status+")");
    return data;
}
async function action(fn){try{await fn()}catch(e){msg(e.message||String(e),true)}}
$("loginForm").onsubmit=e=>{e.preventDefault();action(async()=>{
    const body=Object.fromEntries(new FormData(e.target));
    const res=await fetch("/api/v2/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const data=await res.json().catch(()=>({}));
    if(!res.ok)throw Error("فشل تسجيل الدخول. راجع البريد وكلمة المرور والمؤسسة.");
    token=data.access_token;
    const me=await api("/me");
    $("identity").textContent="الدور: "+me.role+" | المؤسسة: "+me.org_id;
    $("auth").classList.add("hidden");$("workspace").classList.remove("hidden");
    $("loginForm").reset();msg("تم تسجيل الدخول. جميع العمليات مرتبطة بحسابك.");
    await merchants();
})};
$("logout").onclick=()=>action(async()=>{try{await api("/logout","POST")}finally{token=null;$("identity").textContent="";$("workspace").classList.add("hidden");$("auth").classList.remove("hidden");msg("تم إنهاء الجلسة.")}});
$("navMerchants").onclick=()=>{$("merchantsPanel").classList.remove("hidden");$("reviewsPanel").classList.add("hidden");action(merchants)};
$("navReviews").onclick=()=>{$("reviewsPanel").classList.remove("hidden");$("merchantsPanel").classList.add("hidden");action(reviews)};
$("merchantForm").onsubmit=e=>{e.preventDefault();action(async()=>{
    const values=Object.fromEntries(new FormData(e.target));
    if(!values.website)delete values.website;
    await api("/merchants","POST",values);e.target.reset();msg("تم حفظ التاجر");await merchants();
})};
async function merchants(){
    const list=(await api("/merchants")).merchants;
    const box=$("merchantList");box.replaceChildren();
    if(!list.length){box.append(node("p","لا توجد سجلات ضمن هذه المؤسسة.","muted"));return}
    for(const m of list){
        const b=node("button",(m.name||"")+" — "+(m.city||""),"list-button");
        b.onclick=()=>action(()=>dossier(m.id));box.append(b);
    }
}
async function dossier(id){
    selectedMerchant=id;
    const data=await api("/merchants/"+id);
    const m=data.merchant;
    const root=$("dossier");root.replaceChildren();
    root.append(node("h2",m.name+" — "+m.city));
    root.append(node("p","القطاع: "+(m.category||"غير متاح"),"muted"));
    const bar=node("div",undefined,"button-row no-print");
    const analyze=node("button","تحليل الأدلة وإعداد توصيات معلقة");
    analyze.onclick=()=>action(async()=>{const r=await api("/merchants/"+id+"/analyze","POST");msg("أُعدّ تحليل وتوصيات معلقة: "+r.pending_recommendations.length);await dossier(id)});
    const print=node("button","طباعة الملف","secondary");print.onclick=()=>window.print();
    bar.append(analyze,print);root.append(bar);
    const form=node("form");form.className="item no-print";
    form.append(node("h3","إضافة دليل"));
    labelInput(form,"المنصة","platform","text",true);
    labelInput(form,"رابط المنشور","source_url","url",true);
    labelInput(form,"تاريخ الرصد","observed_at","datetime-local",true);
    labelInput(form,"تاريخ النشر الفعلي (اختياري)","published_at","datetime-local");
    labelInput(form,"النص المرصود","text");
    const send=node("button","حفظ الدليل");form.append(send);
    form.onsubmit=e=>{e.preventDefault();action(async()=>{
        const v=Object.fromEntries(new FormData(form));
        v.observed_at=new Date(v.observed_at).toISOString();
        if(v.published_at)v.published_at=new Date(v.published_at).toISOString();else delete v.published_at;
        await api("/merchants/"+id+"/evidence","POST",v);msg("تم توثيق الدليل");await dossier(id)
    })};root.append(form);
    root.append(node("h3","الأدلة المسجلة ("+data.evidence.length+")"));
    for(const e of data.evidence){
        const div=node("div",undefined,"item");
        div.append(link(e.source_url,e.source_url));div.append(node("p",e.body||"لا يوجد نص منشور"));
        div.append(node("small","رُصد: "+e.observed_at+" | نُشر: "+(e.published_at||"غير موثق")));
        root.append(div);
    }
    root.append(node("h3","التوصيات ("+data.recommendations.length+")"));
    for(const rec of data.recommendations){
        const div=node("div",undefined,"item");
        div.append(node("strong",rec.problem));div.append(node("p",rec.action));div.append(node("small","الحالة: "+rec.status));root.append(div);
    }
}
async function reviews(){
    const pending=(await api("/reviews")).pending;
    const box=$("reviewList");box.replaceChildren();
    if(!pending.length){box.append(node("p","لا توجد توصيات تنتظر المراجعة.","muted"));return}
    for(const rec of pending){
        const item=node("div",undefined,"item");
        item.append(node("h3",rec.problem));
        item.append(node("p",rec.action));
        item.append(node("small","المؤسسة والتاجر: "+rec.merchant_id));
        const sources=rec.sources||[];
        item.append(node("p","الأدلة المرتبطة: "+sources.length));
        for(const src of sources){const p=node("p");p.append(link(src.url,src.url));p.append(node("small"," تاريخ الرصد: "+src.observed_at));item.append(p)}
        const form=node("form",undefined,"no-print");const reason=labelInput(form,"مبرر القرار","notes","text",true);
        const controls=node("div",undefined,"button-row");
        for(const [status,label,color] of [["approved","اعتماد",""],["changes_requested","طلب تعديل","secondary"],["rejected","رفض","danger"]]){
            const b=node("button",label,color);b.type="button";b.onclick=()=>action(async()=>{
                if(reason.value.trim().length<3)throw Error("يجب توثيق سبب القرار");
                await api("/recommendations/"+rec.id+"/review","POST",{decision:status,notes:reason.value});
                msg("حُفظ قرار المراجعة: "+label);await reviews();
            });controls.append(b);
        }form.append(controls);item.append(form);box.append(item);
    }
}
