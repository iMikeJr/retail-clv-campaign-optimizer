'use strict';
const API=`${location.protocol}//${location.hostname}:${window.CAMPAIGN_CONFIG.apiPort}`;
const $=id=>document.getElementById(id);
const money=value=>value==null?'—':new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP',maximumFractionDigits:2}).format(value);
const money0=value=>value==null?'—':new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP',maximumFractionDigits:0}).format(value);
const integer=value=>new Intl.NumberFormat('en-GB').format(value);
const percent=(value,digits=1)=>value==null?'—':`${(100*value).toFixed(digits)}%`;
const number=(value,digits=3)=>value==null?'—':Number(value).toFixed(digits);
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names={baseline_const:'Constant baseline',baseline_recent:'Recent baseline',bgnbd:'BG/NBD',logreg:'Logistic regression',gboost:'Gradient boosting'};
const shortNames={baseline_const:'Constant',baseline_recent:'Recent',bgnbd:'BG/NBD',logreg:'Logistic',gboost:'Boosting'};
const fields=[
 {key:'B',label:'Budget (£)',max:5000,step:1,scale:1},
 {key:'K',label:'Maximum coupons',max:1000,step:1,scale:1},
 {key:'m',label:'Margin (assumption, %)',max:100,step:1,scale:100},
 {key:'tau_e',label:'Response to email (assumption, %)',max:100,step:.5,scale:100},
 {key:'tau_c',label:'Response to coupon (assumption, %)',max:100,step:1,scale:100},
 {key:'f_e',label:'Email cost (£)',max:2,step:.01,scale:1},
 {key:'f_c',label:'Coupon fixed cost (£)',max:10,step:.1,scale:1},
 {key:'d',label:'Coupon discount (%)',max:100,step:1,scale:100}
];
const helpTexts={
 sales:'Product sales after returns in the last 12 months, for customers we can identify. This is revenue, not profit.',
 customers:'Customers who bought in the last 12 months. The note below shows all retained accounts, including those who have not bought recently.',
 returns:'The share of invoices that record a return in the last 12 months. A return may cover only part of an order.',
 profit:'Extra profit we expect from the proposed campaign after its costs. It depends on our assumptions about offer responses and margin.',
 none:'Customers we propose leaving without an email or coupon. No messages are sent from this demo.',
 email:'Customers we propose sending an email to. This is a proposed action, not a confirmed purchase.',
 coupon:'Customers we propose offering a coupon to. This is a proposed action, not a confirmed purchase.',
 cost:'What we expect to spend on emails, coupon costs and discounts for this proposal. It can be less than the budget.',
 roi:'Expected extra profit divided by expected campaign cost. For example, £5.43 means £5.43 profit for each £1 spent. It depends on our assumptions.',
 customer:'The customer’s identifier in the source data.',
 action:'The action proposed for this customer under the current budget, coupon limit and assumptions.',
 days:'Days from the customer’s last recorded purchase to 9 December 2011.',
 purchases:'The number of days on which this customer bought something in the retained history. Several orders on one day count as one purchase.',
 age:'Days from the customer’s first recorded purchase to 9 December 2011. This is the length of their recorded history, not their personal age.',
 probability:'The estimated chance that the customer buys at least once in the next 90 days, even if we do nothing. It is not a guarantee.',
 spend:'What we expect the customer to spend in the next 90 days even if we do nothing.',
 gain:'Extra profit we expect from this action after its cost; it depends on our assumption of how customers respond to the offer.',
 B:'The most we are willing to spend on emails and coupons.',
 K:'A ceiling on coupons, not a target.',
 m:'The share of each pound of sales left after product costs, before campaign costs. This is an assumption, not measured from these data.',
 tau_e:'The assumed share of customers who would not otherwise buy but buy because of an email. An A/B test would help estimate this.',
 tau_c:'The assumed share of customers who would not otherwise buy but buy because of a coupon. An A/B test would help estimate this.',
 f_e:'The cost of sending one email, whether or not the customer buys.',
 f_c:'The fixed cost of offering one coupon, before any discount on a purchase.',
 d:'The share taken off the purchase price when a customer uses the coupon.',
 reset:'Restore the starting budget, coupon limit and assumptions for the proposal.',
 advanced:'Change the assumed margin, offer responses, costs and coupon discount used in the proposal.',
 backtestSpend:'What these customers actually spent in the historical period, before any campaign. It is a reference point, not a result.',
 orderValue:'The size of a typical purchase for this customer. Expected gain is the extra chance of buying created by the offer times this value times the margin, minus the cost.',
 backtestShare:'The share of all eligible customers’ actual spending covered by the selected customers in the historical check. It does not show extra sales caused by a campaign.'
};
function infoIcon(key,label){
 return `<button type="button" class="info-icon" data-help="${key}" data-tip="${esc(helpTexts[key])}" aria-label="About ${esc(label)}" aria-describedby="chart-tooltip">i</button>`;
}
function explanationIcon(text,label){
 return `<button type="button" class="info-icon" data-explanation-help data-tip="${esc(text)}" aria-label="About ${esc(label)}" aria-describedby="chart-tooltip">i</button>`;
}
function addExplanation(target,text){
 let icon=target.querySelector('[data-explanation-help]');
 if(icon){if(!icon.dataset.tip.includes(text))icon.dataset.tip+=' '+text;}
 else target.insertAdjacentHTML('beforeend',explanationIcon(text,target.textContent.trim()));
}
function simplifyNotes(){
 document.querySelectorAll('.footnote,.proposal-note').forEach(note=>{
  if(note.closest('.campaign-inputs'))return;
  const panel=note.closest('article,section,.method-body');
  const heading=note.classList.contains('proposal-note')?document.querySelector('.result-heading h3'):(panel.querySelector('h3,h2')||document.querySelector('#method-evidence h2'));
  addExplanation(heading,note.textContent.trim());note.remove();
 });
}
function installInfoIcons(){
 const add=(selector,key,label)=>document.querySelector(selector).insertAdjacentHTML('beforeend',infoIcon(key,label));
 for(const [id,key,label] of [
  ['kpi-sales','sales','Net sales'],['kpi-customers','customers','Customers'],['kpi-returns','returns','Returns'],['kpi-profit','profit','Expected profit from the campaign'],
  ['count-none','none','No contact'],['count-email','email','Email'],['count-coupon','coupon','Coupon'],
  ['cost','cost','Total expected cost'],['net-value','profit','Expected profit'],['roi','roi','Return on investment (ROI)'],
  ['backtest-spend','backtestSpend','Contacted-customer realized spend'],['backtest-share','backtestShare','Share of eligible spend']
 ])$(id).parentElement.insertAdjacentHTML('beforeend',infoIcon(key,label));
 const accountKeys=['customer','days','purchases','age','probability','spend'];
 document.querySelectorAll('#accounts-table th').forEach((th,i)=>th.insertAdjacentHTML('beforeend',infoIcon(accountKeys[i],th.textContent.replace(/[↕↑↓]/g,'').trim())));
 const selectedKeys=['customer','action','days','spend','orderValue','gain'];
 document.querySelectorAll('#selected-customers').forEach(body=>body.closest('table').querySelectorAll('th').forEach((th,i)=>th.insertAdjacentHTML('beforeend',infoIcon(selectedKeys[i],th.textContent.trim()))));
 const reset=$('reset'),actions=document.createElement('div');actions.className='heading-actions';
 reset.replaceWith(actions);actions.appendChild(reset);actions.insertAdjacentHTML('beforeend',infoIcon('reset','Reset proposal'));
 add('#advanced-assumptions>summary','advanced','Advanced assumptions');
}
const state={defaults:null,summary:null,runs:[],installed:false,ready:false,lastCampaign:null,
 monthlyCountry:'',monthlySequence:0,monthlyAbort:null,loyaltyOffset:0,loyaltyTotal:0,loyaltyYear:'2011',loyaltyHighlight:'',loyaltySequence:0,loyaltyAbort:null,
 campaignOffset:0,campaignTotal:0,listSequence:0,listAbort:null,proposalPending:true,
 productCountry:'',productSequence:0,productAbort:null,customerSequence:0,customerAbort:null,customerPage:1,customerPages:1,
 customerSort:'expected_spend_90d',customerDirection:'desc',customerTimer:null,selectedDetails:new Map(),
 campaignSequence:0,campaignAbort:null,debounce:null,backtestSequence:0,backtestAbort:null,
 methodLoaded:false,comparisonModel:'bgnbd',comparisonRows:[],comparisonSequence:0,
 sensitivitySequence:0,sensitivityAbort:null};

