
'use strict';
const $=id=>document.getElementById(id);
let token=null, me=null, merchants=[], selected=null, pending=[];
function alertText(message,error=false){$('alerts').textContent=message;$('alerts').style.color=error?'#a74541':'#087f80';}
async function api(path,method='GET',body){
    const headers={'Accept':'application/json'};
    if(token)headers.Authorization='Bearer '+token;
    if(body)headers['Content-Type']='application/json';
    const response=await fetch('/api/v2'+path,{method,headers,body:body?JSON.stringify(body):undefined,cache:'no-store'});
    let result;try{result=await response.json()}catch{result={detail:'Invalid response'}}
    if(!response.ok)throw Error(response.status+': '+String(result.detail??'Request failed').slice(0,250));
    return result;
}
async function handle(callback){try{await callback()}catch(error){alertText(error.message,true)}}
function textElement(tag,text,cls){const x=document.createElement(tag);x.textContent=String(text??'—');if(cls)x.className=cls;return x}
function paragraph(parent,tag,text,cls){const p=textElement(tag,text,cls);parent.append(p);return p}
function showPanel(id){document.querySelectorAll('.panel').forEach(x=>x.hidden=x.id!==id);document.querySelectorAll('[data-panel]').forEach(x=>x.classList.toggle('active',x.dataset.panel===id))}
document.querySelectorAll('[data-panel]').forEach(x=>x.onclick=()=>{showPanel(x.dataset.panel);if(x.dataset.panel==='reviewsPanel')loadReviews()});
$('loginForm').onsubmit=e=>{e.preventDefault();handle(async()=>{
    const f=Object.fromEntries(new FormData(e.target));
    const result=await api('/login','POST',f);
    token=result.access_token;
    me=await api('/me');
    $('loginBox').hidden=true;$('workspace').hidden=false;$('logout').hidden=false;
    $('identity').textContent=me.role+' | '+me.user_id.slice(0,8);
    $('meInfo').textContent='المؤسسة: '+me.org_id+' — المستخدم: '+me.user_id+' — الدور: '+me.role;
    e.target.reset();await refresh();
    alertText('تم تسجيل الدخول. جميع البيانات معزولة حسب مؤسستك.');
})};
$('logout').onclick=()=>handle(async()=>{if(token)await api('/logout','POST');token=null;me=null;merchants=[];selected=null;$('workspace').hidden=true;$('loginBox').hidden=false;$('logout').hidden=true;$('identity').textContent='غير مسجل الدخول';alertText('انتهت الجلسة.');});
$('refresh').onclick=refresh;
async function refresh(){await handle(async()=>{
    const result=await api('/merchants');merchants=result.merchants;
    $('merchantList').replaceChildren();
    for(const m of merchants){
        const b=document.createElement('button');b.className='merchant-row'+(selected===m.id?' active':'');
        b.textContent=m.name+' — '+m.city;b.onclick=()=>loadMerchant(m.id);$('merchantList').append(b);
    }
    if(!merchants.length)paragraph($('merchantList'),'p','لا يوجد تجار.','muted');
    const reviews=await api('/reviews');pending=reviews.pending;
    const metrics=[['تجار المؤسسة',merchants.length],['التوصيات المعلقة',pending.length],['المؤسسة',me.org_id.slice(0,8)]];
    $('overviewMetrics').replaceChildren();
    for(const [label,value] of metrics){const box=document.createElement('div');box.className='metric';paragraph(box,'small',label);paragraph(box,'b',value);$('overviewMetrics').append(box);}
    await loadReviews();
    if(selected)await loadMerchant(selected);
})}
$('createForm').onsubmit=e=>{e.preventDefault();handle(async()=>{
    const data=Object.fromEntries(new FormData(e.target));
    for(const key of Object.keys(data))if(data[key]==='')delete data[key];
    const result=await api('/merchants','POST',data);
    e.target.reset();await refresh();selected=result.id;await loadMerchant(selected);alertText('تم تسجيل التاجر.');
})};
async function loadMerchant(id){await handle(async()=>{
    const result=await api('/merchants/'+id);selected=id;
    const merchant=result.merchant, detail=$('merchantDetail');detail.replaceChildren();
    paragraph(detail,'h2',merchant.name);
    paragraph(detail,'p',(merchant.category||'غير مصنف')+' — '+merchant.city,'muted');
    const toolbar=document.createElement('div');toolbar.className='toolbar no-print';
    const analyze=document.createElement('button');analyze.textContent='تحليل التسويق';
    analyze.onclick=()=>handle(async()=>{
        const value=await api('/merchants/'+id+'/analyze','POST');
        await loadMerchant(id);await loadReviews();
        alertText('تم إنشاء '+value.pending_recommendations.length+' توصيات للمراجعة.');
    });
    const print=document.createElement('button');print.textContent='طباعة الملف PDF';print.className='secondary';print.onclick=()=>window.print();
    toolbar.append(analyze,print);detail.append(toolbar);
    const score=result.assessments[0]?.result||null;
    const box=document.createElement('div');box.className='metric-grid';
    for(const [label,v] of [['الأدلة',result.evidence.length],['التقييم',score?.score??'غير متاح'],['التغطية',score?.coverage!=null?score.coverage+'%':'غير متاح']]){
        const card=document.createElement('div');card.className='metric';paragraph(card,'small',label);paragraph(card,'b',v);box.append(card);
    }detail.append(box);
    paragraph(detail,'h3','الأدلة المنشورة');
    for(const item of result.evidence){
        const div=document.createElement('div');div.className='evidence';
        const anchor=document.createElement('a');anchor.textContent=item.source_url;anchor.href=item.source_url;anchor.rel='noopener noreferrer';anchor.target='_blank';div.append(anchor);
        paragraph(div,'p',item.body||'(لم يُدخل محتوى نصي)');
        paragraph(div,'small','رُصد بتاريخ '+item.observed_at+' — '+(item.published_at?'نُشر '+item.published_at:'تاريخ النشر غير معروف'));
        detail.append(div);
    }
    if(!result.evidence.length)paragraph(detail,'p','لا توجد أدلة بعد.','muted');
    const form=document.createElement('form');form.className='stack no-print';
    const heading=paragraph(form,'h3','إضافة دليل');
    const inputs=[
      ['platform','المنصة','text'],
      ['source_url','رابط المنشور https://','url'],
      ['observed_at','تاريخ الرصد','datetime-local'],
      ['published_at','تاريخ النشر الموثق (اختياري)','datetime-local'],
      ['text','نص المنشور','text']
    ];
    for(const [name,label,type] of inputs){
        const field=document.createElement('label');field.textContent=label;
        const input=document.createElement(name==='text'?'textarea':'input');input.name=name;if(name!=='text')input.type=type;
        input.required=name==='platform'||name==='source_url'||name==='observed_at';field.append(input);form.append(field);
    }
    const send=document.createElement('button');send.textContent='حفظ الدليل';form.append(send);
    form.onsubmit=e=>{e.preventDefault();handle(async()=>{
        const body=Object.fromEntries(new FormData(form));
        body.observed_at=new Date(body.observed_at).toISOString();
        if(body.published_at)body.published_at=new Date(body.published_at).toISOString();else body.published_at=null;
        if(!body.text)body.text=null;
        await api('/merchants/'+id+'/evidence','POST',body);
        await loadMerchant(id);alertText('تم حفظ مصدر الدليل.');
    })};
    detail.append(form);
    paragraph(detail,'h3','التوصيات المحفوظة');
    for(const rec of result.recommendations){
        const div=document.createElement('div');div.className='evidence';
        paragraph(div,'b',rec.problem);
        paragraph(div,'p',rec.action);
        paragraph(div,'span',rec.status,'tag');detail.append(div);
    }
})}
async function loadReviews(){await handle(async()=>{
    const data=await api('/reviews');pending=data.pending;
    const root=$('reviews');root.replaceChildren();
    if(!pending.length){paragraph(root,'p','لا توجد توصيات بانتظار المراجعة.','muted');return}
    for(const item of pending){
        const card=document.createElement('article');
        paragraph(card,'h3',item.problem);paragraph(card,'p',item.action);
        paragraph(card,'small','التاجر: '+item.merchant_id+' — صاحب الإنشاء: '+item.created_by);
        const notes=document.createElement('textarea');notes.placeholder='ملاحظات مراجعة التوصية';notes.required=true;card.append(notes);
        const actions=document.createElement('div');actions.className='toolbar';
        for(const [decision,label] of [['approved','اعتماد'],['changes_requested','طلب تعديل'],['rejected','رفض']]){
            const b=document.createElement('button');b.textContent=label;if(decision==='rejected')b.className='danger';if(decision==='changes_requested')b.className='secondary';
            b.onclick=()=>handle(async()=>{
                if(notes.value.trim().length<3){alertText('يجب كتابة سبب القرار',true);return}
                await api('/recommendations/'+item.id+'/review','POST',{decision,notes:notes.value});
                await loadReviews();alertText('تم تسجيل قرار المراجع.');
            });
            actions.append(b);
        }
        card.append(actions);root.append(card);
    }
})}