async function request(path,body,signal){
 const tick=performance.now();
 const response=await fetch(API+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal});
 const data=await response.json();
 if(!response.ok)throw new Error(Array.isArray(data.detail)?data.detail.map(e=>`${e.loc.slice(1).join('.')}: ${e.msg}`).join('; '):data.detail||'Local data could not be loaded');
 return {...data,http_ms:performance.now()-tick};
}
function showError(id,message){$(id).textContent=message;$(id).hidden=!message;if(message&&['products-error','customers-error','loyalty-error','returns-error'].includes(id))$('retry-api').hidden=false;}
function dateLabel(value){return new Date(value+'T12:00:00').toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});}
function monthLabel(month,partial=false){
 const d=new Date(month+'-01T12:00:00');
 const name=d.toLocaleDateString('en-GB',{month:'short'});
 return partial?`${name} (1-9)`:`${name} '${String(d.getFullYear()).slice(2)}`;
}
function shortAmount(value,currency=false){
 const abs=Math.abs(value),p=currency?'£':'';
 return abs>=1e6?`${p}${(value/1e6).toFixed(1)}m`:abs>=1000?`${p}${(value/1000).toFixed(0)}k`:`${p}${Math.round(value)}`;
}
function svgTooltip(text){return `data-tip="${esc(text)}" aria-label="${esc(text)}" tabindex="0"`;}

function renderSummary(s){
 $('asof-date').textContent=`Data as of ${dateLabel(s.as_of)}`;
 $('kpi-sales').textContent=money0(s.net_sales_12m);$('kpi-sales').title=money(s.net_sales_12m);
 $('sales-window').textContent=`${dateLabel(s.ranking_window.start)} – ${dateLabel(s.ranking_window.end)}`;
 $('kpi-customers').textContent=integer(s.active_customers_12m);
 $('total-accounts').textContent=`${integer(s.customers)} total accounts`;
 $('kpi-returns').textContent=percent(s.cancellation_rate_12m,2);
 updateHeadlineProfit(s.campaign_expected_profit,s.campaign_budget);
}
function updateHeadlineProfit(profit,budget){
 $('kpi-profit').textContent=money0(profit);$('kpi-profit').title=money(profit);
 $('campaign-investment').textContent=`invest ${money0(budget)}, expect ${money0(profit)} in profit`;
}
async function loadSales(){
 try{
  const countries=await request('/api/sales/by-country');
  showError('sales-error','');$('country-total').textContent=money0(countries.total);
  renderCountryBars(countries.rows);
  const uk=countries.rows.find(r=>r.country==='United Kingdom');
  $('uk-share').textContent=`United Kingdom: ${money0(uk.net_sales)} (${percent(uk.share,1)} of net sales)`;
  const selection=state.productCountry;
  $('product-country').innerHTML='<option value="">All countries</option>'+countries.countries.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
  $('product-country').value=countries.countries.includes(selection)?selection:'';
  await loadMonthly();
 }catch(error){showError('sales-error',error.message+' Use Retry local data to try again.');$('retry-api').hidden=false;}
}
async function loadMonthly(){
 const sequence=++state.monthlySequence;state.monthlyAbort?.abort();const controller=new AbortController();state.monthlyAbort=controller;
 $('sales-partial-note').textContent='Loading monthly sales…';
 try{
  const data=await request('/api/sales/monthly?'+new URLSearchParams({country:state.monthlyCountry}),undefined,controller.signal);
  if(sequence!==state.monthlySequence)return;
  showError('monthly-error','');
  $('monthly-country').innerHTML='<option value="">All countries</option>'+data.countries.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
  $('monthly-country').value=state.monthlyCountry;
  renderMonthly('sales-monthly-chart',data.rows,'net_sales',{label:'Monthly net sales',currency:true,color:'#28664e'});
 }catch(error){if(error.name!=='AbortError'&&sequence===state.monthlySequence){showError('monthly-error',error.message);$('sales-partial-note').textContent='Monthly sales unavailable. Change the country to retry.';}}
}
function updateChartExplanation(heading,text){
 let icon=heading.querySelector('[data-explanation-help]');
 if(!icon){addExplanation(heading,text);icon=heading.querySelector('[data-explanation-help]');icon.dataset.baseTip='';}
 else if(icon.dataset.baseTip===undefined)icon.dataset.baseTip=icon.dataset.tip;
 icon.dataset.tip=[icon.dataset.baseTip,text].filter(Boolean).join(' ');
}
function renderCountryBars(rows){
 rows=rows.filter(r=>r.country!=='United Kingdom');
 const width=620,height=rows.length*26+48,left=180,right=132,max=Math.max(1,...rows.map(r=>r.net_sales)),min=Math.min(0,...rows.map(r=>r.net_sales));
 const x=value=>left+(value-min)/(max-min)*(width-left-right);
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Net sales excluding the United Kingdom, linear scale starting at zero">`;
 rows.forEach((r,i)=>{
  const other=r.country==='Other',y=9+i*26+(other?10:0),zero=x(0),value=x(r.net_sales);
  if(other)svg+=`<line data-other-divider x1="3" x2="${width-3}" y1="${y-7}" y2="${y-7}" class="grid-line"/>`;
  const tip=`${r.country}\nNet sales ${money(r.net_sales)} · ${percent(r.share,2)} of total`;
  svg+=`<g data-country="${esc(r.country)}" ${svgTooltip(tip)}><text x="3" y="${y+13}" class="heat-label">${esc(other?'Other countries (combined)':r.country)}</text><rect x="${Math.min(zero,value)}" y="${y}" width="${Math.max(.7,Math.abs(value-zero))}" height="18" rx="2" fill="${r.net_sales<0?'#be805c':other?'#d9e3d1':i===0?'#316c50':'#a9c498'}"/><text x="${width-3}" y="${y+13}" text-anchor="end" class="heat-label">${shortAmount(r.net_sales,true)} · ${percent(r.share,1)}</text></g>`;
 });
 svg+=`<line x1="${x(0)}" x2="${x(max)}" y1="${height-25}" y2="${height-25}" class="grid-line"/><text x="${x(0)}" y="${height-8}" class="axis-label">£0</text><text x="${x(max)}" y="${height-8}" text-anchor="end" class="axis-label">${shortAmount(max,true)}</text>`;
 $('country-chart').innerHTML=svg+'</svg>';
}
function renderMonthly(id,rows,key,options){
 const partial=rows.find(r=>r.partial),complete=rows.filter(r=>!r.partial);
 const format=v=>options.percent?percent(v,2):options.currency?money(v):number(v,2);
 let note='';
 if(partial){
  const days=Number(state.summary.as_of.slice(-2));
  const totalDays=complete.reduce((n,r)=>{const [year,month]=r.month.split('-').map(Number);return n+new Date(year,month,0).getDate();},0);
  const total=k=>complete.reduce((sum,r)=>sum+(r[k]||0),0);
  // A percentage is already a rate: compare daily invoice counts, not percentage/day.
  const previous=total(key)/totalDays;
  const compact=v=>Math.abs(v)<100?money(v):`£${(v/1000).toFixed(1)}k`;
  const month=new Date(partial.month+'-01T12:00:00').toLocaleDateString('en-GB',{month:'long'});
  const shortMonth=new Date(partial.month+'-01T12:00:00').toLocaleDateString('en-GB',{month:'short'});
  note=options.percent
   ? `1–${days} ${shortMonth}: ${percent(partial[key])} of invoices were returns; previous months averaged ${percent(total('cancelled_invoices')/total('total_invoices'))}.`
   : id==='sales-monthly-chart'
    ? `${month} is incomplete (1-${days} ${shortMonth}): ${shortAmount(partial[key],true)} in ${days} days, or ${compact(partial[key]/days)} per day. An average day in the previous months was ${compact(previous)}.`
    : `1–${days} ${shortMonth}: ${options.currency?shortAmount(partial[key],true):integer(partial[key])}${options.currency?'':' return invoices'} in ${days} days (${options.currency?compact(partial[key]/days):number(partial[key]/days,1)} a day); previous months averaged ${options.currency?compact(previous):number(previous,1)} a day.`;

  const full=`${shortMonth} 1–${days}: ${format(partial[key])}. ${options.percent?'Return invoices: '+number(partial.cancelled_invoices/days,2)+' per day; previous average '+number(total('cancelled_invoices')/totalDays,2)+' per day.':format(partial[key]/days)+' per calendar day, compared with '+format(previous)+' per day.'} The previous average covers Dec 2009–Nov 2011 (${totalDays} calendar days). ${month} covers ${days} days. Charts end at November; no full December month is estimated.`;
  updateChartExplanation($(id).closest('article').querySelector('h3'),full);

 }
 rows=complete;
 const width=640,height=300,left=56,right=24,top=20,bottom=45;
 const values=rows.map(r=>r[key]).filter(v=>v!=null);
 if(!values.length){$(id).textContent='No data for this period.';return;}
 const min=Math.min(0,...values),max=Math.max(...values,options.percent ? .01 : 1)*1.09;
 const x=i=>left+i/Math.max(1,rows.length-1)*(width-left-right),y=v=>height-bottom-(v-min)/(max-min)*(height-top-bottom);
 const label=v=>options.percent?percent(v,0):shortAmount(v,options.currency);
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(options.label)}; complete months through November 2011">`;
 for(let i=0;i<=4;i++){
  const value=min+(max-min)*i/4;
  svg+=`<line x1="${left}" x2="${width-right}" y1="${y(value)}" y2="${y(value)}" class="grid-line"/><text x="${left-8}" y="${y(value)+3}" text-anchor="end" class="axis-label">${label(value)}</text>`;
 }
 if(options.bars){
  const barWidth=(width-left-right)/rows.length*.63;
  rows.forEach((r,i)=>{if(r[key]!=null)svg+=`<rect x="${x(i)-barWidth/2}" y="${Math.min(y(r[key]),y(0))}" width="${barWidth}" height="${Math.max(.5,Math.abs(y(0)-y(r[key])))}" rx="1" fill="${r.partial?'white':options.color}" ${r.partial?`stroke="${options.color}" stroke-width="2" stroke-dasharray="2 3"`:''} ${svgTooltip(`${monthLabel(r.month,r.partial)}\n${options.label}: ${options.currency?money(r[key]):integer(r[key])}`)} data-month="${r.month}" data-partial="${r.partial}"/>`;});
 }else{
  rows.forEach((r,i)=>{
   const previous=rows[i-1];
   if(previous && previous[key]!=null && r[key]!=null)svg+=`<line x1="${x(i-1)}" y1="${y(previous[key])}" x2="${x(i)}" y2="${y(r[key])}" stroke="${options.color}" stroke-width="2.3" ${r.partial||previous.partial?'stroke-dasharray="2 4"':''} data-partial="${Boolean(r.partial||previous.partial)}"/>`;
  });
  rows.forEach((r,i)=>{if(r[key]!=null)svg+=`<circle cx="${x(i)}" cy="${y(r[key])}" r="${r.partial?4.5:3}" fill="${r.partial?'white':options.color}" stroke="${r.partial?options.color:'white'}" stroke-width="${r.partial?2:1}" ${svgTooltip(`${monthLabel(r.month,r.partial)}\n${options.label}: ${options.percent?percent(r[key],2):money(r[key])}`)} data-month="${r.month}" data-partial="${r.partial}"/>`;});
 }
 rows.forEach((r,i)=>{if(i%4===0 || i===rows.length-1)svg+=`<text x="${x(i)}" y="${height-bottom+22}" text-anchor="${i===0?'start':i===rows.length-1?'end':'middle'}" class="axis-label ${r.partial?'partial-tag':''}">${esc(monthLabel(r.month,r.partial))}</text>`;});
 $(id).innerHTML=svg+'</svg>'+(id==='sales-monthly-chart'?'':`<p class="partial-note">${esc(note)}</p>`);
 if(id==='sales-monthly-chart')$('sales-partial-note').textContent=note;
}
async function loadProducts(){
 const sequence=++state.productSequence;state.productAbort?.abort();const controller=new AbortController();state.productAbort=controller;
 $('products-status').textContent='Loading product rankings…';
 try{
  const country=state.productCountry;
  const data=await request('/api/products/top?'+new URLSearchParams({country}),undefined,controller.signal);
  if(sequence!==state.productSequence)return;
  showError('products-error','');$('products-status').textContent=`${country||'All countries'} · last 12 months`;
  $('product-revenue-country').textContent=country||'All countries';$('product-units-country').textContent=country||'All countries';
  for(const [id,rows,byUnits] of [['products-revenue',data.by_revenue,false],['products-units',data.by_units,true]]){
   $(id).innerHTML=rows.length?rows.map(r=>`<tr><td class="product-name" title="${esc(r.description)}">${esc(r.description)}<span>${esc(r.stockcode)}</span></td><td>${byUnits?integer(r.units):money0(r.revenue)}</td><td>${byUnits?money0(r.revenue):integer(r.units)}</td></tr>`).join(''):'<tr><td colspan="3" class="empty-row">No products for this country.</td></tr>';
  }
 }catch(error){if(error.name!=='AbortError'){showError('products-error',error.message);$('products-status').textContent='Product rankings unavailable.';}}
}
function pageControls(prefix,total,offset,limit,busy=false){
 const pages=Math.ceil(total/limit),page=Math.floor(offset/limit)+1;
 $(`${prefix}-previous`).disabled=busy||offset===0;
 $(`${prefix}-next`).disabled=busy||offset+limit>=total;
 $(`${prefix}-go`).disabled=busy||!total;$(`${prefix}-go-form`).querySelector('button').disabled=busy||!total;
 if(busy)return;
 $(`${prefix}-count`).textContent=`Showing ${integer(total&&offset<total?offset+1:0)}–${integer(Math.min(offset+limit,total))} of ${integer(total)}`;
 $(`${prefix}-page`).textContent=pages?`Page ${page} of ${pages}`:'No matches';
 $(`${prefix}-go`).value=page;$(`${prefix}-go`).max=Math.max(1,pages);
}
async function loadHeatmap(customerID=''){
 const sequence=++state.loyaltySequence;state.loyaltyAbort?.abort();const controller=new AbortController();state.loyaltyAbort=controller;
 $('loyalty-status').textContent='Loading ranking…';pageControls('loyalty',state.loyaltyTotal,state.loyaltyOffset,10,true);
 try{
  const data=await request('/api/customers/loyalty-heatmap?'+new URLSearchParams({limit:10,offset:state.loyaltyOffset,customer_id:customerID,year:state.loyaltyYear}),undefined,controller.signal);
  if(sequence!==state.loyaltySequence)return;
  showError('loyalty-error','');state.loyaltyOffset=data.offset;state.loyaltyTotal=data.total;state.loyaltyHighlight=data.highlight_id||'';
  pageControls('loyalty',data.total,data.offset,10);
  $('loyalty-status').textContent=data.found===false?`Customer ID ${customerID} was not found.`:data.highlight_id?`Customer ${data.highlight_id} is highlighted on this page.`:'All customers ranked by loyalty · ties use customer ID';
  const width=1140,left=80,top=35,rowHeight=24,gap=4,cellWidth=(width-left-12)/data.months.length;
  const max=Math.max(1,...data.rows.flatMap(r=>r.monthly_spend));
  let svg=`<svg viewBox="0 0 ${width} ${top+data.rows.length*rowHeight+16}" role="img" aria-label="Monthly spend for customers ranked by loyalty, January to December ${state.loyaltyYear}">`;
  data.months.forEach((month,i)=>{const partial=month===state.summary.as_of.slice(0,7);svg+=`<text x="${left+i*cellWidth+cellWidth/2}" y="18" text-anchor="middle" class="heat-label ${partial?'partial-tag':''}">${esc(partial?'Dec (1-9)':new Date(month+'-01T12:00:00').toLocaleDateString('en-GB',{month:'short'}))}</text>`;});
  data.rows.forEach((r,index)=>{
   const y=top+index*rowHeight,highlight=r.customer_id===data.highlight_id;
   svg+=`<g class="loyalty-row ${highlight?'is-highlighted':''}" data-customer-id="${esc(r.customer_id)}">`;
   if(highlight)svg+=`<rect x="0" y="${y-2}" width="${width-3}" height="${rowHeight}" fill="#eef5e5" stroke="#426d3b" rx="3"/>`;
   svg+=`<text x="5" y="${y+13}" class="heat-label" ${highlight?'font-weight="700"':''}>${esc(r.customer_id)}</text>`;
   r.monthly_spend.forEach((spend,i)=>{
    const shade=spend===0?0:Math.log1p(spend)/Math.log1p(max);
    const start=[242,246,233],end=[32,85,55],color=start.map((v,j)=>Math.round(v+(end[j]-v)*shade));
    const partial=data.months[i]===state.summary.as_of.slice(0,7);
    svg+=`<rect class="heat-cell" x="${left+i*cellWidth}" y="${y}" width="${cellWidth-gap}" height="${rowHeight-gap}" rx="2" fill="rgb(${color.join(',')})" ${svgTooltip(`Customer ${r.customer_id} · ${partial?'Dec (1-9)':monthLabel(data.months[i])}\nMonthly spend ${money(spend)}`)} data-customer="${esc(r.customer_id)}" data-month="${data.months[i]}" data-spend="${spend}"/>`;
   });
   if(r.monthly_spend.every(v=>v===0))svg+=`<text class="heat-empty" x="${left+(data.months.length*cellWidth-gap)/2}" y="${y+13}" text-anchor="middle">${state.loyaltyYear==='2011'?'No purchases in the period shown (Jan-Dec 2011)':'No purchases in '+state.loyaltyYear}</text>`;
   svg+='</g>';
  });
  $('loyalty-heatmap').innerHTML=svg+'</svg>';
 }catch(error){if(error.name!=='AbortError'&&sequence===state.loyaltySequence){showError('loyalty-error',error.message);$('loyalty-status').textContent='Ranking unavailable. Use Find to retry.';}}
}
function setCustomerPagerDisabled(disabled){
 for(const id of ['first','previous','next','last'])$(`customers-${id}`).disabled=disabled;
 $('customer-go').disabled=disabled;$('customer-go-form').querySelector('button').disabled=disabled;
}
async function loadCustomers(){
 const sequence=++state.customerSequence;state.customerAbort?.abort();const controller=new AbortController();state.customerAbort=controller;
 $('customers-status').textContent='Loading accounts…';setCustomerPagerDisabled(true);
 try{
  const offset=(state.customerPage-1)*10,apiPage=Math.floor(offset/25)+1;
  const params={search:$('customer-search').value,sort:state.customerSort,direction:state.customerDirection};
  const fetchPage=page=>request('/api/customers?'+new URLSearchParams({...params,page}),undefined,controller.signal);
  const result=await fetchPage(apiPage);
  let rows=result.rows;
  if(offset%25+10>25 && apiPage<result.pages)rows=rows.concat((await fetchPage(apiPage+1)).rows);
  if(sequence!==state.customerSequence)return;
  rows=rows.slice(offset%25,offset%25+10);
  showError('customers-error','');state.customerPages=Math.ceil(result.total/10);
  $('accounts-body').innerHTML=rows.length?rows.map(c=>`<tr><td>${esc(c.customer_id)}</td><td>${integer(c.days_since_last_purchase)}</td><td>${integer(c.number_of_purchases)}</td><td>${integer(c.customer_age_days)}</td><td><span class="probability-number">${percent(c.probability_of_buying_90d,1)}</span></td><td>${money(c.expected_spend_90d)}</td></tr>`).join(''):'<tr><td colspan="6" class="empty-row">No customer IDs match your search.</td></tr>';
  $('customers-status').textContent=`${integer(result.total)} ${$('customer-search').value?'matching accounts':'total accounts'} · 10 per page`;
  $('customer-count').textContent=`Showing ${integer(result.total?offset+1:0)}–${integer(Math.min(offset+10,result.total))} of ${integer(result.total)}`;
  $('customer-page').textContent=state.customerPages?`Page ${state.customerPage} of ${state.customerPages}`:'No matches';
  setCustomerPagerDisabled(false);
  for(const id of ['first','previous'])$(`customers-${id}`).disabled=state.customerPage<=1;
  for(const id of ['next','last'])$(`customers-${id}`).disabled=state.customerPage>=state.customerPages;
  $('customer-go').max=Math.max(1,state.customerPages);$('customer-go').value=state.customerPage;
  if(!state.customerPages){$('customer-go').disabled=true;$('customer-go-form').querySelector('button').disabled=true;}
  document.querySelectorAll('#accounts-table th button[data-sort]').forEach(button=>{
   const active=button.dataset.sort===state.customerSort;
   button.parentElement.setAttribute('aria-sort',active?(state.customerDirection==='asc'?'ascending':'descending'):'none');
   button.querySelector('span').textContent=active?(state.customerDirection==='asc'?'↑':'↓'):'↕';
  });
 }catch(error){if(error.name!=='AbortError'&&sequence===state.customerSequence){showError('customers-error',error.message);$('customers-status').textContent='Accounts unavailable. Change the search or sort to retry.';}}
}
async function loadReturns(){
 try{
  const data=await request('/api/cancellations/monthly');showError('returns-error','');
  renderMonthly('returns-count-chart',data.rows,'cancelled_invoices',{label:'Return invoices',bars:true,color:'#7f9c70'});
  renderMonthly('returns-value-chart',data.rows,'cancellation_value',{label:'Value returned',bars:true,currency:true,color:'#b8845a'});
  renderMonthly('returns-rate-chart',data.rows,'cancellation_rate',{label:'Share of invoices',percent:true,color:'#b17b42'});
 }catch(error){showError('returns-error',error.message);}
}
function installInputs(){
 $('campaign-model').innerHTML=state.defaults.models.map(m=>`<option value="${m}">${shortNames[m]}</option>`).join('');
 const control=f=>`<div class="control"><div class="control-label"><span class="control-caption"><label for="input-${f.key}">${f.label}</label>${infoIcon(f.key,f.label)}</span><input id="input-${f.key}" type="number" min="0" max="${state.defaults.ranges[f.key][1]*f.scale}" step="${f.step}" aria-label="${f.label}" data-tip="${esc(helpTexts[f.key])}" aria-describedby="chart-tooltip"></div><input id="slider-${f.key}" type="range" min="0" max="${f.max}" step="${f.step}" aria-label="${f.label} slider" data-tip="${esc(helpTexts[f.key])}" aria-describedby="chart-tooltip"></div>`;
 $('primary-controls').innerHTML=fields.slice(0,2).map(control).join('');$('advanced-controls').innerHTML=fields.slice(2).map(control).join('');
 fields.forEach(f=>{
  const input=$(`input-${f.key}`),slider=$(`slider-${f.key}`);
  slider.addEventListener('input',()=>{input.value=slider.value;queueCampaign();});
  input.addEventListener('input',()=>{if(input.value!==''&&Number.isFinite(Number(input.value))){slider.max=Math.max(f.max,Number(input.value));slider.value=input.value;}queueCampaign();});
 });
 for(const id of ['campaign-model','extra-budget'])$(id).addEventListener('change',queueCampaign);
 $('reset').addEventListener('click',()=>{setDefaults();queueCampaign();});
 $('refresh-sensitivity').addEventListener('click',refreshSensitivity);
 $('comparison-run').addEventListener('change',refreshComparison);
 $('method-evidence').addEventListener('toggle',ensureMethod);
 $('product-country').addEventListener('change',()=>{state.productCountry=$('product-country').value;loadProducts();});
 $('customer-search').addEventListener('input',()=>{
  clearTimeout(state.customerTimer);state.customerAbort?.abort();state.customerSequence++;state.customerPage=1;
  setCustomerPagerDisabled(true);$('customers-status').textContent='Searching accounts…';
  state.customerTimer=setTimeout(loadCustomers,250);
 });
 document.querySelectorAll('#accounts-table th button[data-sort]').forEach(button=>button.addEventListener('click',()=>{
  if(state.customerSort===button.dataset.sort)state.customerDirection=state.customerDirection==='asc'?'desc':'asc';
  else{state.customerSort=button.dataset.sort;state.customerDirection='asc';}
  state.customerPage=1;clearTimeout(state.customerTimer);loadCustomers();
 }));
 $('customers-previous').addEventListener('click',()=>{if(state.customerPage>1){state.customerPage--;loadCustomers();}});
 $('customers-next').addEventListener('click',()=>{if(state.customerPage<state.customerPages){state.customerPage++;loadCustomers();}});
 for(const [id,page] of [['first',()=>1],['last',()=>state.customerPages]])$(`customers-${id}`).addEventListener('click',()=>{state.customerPage=page();loadCustomers();});
 $('customer-go-form').addEventListener('submit',event=>{event.preventDefault();if($('customer-go').checkValidity()){state.customerPage=Number($('customer-go').value);loadCustomers();}});
 $('monthly-country').addEventListener('change',()=>{state.monthlyCountry=$('monthly-country').value;loadMonthly();});
 $('campaign-action').addEventListener('change',()=>{state.campaignOffset=0;loadCampaignRows();});
 $('campaign-list-retry').addEventListener('click',()=>loadCampaignRows());
 $('campaign-export').addEventListener('click',exportCampaign);
 for(const prefix of ['loyalty','campaign-list']){
  const limit=prefix==='loyalty'?10:15;
  const move=offset=>{
   if(prefix==='loyalty'){state.loyaltyOffset=offset;$('loyalty-search').value='';loadHeatmap();}
   else{state.campaignOffset=offset;loadCampaignRows();}
  };
  $(`${prefix}-previous`).addEventListener('click',()=>move(Math.max(0,(prefix==='loyalty'?state.loyaltyOffset:state.campaignOffset)-limit)));
  $(`${prefix}-next`).addEventListener('click',()=>move((prefix==='loyalty'?state.loyaltyOffset:state.campaignOffset)+limit));
  $(`${prefix}-go-form`).addEventListener('submit',e=>{e.preventDefault();if($(`${prefix}-go`).checkValidity())move((Number($(`${prefix}-go`).value)-1)*limit);});
 }
 $('loyalty-year').addEventListener('change',e=>{state.loyaltyYear=e.target.value;loadHeatmap(state.loyaltyHighlight);});
 $('loyalty-search-form').addEventListener('submit',e=>{e.preventDefault();state.loyaltyOffset=0;loadHeatmap($('loyalty-search').value.trim());});
 $('loyalty-search').addEventListener('input',()=>{if(!$('loyalty-search').value){state.loyaltyOffset=0;loadHeatmap();}});
 state.installed=true;setDefaults();
}
function setDefaults(){
 for(const f of fields){$(`input-${f.key}`).value=state.defaults.defaults[f.key]*f.scale;$(`slider-${f.key}`).max=f.max;$(`slider-${f.key}`).value=state.defaults.defaults[f.key]*f.scale;}
 $('campaign-model').value='bgnbd';$('extra-budget').checked=false;
}
function readInputs(){
 const result={...state.defaults.defaults,run:'PROD',model:$('campaign-model').value,interactive:true,include_extra_100:$('extra-budget').checked};
 for(const f of fields){const input=$(`input-${f.key}`);if(!input.value.trim()||!input.checkValidity())throw new Error(`Enter a valid ${f.label.toLowerCase()}.`);result[f.key]=Number(input.value)/f.scale;}
 return result;
}
function queueCampaign(){
 clearTimeout(state.debounce);state.campaignAbort?.abort();state.campaignSequence++;
 state.proposalPending=true;state.listAbort?.abort();state.listSequence++;
 pageControls('campaign-list',state.campaignTotal,state.campaignOffset,15,true);$('campaign-export').disabled=true;$('campaign-action').disabled=true;
 state.backtestAbort?.abort();state.backtestSequence++;
 state.sensitivityAbort?.abort();state.sensitivitySequence++;$('refresh-sensitivity').disabled=false;
 $('campaign-status').textContent='Updating recommendation…';$('request-time').textContent='';
 $('campaign-investment').textContent='Updating the investment proposal…';
 $('sensitivity-status').textContent='Chart uses the previous assumptions. Select Update sensitivity to refresh it.';$('sensitivity-status').classList.add('stale');
 state.debounce=setTimeout(refreshCampaign,350);
}
async function refreshCampaign(){
 let params;
 try{params=readInputs();showError('campaign-error','');}
 catch(error){showError('campaign-error',error.message);$('campaign-status').textContent='Check proposal inputs';$('campaign-investment').textContent='Previous proposal shown — check the campaign inputs.';return;}
 const sequence=++state.campaignSequence;state.campaignAbort?.abort();const controller=new AbortController();state.campaignAbort=controller;
 $('campaign-status').textContent='Preparing the recommendation…';
 try{
  const result=await request('/api/optimize',params,controller.signal);
  if(sequence!==state.campaignSequence)return;
  state.lastCampaign=result;renderCampaign(result);
  if($('method-evidence').open)await refreshBacktest();
 }catch(error){if(error.name!=='AbortError'&&sequence===state.campaignSequence){showError('campaign-error',error.message+' Previous proposal results remain visible.');$('campaign-status').textContent='Proposal unavailable';$('campaign-investment').textContent='Previous proposal shown — local calculation unavailable.';}}
}
function renderCampaign(r){
 updateHeadlineProfit(r.net_value,r.B);
 for(const a of ['none','email','coupon'])$(`count-${a}`).textContent=integer(r.counts[a]);
 $('cost').textContent=money(r.cost);$('net-value').textContent=money(r.net_value);$('roi').textContent=r.roi==null?'—':`${money(r.roi)} profit per £1 invested`;
 $('conservative-cost').textContent=`${money(r.cost_pence/100)} reserved · ${money0(r.B)} available`;
 $('campaign-status').textContent='Recommendation ready';
 state.proposalPending=false;state.campaignOffset=0;$('campaign-action').disabled=false;
 loadCampaignRows();
 $('solver-detail').textContent=r.solver.optimality_gap!=null&&r.solver.optimality_gap<=.005?'Solved to within 0.5% of the best possible plan':'A feasible plan; the 0.5% target has not been reached';
 $('solver-detail').insertAdjacentHTML('beforeend',explanationIcon(`Status: ${r.solver.status}. Native status: ${r.solver.native_status}. Actual gap: ${percent(r.solver.optimality_gap,4)}. Target: 0.5%. The bound applies to the plan using values rounded to pennies.`,'Calculation status'));

 $('request-time').textContent=`${Math.round(r.http_ms)} ms${r.cache_hit?' · cached':''}`;
 $('greedy-improvement').textContent=money(r.baselines.ratio_greedy.improvement);
 $('marginal').textContent=r.extra_100?money(r.extra_100.marginal_net_value):'Not requested';
 $('marginal').title=r.extra_100?`${r.extra_100.solver.status}; gap ${percent(r.extra_100.solver.optimality_gap,4)}`:'Optional additional solve';
 const labels={naive:'Naive · highest expected value',email_only:'Email · every positive-value customer',ratio_greedy:'Ratio greedy · email then upgrades'};
 $('baseline-table').innerHTML=Object.entries(r.baselines).map(([key,b])=>`<tr><td>${labels[key]}</td><td>${money(b.net_value)}</td><td>${money(b.improvement)}</td><td>${b.feasible?'Yes':'No · over budget'}</td></tr>`).join('');
 $('action-economics').innerHTML=['email','coupon'].map(a=>`<tr><td>${a==='email'?'Email':'Coupon'}</td><td>${money(r.by_action[a].cost)}</td><td>${money(r.by_action[a].net_value)}</td></tr>`).join('');
}
async function loadCampaignRows(){
 const campaign=state.lastCampaign;if(!campaign||state.proposalPending)return;
 const sequence=++state.listSequence;state.listAbort?.abort();const controller=new AbortController();state.listAbort=controller;
 const action=$('campaign-action').value;
 pageControls('campaign-list',state.campaignTotal,state.campaignOffset,15,true);$('campaign-export').disabled=true;
 $('campaign-list-status').textContent='Loading campaign list…';$('selected-customers').innerHTML='<tr><td colspan="6" class="empty-row">Loading campaign list…</td></tr>';
 try{
  const data=await request('/api/campaign/customers?'+new URLSearchParams({solution_id:campaign.solution_id,action,limit:15,offset:state.campaignOffset}),undefined,controller.signal);
  if(sequence!==state.listSequence||campaign!==state.lastCampaign)return;
  state.campaignTotal=data.total;showError('campaign-list-error','');$('campaign-list-retry').hidden=true;
  pageControls('campaign-list',data.total,data.offset,15);$('campaign-export').disabled=false;
  $('campaign-list-status').textContent='Recommended actions, not confirmed responses';
  const label={coupon:'Coupon',email:'Email',none:'No contact'};
  $('selected-customers').innerHTML=data.rows.length?data.rows.map(c=>`<tr><td>${esc(c.customer_id)}</td><td><span class="action-tag ${c.action}">${label[c.action]}</span></td><td>${c.days_since_last_purchase==null?'Unavailable':integer(c.days_since_last_purchase)}</td><td>${money(c.expected_spend_90d)}</td><td>${money(c.v)}</td><td>${money(c.net_value)}</td></tr>`).join(''):'<tr><td colspan="6" class="empty-row">No customers match this action.</td></tr>';
 }catch(error){if(error.name!=='AbortError'&&sequence===state.listSequence){showError('campaign-list-error',error.message);$('campaign-list-retry').hidden=false;$('campaign-list-status').textContent='Campaign list unavailable.';$('selected-customers').innerHTML='<tr><td colspan="6" class="empty-row">Campaign list unavailable. Use Retry campaign list.</td></tr>';}}
}
async function exportCampaign(){
 if(!state.lastCampaign||state.proposalPending)return;
 const action=$('campaign-action').value,solution=state.lastCampaign.solution_id;
 $('campaign-export').disabled=true;
 try{
  const response=await fetch(API+'/api/campaign/export?'+new URLSearchParams({solution_id:solution,action}));
  if(!response.ok)throw new Error('Campaign export unavailable. Update the proposal and retry.');
  const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download=`campaign-${action}.csv`;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(error){showError('campaign-list-error',error.message);}
 finally{if(!state.proposalPending)$('campaign-export').disabled=false;}
}
async function refreshBacktest(){
 if(!state.lastCampaign)return;
 const sequence=++state.backtestSequence;state.backtestAbort?.abort();const controller=new AbortController();state.backtestAbort=controller;
 $('backtest-coverage').textContent='Loading Run A for the current proposal…';
 try{
  const result=await request('/api/optimize',{...readInputs(),run:'A',include_extra_100:false},controller.signal);
  if(sequence===state.backtestSequence)renderBacktest(result);
 }catch(error){if(error.name!=='AbortError')$('backtest-coverage').textContent=`Run A unavailable: ${error.message}`;}
}
async function ensureMethod(){
 if(!$('method-evidence').open||!state.ready)return;
 if(!state.methodLoaded){state.methodLoaded=true;await Promise.all([refreshComparison(),refreshSensitivity(),refreshBacktest()]);}
 else await refreshBacktest();
}
function installTooltips(){
 const tip=$('chart-tooltip');let pointer=null,focused=null;
 const show=(el,x,y)=>{
  tip.textContent=el.dataset.tip;tip.hidden=false;const rect=tip.getBoundingClientRect();
  tip.style.left=Math.max(5,Math.min(x+12,innerWidth-rect.width-8))+'px';
  tip.style.top=Math.max(5,Math.min(y+12,innerHeight-rect.height-8))+'px';
 };
 document.addEventListener('pointermove',e=>{
  pointer={x:e.clientX,y:e.clientY};focused=null;
  const el=e.target.closest('[data-tip]');if(el)show(el,pointer.x,pointer.y);else tip.hidden=true;
 });
 document.addEventListener('focusin',e=>{
  focused=e.target.closest('[data-tip]');pointer=null;
  if(focused){const box=focused.getBoundingClientRect();show(focused,box.left+box.width/2,box.top);}else tip.hidden=true;
 });
 document.addEventListener('pointerleave',()=>{pointer=null;tip.hidden=true;});
 document.addEventListener('focusout',()=>{focused=null;tip.hidden=true;});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')tip.hidden=true;});
 window.addEventListener('scroll',()=>{
  if(focused){const box=focused.getBoundingClientRect();show(focused,box.left+box.width/2,box.top);}
  else if(pointer){const el=document.elementFromPoint(pointer.x,pointer.y)?.closest('[data-tip]');if(el)show(el,pointer.x,pointer.y);else tip.hidden=true;}
  else tip.hidden=true;
 },{passive:true});
}
async function start(){
 try{
  const [summary,defaults,runs]=await Promise.all([request('/api/exec/summary'),request('/api/defaults'),request('/api/runs')]);
  state.summary=summary;state.defaults=defaults;state.runs=runs.runs;renderSummary(summary);
  showError('global-error','');$('retry-api').hidden=true;
  if(!state.installed)installInputs();
  state.ready=true;
  await Promise.all([loadSales(),loadProducts(),loadHeatmap(),loadCustomers(),loadReturns(),refreshCampaign()]);
  await ensureMethod();
 }catch(error){showError('global-error',`Local data is unavailable. ${error.message}`);$('retry-api').hidden=false;}
}

// Technical evidence stays inside the collapsed Method and evidence section.
function renderBacktest(r) {
  const b=r.backtest;
  if(!b) { $('backtest-coverage').textContent='Realized outcomes are unavailable.'; return; }
  $('backtest-spend').textContent=money(b.selected_realized_spend); $('backtest-share').textContent=percent(b.share,2);
  const selected=r.counts.email+r.counts.coupon,total=b.groups.all_eligible.customers;
  $('backtest-coverage').textContent=`${integer(selected)} of ${integer(total)} customers selected (${percent(selected/total,2)}).`;
  const labels={coupon:'Coupon',email_only:'Email only',none:'None',all_eligible:'All eligible customers'};
  $('backtest-table').innerHTML=Object.entries(b.groups).map(([k,g])=>`<tr class="${k==='all_eligible'?'all-eligible':''}"><td>${labels[k]}</td><td>${integer(g.customers)}</td><td>${percent(g.mean_predicted_pi,2)}</td><td>${percent(g.observed_purchase_rate,2)}</td><td>${money(g.mean_realized_spend)}</td><td title="Among buyers: ${money(g.mean_predicted_order_value_buyers)}">${money(g.mean_predicted_order_value)}</td><td title="${integer(g.buyers)} buyers; mean of customer spend / purchase occasions">${money(g.mean_realized_order_value_buyers)}</td></tr>`).join('');
}
async function refreshComparison() {
  const sequence=++state.comparisonSequence;
  const run=$('comparison-run').value;
  const metadata=state.runs.find(r=>r.run_name===run);
  if(metadata) $('comparison-period').textContent=`${metadata.window_days}-day holdout · ${dateLabel(metadata.test_cutoff)} → ${dateLabel(metadata.horizon_end)}`;
  try {
    const metrics=await request(`/api/metrics?run=${encodeURIComponent(run)}`);
    if(sequence!==state.comparisonSequence) return;
    state.comparisonRows=metrics.models;
    renderModelTable(); await refreshCalibration();
  } catch(error) { $('model-table').innerHTML=`<tr><td colspan="7">${esc(error.message)}</td></tr>`; }
}
function renderModelTable() {
  $('model-table').innerHTML=state.comparisonRows.map(r=>`<tr class="${r.model===state.comparisonModel?'selected-model':''}"><td><button class="model-button" data-model="${r.model}" aria-pressed="${r.model===state.comparisonModel}">${names[r.model]}</button></td><td>${number(r.roc_auc)}</td><td>${number(r.average_precision)}</td><td>${number(r.log_loss)}</td><td>${number(r.brier_score)}</td><td>${number(r.lift_top_10pct,2)}</td><td>${percent(r.revenue_capture_top_20pct)}</td></tr>`).join('');
  $('model-table').querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{state.comparisonModel=button.dataset.model;renderModelTable();refreshCalibration();}));
}
async function refreshCalibration() {
  const run=$('comparison-run').value,model=state.comparisonModel;
  $('calibration-model').textContent=shortNames[model];
  try {
    const result=await request(`/api/calibration?run=${encodeURIComponent(run)}&model=${encodeURIComponent(model)}`);
    if(run!==$('comparison-run').value || model!==state.comparisonModel) return;
    drawChart('calibration-chart',[{color:'#25634c',points:result.bins.map(b=>({x:b.calib_mean_pred,y:b.calib_observed_rate,tip:`${integer(b.calib_n)} customers · predicted ${percent(b.calib_mean_pred)} · observed ${percent(b.calib_observed_rate)}`}))}],
              {xLabel:'Predicted probability',yLabel:'Observed purchase rate',percent:true,calibration:true});
  } catch(error) { $('calibration-chart').textContent=error.message; }
}
async function refreshSensitivity() {
  let parameters;
  try { parameters={...readInputs(),include_extra_100:false,interactive:true,...state.defaults.sensitivity_grid}; }
  catch(error) { $('sensitivity-status').textContent=error.message; return; }
  const sequence=++state.sensitivitySequence;
  state.sensitivityAbort?.abort();const controller=new AbortController();state.sensitivityAbort=controller;
  $('refresh-sensitivity').disabled=true;
  $('sensitivity-status').classList.remove('stale'); $('sensitivity-status').textContent='Calculating sensitivity… existing curves stay visible.';
  try {
    const result=await request('/api/sensitivity',parameters,controller.signal);
    if(sequence!==state.sensitivitySequence) return;
    const colors=['#527b9a','#25634c','#cb823c'];
    const curves=parameters.tau_c_values.map((tau,i)=>({color:colors[i%colors.length],points:result.points.filter(p=>p.tau_c===tau).sort((a,b)=>a.B-b.B).map(p=>({x:p.B,y:p.net_value,tip:`Budget ${money(p.B)} · net ${money(p.net_value)} · gap ${percent(p.solver.optimality_gap,4)}`}))}));
    drawChart('sensitivity-chart',curves,{xLabel:'Budget (£)',yLabel:'Expected net value (£)',percent:false,calibration:false});
    $('sensitivity-legend').innerHTML=parameters.tau_c_values.map((tau,i)=>`<span><i style="background:${colors[i%colors.length]}"></i>Coupon response ${percent(tau,0)}</span>`).join('');
    const gaps=result.points.map(p=>p.solver.optimality_gap).filter(g=>g!=null);
    $('sensitivity-status').textContent=`${result.grid_points} comparisons · current assumptions`;
    $('sensitivity-status').dataset.tip=`${result.solves} new calculations; ${Math.round(result.http_ms)} ms; maximum gap ${percent(Math.max(...gaps),3)}.`;
    $('sensitivity-status').tabIndex=0;
  } catch(error) { if(error.name!=='AbortError') $('sensitivity-status').textContent=`Sensitivity unavailable: ${error.message}`; }
  finally { if(sequence===state.sensitivitySequence) $('refresh-sensitivity').disabled=false; }
}
function drawChart(id,series,options) {
  const width=options.calibration?320:500,height=options.calibration?220:250,left=options.calibration?48:65,right=20,top=25,bottom=43;
  const points=series.flatMap(s=>s.points);
  if(!points.length) { $(id).textContent='No chart data available.'; return; }
  const xmax=options.calibration?1:Math.max(...points.map(p=>p.x),1),xmin=0;
  let ymin=options.calibration?0:Math.min(0,...points.map(p=>p.y)),ymax=options.calibration?1:Math.max(1,...points.map(p=>p.y))*1.05;
  if(ymax===ymin) ymax=ymin+1;
  const x=value=>left+(value-xmin)/(xmax-xmin)*(width-left-right),y=value=>height-bottom-(value-ymin)/(ymax-ymin)*(height-top-bottom);
  const label=value=>options.percent?`${Math.round(value*100)}%`:Math.abs(value)>=1000?`${(value/1000).toFixed(1)}k`:Math.round(value);
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(options.yLabel)} versus ${esc(options.xLabel)}"><text x="${left}" y="12" class="chart-title">${esc(options.yLabel)}</text>`;
  for(let i=0;i<=4;i++) {
    const vy=ymin+(ymax-ymin)*i/4,vx=xmax*i/4;
    svg+=`<line x1="${left}" x2="${width-right}" y1="${y(vy)}" y2="${y(vy)}" class="grid-line"/><text x="${left-8}" y="${y(vy)+3}" text-anchor="end" class="axis-label">${label(vy)}</text><text x="${x(vx)}" y="${height-bottom+17}" text-anchor="middle" class="axis-label">${label(vx)}</text>`;
  }
  if(options.calibration) svg+=`<line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="#a4b2a6" stroke-dasharray="4 4"/>`;
  for(const s of series) {
    svg+=`<polyline points="${s.points.map(p=>`${x(p.x)},${y(p.y)}`).join(' ')}" fill="none" stroke="${s.color}" stroke-width="2"/>`;
    for(const p of s.points) svg+=`<circle cx="${x(p.x)}" cy="${y(p.y)}" r="${options.calibration?3.7:3}" fill="${s.color}" stroke="white" stroke-width="1"><title>${esc(p.tip)}</title></circle>`;
  }
  svg+=`<text x="${left+(width-left-right)/2}" y="${height-4}" text-anchor="middle" class="axis-label">${esc(options.xLabel)}</text></svg>`;
  $(id).innerHTML=svg;
}

$('retry-api').addEventListener('click',start);
installInfoIcons();
simplifyNotes();
installTooltips();
start();
