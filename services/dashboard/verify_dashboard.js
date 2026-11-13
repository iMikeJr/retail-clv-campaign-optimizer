// Playwright CLI run-code function. Run from the repository root; no test dependency.
async (page) => {
 const errors=[],external=[],requests=[],interactions=[];
 const check=(condition,message)=>{if(!condition)throw new Error(message);};
 const money=v=>new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP',maximumFractionDigits:2}).format(v);
 const money0=v=>new Intl.NumberFormat('en-GB',{style:'currency',currency:'GBP',maximumFractionDigits:0}).format(v);
 page.on('pageerror',error=>errors.push(error.message));
 page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
 page.on('request',request=>requests.push(request.url()));
 await page.route('**/*',route=>{
  const url=new URL(route.request().url());
  if(['127.0.0.1','localhost'].includes(url.hostname))return route.continue();
  external.push(url.href);return route.abort();
 });
 await page.setViewportSize({width:1366,height:900});
 await page.goto('http://127.0.0.1:8080');
 await page.waitForFunction(()=>document.querySelectorAll('#accounts-body tr').length===10 && document.querySelectorAll('.heat-cell').length===120 && document.querySelectorAll('#selected-customers tr').length===15 && document.querySelector('#returns-rate-chart svg'));
 check(await page.locator('#kpi-customers').textContent()==='4,260','Customers KPI must show active customers');
 check(await page.locator('#total-accounts').textContent()==='5,851 total accounts','Total-account footnote missing');
 check(await page.locator('#asof-date').textContent()==='Data as of 09 Dec 2011','As-of label incorrect');
 check(await page.getByText('Sales to identified customers only (about 77% of lines)',{exact:true}).isVisible(),'Population note missing');
 check(await page.locator('#campaign-investment').textContent()==='invest £1,682, expect £9,123 in profit','Investment/profit framing incorrect');
 check(!await page.locator('#method-evidence').evaluate(el=>el.open),'Method must start collapsed');
 check(!await page.locator('#advanced-assumptions').evaluate(el=>el.open),'Advanced assumptions must start collapsed');
 const aboveFold=await page.evaluate(()=>{
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),parts=[];
  while(walker.nextNode()){
   const node=walker.currentNode;
   if(!node.textContent.trim()||node.parentElement.closest('script,style'))continue;
   const range=document.createRange();range.selectNodeContents(node);const box=range.getBoundingClientRect();
   if(box.width&&box.height&&box.bottom>0&&box.top<innerHeight&&getComputedStyle(node.parentElement).visibility!=='hidden')parts.push(node.textContent.trim());
  }
  return parts.join(' ');
 });
 check(!/\b(AUC|pi|tau|solver|gap)\b|log loss/i.test(aboveFold),'Technical vocabulary above the fold');
 for(const id of ['sales','customers','returns','campaign'])check(await page.locator('#'+id).count()===1,'Missing section '+id);
 check(await page.locator('#returns h2').count()===1,'Returns heading incorrect');
 check(await page.getByRole('heading',{name:'Cancellations',exact:true}).count()===0,'Old panel label remains');
 check((await page.locator('#loyalty-heatmap').textContent()).includes('Dec (1-9)'),'Heatmap partial month missing');
 check(await page.locator('#country-chart svg g').count()===10,'Expected other top countries plus Other');
 check(await page.locator('#products-revenue tr').count()===10 && await page.locator('#products-units tr').count()===10,'Product top tens incomplete');
 const partialStyles={};
 for(const id of ['sales-monthly-chart','returns-count-chart','returns-value-chart','returns-rate-chart']){
  check(await page.locator('#'+id+' [data-month="2011-12"]').count()===0,id+' must exclude partial December from chart');
  check(await page.locator('#'+id+' [data-month="2011-11"]').count()===1,id+' must end in November');
  check((await page.locator(id==='sales-monthly-chart'?'#sales-partial-note':'#'+id+' .partial-note').textContent()).includes('previous'),id+' must compare previous months');
  partialStyles[id]='Complete months through November; December value and daily comparison in note';
 }
 const uk=await page.evaluate(async()=>(await (await fetch('http://127.0.0.1:8000/api/sales/by-country')).json()).rows.find(r=>r.country==='United Kingdom'));
 check(await page.locator('#uk-share').textContent()===`United Kingdom: ${money0(uk.net_sales)} (${(100*uk.share).toFixed(1)}% of net sales)`,'UK headline mismatch');
 check(!(await page.locator('#country-chart').textContent()).includes('United Kingdom'),'UK must be excluded from bars');
 const bars=await page.locator('#country-chart svg g rect').evaluateAll(els=>els.map(el=>({x:+el.getAttribute('x'),width:+el.getAttribute('width')})));
 check(bars.every(b=>b.x===180),'Country bars must start at zero');
 check(await page.locator('.assumption-banner').count()===0,'Warning banner remains');
 check(await page.locator('#campaign .assumption-note').count()===1,'Inline assumption note missing');
 check(await page.locator('#kpi-sales').locator('..').textContent().then(t=>t.includes('Product revenue after returns. Revenue is not profit.')),'Revenue note must be inside sales card');
 check(await page.locator('.scenario-card .scenario-tag').textContent()==='Scenario (assumption-based)','Scenario tag missing');
 check(await page.locator('.scenario-card').evaluate(el=>getComputedStyle(el).borderTopStyle)==='dashed','Scenario card border must be dashed');
 check(await page.locator('#roi').textContent()==='£5.43 profit per £1 invested','ROI wording mismatch');
 check(await page.locator('.probability-track').count()===0&&await page.locator('.probability-number').count()===10,'Percentages must remain without saturated bars');
 check((await page.locator('button[data-sort=customer_age_days]').textContent()).includes('Time as customer (days)'),'Time as customer label missing');
 check(await page.locator('#product-country').inputValue()===''&&await page.locator('#product-revenue-country').textContent()==='All countries','Product selector must start at All countries');
 check(await page.locator('[data-other-divider]').count()===1,'Combined countries divider missing');
 check((await page.locator('#country-chart').textContent()).includes('Other countries (combined)'),'Combined countries label missing');
 check(!(await page.locator('#campaign').textContent()).includes('Days since last purchase and expected spend use PROD/BG-NBD'),'Removed footnote remains');
 // Independently reproduce December notes from HTTP values and calendar-day counts.
 const partialComparisons=await page.evaluate(async()=>{
  const sales=await (await fetch('http://127.0.0.1:8000/api/sales/monthly')).json();
  const returns=await (await fetch('http://127.0.0.1:8000/api/cancellations/monthly')).json();
  return [['sales-monthly-chart',sales.rows,'net_sales'],['returns-count-chart',returns.rows,'cancelled_invoices'],['returns-value-chart',returns.rows,'cancellation_value'],['returns-rate-chart',returns.rows,'cancellation_rate']].map(([id,rows,key])=>{
   const partial=rows.find(r=>r.partial),full=rows.filter(r=>!r.partial);
   const days=full.reduce((n,r)=>{const [y,m]=r.month.split('-').map(Number);return n+new Date(y,m,0).getDate();},0);
   const numerator=key==='cancellation_rate'?'cancelled_invoices':key;
   return {id,value:partial[key],partial_daily:partial[numerator]/9,previous_daily:full.reduce((sum,r)=>sum+r[numerator],0)/days,previous_days:days,note:document.querySelector(id==='sales-monthly-chart'?'#sales-partial-note':'#'+id+' .partial-note').textContent};
  });
 });
 for(const comparison of partialComparisons){
  const currency=['sales-monthly-chart','returns-value-chart'].includes(comparison.id);
  if(comparison.id==='returns-rate-chart'){
   check(comparison.note.includes('14.9%')&&comparison.note.includes('16.6%'),'Return-share comparison incorrect');
  }else{
   const format=v=>currency?`£${(v/1000).toFixed(1)}k`:v.toFixed(1);
   check(comparison.note.includes(format(comparison.partial_daily))&&comparison.note.includes(format(comparison.previous_daily)),'Incorrect daily comparison '+comparison.id);
  }
  if(comparison.id!=='sales-monthly-chart')check(comparison.note.length<160,'Chart comparison is too long '+comparison.id);
 }
 // Every help icon supports both pointer hover and actual keyboard tab focus.
 await page.locator('#advanced-assumptions>summary').click();

 const tooltipTexts=[];
 const icons=page.locator('.info-icon:visible');
 for(let i=0;i<await icons.count();i++){
  const icon=icons.nth(i),text=await icon.getAttribute('data-tip');
  await icon.hover();check(await page.locator('#chart-tooltip').isVisible()&&await page.locator('#chart-tooltip').textContent()===text,'Help hover failed '+i);
  await icon.focus();await page.keyboard.press('Shift+Tab');await page.keyboard.press('Tab');
  check(await icon.evaluate(el=>el===document.activeElement),'Help icon not reachable with keyboard '+i);
  check(await page.locator('#chart-tooltip').isVisible()&&await page.locator('#chart-tooltip').textContent()===text,'Help focus failed '+i);
  await page.keyboard.press('Escape');check(!await page.locator('#chart-tooltip').isVisible(),'Escape should dismiss tooltip');
  tooltipTexts.push({label:await icon.getAttribute('aria-label'),text});
 }
 check(tooltipTexts.length>=32,'Every card, header and control must have help');
 check(await page.locator('#accounts-table .info-icon').first().evaluate(el=>getComputedStyle(el).borderTopStyle)==='solid','Header help must retain its visible icon border');
 for(const input of await page.locator('#primary-controls input, #advanced-controls input').all()){
  const text=await input.getAttribute('data-tip');
  await input.hover();check(await page.locator('#chart-tooltip').textContent()===text,'Control hover help failed');
  await input.focus();check(await page.locator('#chart-tooltip').isVisible()&&await page.locator('#chart-tooltip').textContent()===text,'Control keyboard help failed');
 }

 // The two hidden historical cards are checked after evidence opens below.
 await page.locator('#advanced-assumptions>summary').click();
 await page.mouse.move(0,0);
 await page.evaluate(()=>{document.activeElement.blur();window.scrollTo({top:0,behavior:'instant'});});
 await page.waitForFunction(()=>!document.getElementById('selected-customers').textContent.includes('Loading'));
 const selectedContext=await page.evaluate(async()=>{
  const rows=[...document.querySelectorAll('#selected-customers tr')].map(tr=>[...tr.children].map(td=>td.textContent));
  return await Promise.all(rows.map(async cells=>({cells,customer:(await (await fetch('http://127.0.0.1:8000/api/customers?search='+cells[0])).json()).rows.find(c=>c.customer_id===cells[0])})));
 });
 for(const {cells,customer} of selectedContext){
  check(cells.length===6 && customer,'Selected customer context missing');
  check(cells[2]===new Intl.NumberFormat('en-GB').format(customer.days_since_last_purchase),'Selected recency mismatch');
  check(cells[3]===money(customer.expected_spend_90d),'Selected spend mismatch');
 }
 const economics=await page.evaluate(async()=>{
  const r=await (await fetch('http://127.0.0.1:8000/api/optimize',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
  return {profit:r.net_value,greedy:r.baselines.ratio_greedy.net_value,improvement:r.baselines.ratio_greedy.improvement,rows:r.top_selected.slice(0,3).map(c=>({id:c.customer_id,margin:r.assumptions.m,v:c.v,pi:c.pi,tau:c.action==='coupon'?r.assumptions.tau_c:r.assumptions.tau_e,incremental_probability:(c.action==='coupon'?r.assumptions.tau_c:r.assumptions.tau_e)*(1-c.pi),cost:c.cost,gain:c.net_value}))};
 });
 for(const row of economics.rows){
  const calculated=row.margin*row.v*row.incremental_probability-row.cost;
  check(money(calculated)===money(row.gain),'Expected gain arithmetic differs by a penny '+row.id);
  const cells=selectedContext.find(c=>c.cells[0]===row.id).cells;
  check(cells[4]===money(row.v)&&cells[5]===money(row.gain),'Typical value or gain differs from optimizer '+row.id);
 }
 await page.screenshot({path:'docs/screenshots/dashboard-overview.png'});
 await page.screenshot({path:'docs/screenshots/dashboard-full-page.png',fullPage:true});
 async function getChange(action,path,predicate,label){
  const waiting=page.waitForResponse(response=>{
   const url=new URL(response.url());
   return url.pathname===path&&predicate(url.searchParams,response.request());
  },{timeout:30000});
  const start=Date.now();await action();const response=await waiting;const data=await response.json();
  check(response.status()===200,label+' failed');
  interactions.push({label,milliseconds:Date.now()-start,status:response.status(),cache_hit:data.cache_hit,solver:data.solver});
  return data;
 }
 // New controls: monthly series, loyalty paging/search, campaign filters/CSV.
 const yBefore=await page.locator('#sales-monthly-chart .axis-label').allTextContents();
 const monthlyFrance=await getChange(()=>page.locator('#monthly-country').selectOption('France'),'/api/sales/monthly',p=>p.get('country')==='France','Monthly France');
 await page.waitForFunction(()=>!document.getElementById('sales-partial-note').textContent.includes('Loading'));
 const decFrance=monthlyFrance.rows.find(r=>r.partial);
 check((await page.locator('#sales-partial-note').textContent()).includes(`£${(decFrance.net_sales/1000).toFixed(0)}k`),'Filtered December note did not follow France');
 check(JSON.stringify(await page.locator('#sales-monthly-chart .axis-label').allTextContents())!==JSON.stringify(yBefore),'Monthly y-axis did not rescale');
 check(await page.locator('#product-country').inputValue()==='','Monthly filter must leave product filter independent');
 // Retry local data must preserve the selected country and its actual series.
 await page.locator('#retry-api').evaluate(el=>el.hidden=false);
 await getChange(()=>page.locator('#retry-api').click(),'/api/sales/monthly',p=>p.get('country')==='France','Reload local data keeps monthly country');
 await page.waitForFunction(()=>document.getElementById('monthly-country').value==='France'&&!document.getElementById('sales-partial-note').textContent.includes('Loading'));
 check((await page.locator('#sales-partial-note').textContent()).includes(`£${(decFrance.net_sales/1000).toFixed(0)}k`),'Reload changed the chart without changing its country');
 await page.locator('#sales').screenshot({path:'docs/screenshots/dashboard-sales-france.png'});
 await getChange(()=>page.locator('#monthly-country').selectOption(''),'/api/sales/monthly',p=>p.get('country')==='','Monthly all countries');
 await page.waitForFunction(()=>document.getElementById('sales-partial-note').textContent.includes('£339k'));
 const loyaltyInitial=await page.evaluate(async()=>await (await fetch('http://127.0.0.1:8000/api/customers/loyalty-heatmap')).json());
 check(JSON.stringify(await page.locator('.loyalty-row').evaluateAll(els=>els.map(el=>el.dataset.customerId)))===JSON.stringify(loyaltyInitial.rows.map(r=>r.customer_id)),'Default loyalty page differs from existing top ten');
 await getChange(()=>page.locator('#loyalty-next').click(),'/api/customers/loyalty-heatmap',p=>p.get('offset')==='10','Loyalty next page');
 await page.waitForFunction(()=>document.getElementById('loyalty-go').value==='2');
 await getChange(()=>page.locator('#loyalty-previous').click(),'/api/customers/loyalty-heatmap',p=>p.get('offset')==='0','Loyalty previous page');
 await page.waitForFunction(()=>document.getElementById('loyalty-go').value==='1');
 await page.locator('#loyalty-go').fill('4');
 await getChange(()=>page.locator('#loyalty-go-form button').click(),'/api/customers/loyalty-heatmap',p=>p.get('offset')==='30','Loyalty go to page');
 await page.waitForFunction(()=>document.getElementById('loyalty-go').value==='4');
 await page.locator('#loyalty-search').fill('14500');
 const foundLoyalty=await getChange(()=>page.locator('#loyalty-search-form button').click(),'/api/customers/loyalty-heatmap',p=>p.get('customer_id')==='14500','Find loyalty customer beyond top 25');
 await page.waitForFunction(()=>document.querySelector('.loyalty-row.is-highlighted')?.dataset.customerId==='14500');
 check(await page.locator('#loyalty-go').inputValue()===String(Math.floor(foundLoyalty.offset/10)+1),'Loyalty search did not jump to its ranked page');
 await page.locator('#loyalty-heatmap').locator('..').screenshot({path:'docs/screenshots/dashboard-loyalty-search.png'});
 await page.locator('#loyalty-search').fill('999999');
 await getChange(()=>page.locator('#loyalty-search-form button').click(),'/api/customers/loyalty-heatmap',p=>p.get('customer_id')==='999999','Unknown loyalty customer');
 await page.waitForFunction(()=>document.getElementById('loyalty-status').textContent.includes('not found'));
 check(await page.locator('.loyalty-row.is-highlighted').count()===0,'Unknown customer left a highlight');
 await page.locator('#loyalty-heatmap').locator('..').screenshot({path:'docs/screenshots/dashboard-loyalty-not-found.png'});
 await getChange(()=>page.locator('#loyalty-search').fill(''),'/api/customers/loyalty-heatmap',p=>p.get('offset')==='0','Clear loyalty search');
 await page.waitForFunction(()=>document.getElementById('loyalty-go').value==='1');
 const lastLoyaltyPage=Math.ceil(loyaltyInitial.total/10);
 await page.locator('#loyalty-go').fill(String(lastLoyaltyPage));
 await getChange(()=>page.locator('#loyalty-go-form button').click(),'/api/customers/loyalty-heatmap',p=>p.get('offset')===String((lastLoyaltyPage-1)*10),'Last loyalty page');
 await page.waitForFunction(()=>document.getElementById('loyalty-next').disabled);
 check(await page.locator('.loyalty-row').count()===loyaltyInitial.total%10,'Last loyalty page is incomplete or duplicated');
 await page.locator('#loyalty-go').fill('1');
 await getChange(()=>page.locator('#loyalty-go-form button').click(),'/api/customers/loyalty-heatmap',p=>p.get('offset')==='0','Restore first loyalty page');
 // Lapsed customer 13902: empty row shows the muted message, cells stay focusable, highlight and paging still work.
 await page.locator('#loyalty-search').fill('13902');
 const lapsed=await getChange(()=>page.locator('#loyalty-search-form button').click(),'/api/customers/loyalty-heatmap',p=>p.get('customer_id')==='13902','Find lapsed loyalty customer');
 await page.waitForFunction(()=>document.querySelector('.loyalty-row.is-highlighted')?.dataset.customerId==='13902');
 const lapsedRow=page.locator('.loyalty-row.is-highlighted');
 check((await lapsedRow.locator('.heat-empty').textContent())==='No purchases in the period shown (Jan-Dec 2011)','Empty-row message missing for customer 13902');
 check(await lapsedRow.locator('.heat-cell').count()===12,'Empty row lost its 12 cells');
 check(await lapsedRow.locator('.heat-cell').first().getAttribute('tabindex')==='0','Empty-row cells are not keyboard focusable');
 const rowBoxes=await page.locator('.loyalty-row').evaluateAll(els=>els.map(el=>{const b=el.querySelector('.heat-cell').getBoundingClientRect();return [Math.round(b.width),Math.round(b.height)].join('x');}));
 check(new Set(rowBoxes).size===1,'Empty row is not aligned with the others');
 check(await page.locator('#loyalty-go').inputValue()===String(Math.floor(lapsed.offset/10)+1),'Lapsed search did not jump to its ranked page');
 await page.locator('#loyalty-heatmap').locator('..').screenshot({path:'docs/screenshots/dashboard-loyalty-lapsed.png'});
 await getChange(()=>page.locator('#loyalty-next').click(),'/api/customers/loyalty-heatmap',p=>p.get('offset')===String(lapsed.offset+10),'Next page after lapsed customer');
 await page.locator('#loyalty-search').fill('');
 await getChange(()=>page.locator('#loyalty-search').dispatchEvent('input'),'/api/customers/loyalty-heatmap',p=>p.get('offset')==='0','Reset after lapsed customer');
 await page.waitForFunction(()=>document.getElementById('loyalty-go').value==='1');
 // Period selector: only the month columns change; page, search and highlight are kept.
 check(await page.locator('#loyalty-year').inputValue()==='2011','Period must default to 2011');
 await page.locator('#loyalty-search').fill('13902');
 await getChange(()=>page.locator('#loyalty-search-form button').click(),'/api/customers/loyalty-heatmap',p=>p.get('customer_id')==='13902'&&p.get('year')==='2011','Find 13902 for period change');
 await page.waitForFunction(()=>document.querySelector('.loyalty-row.is-highlighted')?.dataset.customerId==='13902');
 const pageBefore=await page.locator('#loyalty-go').inputValue();
 const idsBefore=await page.locator('.loyalty-row').evaluateAll(els=>els.map(el=>el.dataset.customerId));
 await getChange(()=>page.locator('#loyalty-year').selectOption('2010'),'/api/customers/loyalty-heatmap',p=>p.get('year')==='2010'&&p.get('customer_id')==='13902','Switch period to 2010');
 await page.waitForFunction(()=>document.querySelector('.heat-cell')?.dataset.month==='2010-01');
 check(await page.locator('#loyalty-go').inputValue()===pageBefore,'Period change moved the loyalty page');
 check(JSON.stringify(await page.locator('.loyalty-row').evaluateAll(els=>els.map(el=>el.dataset.customerId)))===JSON.stringify(idsBefore),'Period change reordered customers');
 check(await page.locator('.loyalty-row.is-highlighted').getAttribute('data-customer-id')==='13902','Highlight lost on period change');
 check(await page.locator('.loyalty-row.is-highlighted .heat-empty').count()===0,'13902 should have purchases in 2010');
 check(await page.locator('.loyalty-row.is-highlighted .heat-cell').evaluateAll(cells=>cells.some(c=>Number(c.dataset.spend)>0)),'13902 shows no 2010 spend');
 check(!(await page.locator('#loyalty-heatmap').textContent()).includes('Dec (1-9)'),'2010 must not show the partial December label');
 check((await page.locator('#loyalty-heatmap .heat-label').allTextContents()).includes('Dec'),'2010 Dec label missing');
 await page.locator('#loyalty-heatmap').locator('..').screenshot({path:'docs/screenshots/dashboard-loyalty-2010.png'});
 await page.locator('#loyalty-search').fill('12362');
 await getChange(()=>page.locator('#loyalty-search-form button').click(),'/api/customers/loyalty-heatmap',p=>p.get('customer_id')==='12362'&&p.get('year')==='2010','Find customer with no 2010 purchases');
 await page.waitForFunction(()=>document.querySelector('.loyalty-row.is-highlighted')?.dataset.customerId==='12362');
 check((await page.locator('.loyalty-row.is-highlighted .heat-empty').textContent())==='No purchases in 2010','2010 empty-row message wrong');
 await page.locator('#loyalty-heatmap').locator('..').screenshot({path:'docs/screenshots/dashboard-loyalty-2010-empty.png'});
 await getChange(()=>page.locator('#loyalty-next').click(),'/api/customers/loyalty-heatmap',p=>p.get('year')==='2010'&&p.get('offset')!=='0','Next page keeps 2010');
 await getChange(()=>page.locator('#loyalty-year').selectOption('2011'),'/api/customers/loyalty-heatmap',p=>p.get('year')==='2011','Restore period 2011');
 await page.waitForFunction(()=>document.querySelector('.heat-cell')?.dataset.month==='2011-01');
 check((await page.locator('#loyalty-heatmap').textContent()).includes('Dec (1-9)'),'2011 partial label missing after restore');
 await page.locator('#loyalty-search').fill('');
 await getChange(()=>page.locator('#loyalty-search').dispatchEvent('input'),'/api/customers/loyalty-heatmap',p=>p.get('offset')==='0','Reset after period checks');
 await page.waitForFunction(()=>document.getElementById('loyalty-go').value==='1');
 await page.waitForFunction(()=>document.querySelectorAll('.heat-cell').length===120);
 check(await page.locator('#campaign-action').inputValue()==='coupon','Campaign filter must default to Coupon');
 await getChange(()=>page.locator('#campaign-list-next').click(),'/api/campaign/customers',p=>p.get('offset')==='15','Campaign next page');
 await page.waitForFunction(()=>document.getElementById('campaign-list-go').value==='2');
 await getChange(()=>page.locator('#campaign-list-previous').click(),'/api/campaign/customers',p=>p.get('offset')==='0','Campaign previous page');
 await page.waitForFunction(()=>document.getElementById('campaign-list-go').value==='1');
 await page.locator('#campaign-list-go').fill('3');
 await getChange(()=>page.locator('#campaign-list-go-form button').click(),'/api/campaign/customers',p=>p.get('offset')==='30','Campaign go to page');
 await page.waitForFunction(()=>document.getElementById('campaign-list-go').value==='3');
 const csvChecks=[];
 for(const action of ['email','none','all','coupon']){
  const rows=await getChange(()=>page.locator('#campaign-action').selectOption(action),'/api/campaign/customers',p=>p.get('action')===action&&p.get('offset')==='0','Campaign filter '+action);
  await page.waitForFunction(()=>!document.getElementById('campaign-export').disabled);
  check(rows.rows.every((r,i)=>!i||r.net_value<=rows.rows[i-1].net_value),'Campaign order incorrect');
  check(rows.rows.every(r=>action==='all'||r.action===action),'Action filter incorrect');
  const responseWait=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/campaign/export'&&new URL(r.url()).searchParams.get('action')===action);
  const downloadWait=page.waitForEvent('download');
  await page.locator('#campaign-export').click();
  const response=await responseWait,download=await downloadWait;
  await download.saveAs(`/tmp/phase2-campaign-${action}.csv`);
  const text=await page.evaluate(async p=>await (await fetch('http://127.0.0.1:8000/api/campaign/export?'+new URLSearchParams(p))).text(),{solution_id:rows.solution_id,action});
  check(response.status()===200&&download.suggestedFilename()===`campaign-${action}.csv`,'CSV download failed');
  const exported=text.trim().split(/\r?\n/);
  check(exported.length-1===rows.total,'CSV must contain all rows of the action filter');
  check(exported[0]==='customer_id,action,days_since_last_purchase,expected_spend_90d,order_value,expected_gain','CSV columns differ from table');
  csvChecks.push({action,total:rows.total,csv_rows:exported.length-1});
  if(action==='none')check((await page.locator('#selected-customers').textContent()).includes('No contact'),'No contact label missing');
  if(['email','none','all'].includes(action))await page.locator('#selected-table').locator('..').locator('..').screenshot({path:`docs/screenshots/dashboard-campaign-${action}.png`});
 }
 await page.waitForFunction(()=>document.querySelectorAll('#selected-customers tr').length===15&&document.getElementById('campaign-list-go').value==='1');
 const products=await getChange(()=>page.locator('#product-country').selectOption('France'),'/api/products/top',p=>p.get('country')==='France','Product country France');
 await page.waitForFunction(()=>document.getElementById('product-revenue-country').textContent==='France');
 check((await page.locator('#products-revenue tr:first-child').textContent()).includes(products.by_revenue[0].stockcode),'Country-filter product mismatch');
 await getChange(()=>page.locator('#product-country').selectOption(''),'/api/products/top',p=>p.get('country')==='','Product all countries');
 await page.locator('#customers').scrollIntoViewIfNeeded();
 const cell=page.locator('.heat-cell').first();const amount=await cell.getAttribute('data-spend');const customer=await cell.getAttribute('data-customer');
 await cell.hover();await page.locator('#chart-tooltip').waitFor({state:'visible'});
 check((await page.locator('#chart-tooltip').textContent()).includes(money(Number(amount))),'Heatmap hover value incorrect');
 check((await page.locator('#chart-tooltip').textContent()).includes(customer),'Heatmap hover customer incorrect');
 await page.screenshot({path:'docs/screenshots/dashboard-heatmap-hover.png'});
 await page.locator('#chart-tooltip').evaluate(el=>el.style.visibility='hidden');
 await page.locator('#loyalty-heatmap').screenshot({path:'docs/screenshots/dashboard-loyalty-heatmap.png'});
 await page.locator('#chart-tooltip').evaluate(el=>el.style.visibility='');
 await page.mouse.move(0,0);
 await page.locator('.topbar').evaluate(el=>el.style.visibility='hidden');
 await page.locator('.customer-panel').screenshot({path:'docs/screenshots/dashboard-customer-ranking.png'});
 await page.locator('.topbar').evaluate(el=>el.style.visibility='');
 const initialCustomers=await page.evaluate(async()=>await (await fetch('http://127.0.0.1:8000/api/customers?sort=expected_spend_90d&direction=desc')).json());
 const displayedIDs=await page.locator('#accounts-body tr td:first-child').allTextContents();
 check(JSON.stringify(displayedIDs)===JSON.stringify(initialCustomers.rows.slice(0,10).map(c=>c.customer_id)),'Initial page is not highest expected spend first');
 check(await page.locator('th:has(button[data-sort="expected_spend_90d"])').getAttribute('aria-sort')==='descending','Initial sort indicator incorrect');
 const firstID=await page.locator('#accounts-body tr:first-child td:first-child').textContent();
 await getChange(()=>page.locator('#customers-next').click(),'/api/customers',p=>p.get('page')==='1','Customer next page');
 await page.waitForFunction(()=>document.getElementById('customer-page').textContent==='Page 2 of 586');
 check(await page.locator('#accounts-body tr:first-child td:first-child').textContent()!==firstID,'Pagination did not change rows');
 await getChange(()=>page.locator('#customers-previous').click(),'/api/customers',p=>p.get('page')==='1','Customer previous page');
 // Page 3 spans the API's 25-row boundary; compare all 10 IDs independently.
 await getChange(()=>page.locator('#customers-next').click(),'/api/customers',p=>p.get('page')==='1','Customer page 2 for boundary');
 await getChange(()=>page.locator('#customers-next').click(),'/api/customers',p=>p.get('page')==='2','Customer boundary page 3');
 await page.waitForFunction(()=>document.getElementById('customer-page').textContent==='Page 3 of 586');
 const apiSecond=await page.evaluate(async()=>await (await fetch('http://127.0.0.1:8000/api/customers?sort=expected_spend_90d&direction=desc&page=2')).json());
 check(JSON.stringify(await page.locator('#accounts-body tr td:first-child').allTextContents())===JSON.stringify(initialCustomers.rows.concat(apiSecond.rows).slice(20,30).map(c=>c.customer_id)),'Boundary page skips or repeats customers');
 await getChange(()=>page.locator('#customers-last').click(),'/api/customers',p=>p.get('page')==='235','Last customer page');
 await page.waitForFunction(()=>document.getElementById('customer-page').textContent==='Page 586 of 586');
 check(await page.locator('#accounts-body tr').count()===1&&await page.locator('#customers-next').isDisabled()&&await page.locator('#customers-last').isDisabled(),'Last page wrong');
 await page.locator('#customer-go').fill('3');
 await getChange(()=>page.locator('#customer-go-form button').click(),'/api/customers',p=>p.get('page')==='2','Go to customer page');
 await page.waitForFunction(()=>document.getElementById('customer-page').textContent==='Page 3 of 586');
 await getChange(()=>page.locator('#customers-first').click(),'/api/customers',p=>p.get('page')==='1','First customer page');
 await page.waitForFunction(()=>document.getElementById('customer-page').textContent==='Page 1 of 586');
 check(await page.locator('#customers-first').isDisabled()&&await page.locator('#customers-previous').isDisabled(),'First page controls wrong');
 await getChange(()=>page.locator('#customer-search').fill('12347'),'/api/customers',p=>p.get('search')==='12347','Customer search');
 await page.waitForFunction(()=>document.querySelectorAll('#accounts-body tr').length===1);
 check(await page.locator('#accounts-body tr:first-child td:first-child').textContent()==='12347','Search result incorrect');
 await getChange(()=>page.locator('#customer-search').fill('99999999'),'/api/customers',p=>p.get('search')==='99999999','Empty customer search');
 await page.waitForFunction(()=>document.getElementById('customer-page').textContent==='No matches');
 check(await page.locator('#customers-next').isDisabled(),'Next enabled on empty results');
 await getChange(()=>page.locator('#customer-search').fill(''),'/api/customers',p=>p.get('search')==='','Clear customer search');
 const ascending=await getChange(()=>page.locator('button[data-sort="expected_spend_90d"]').click(),'/api/customers',p=>p.get('sort')==='expected_spend_90d'&&p.get('direction')==='asc','Ascending expected spend');
 check(ascending.rows.every((r,i)=>!i||r.expected_spend_90d>=ascending.rows[i-1].expected_spend_90d),'Ascending sort incorrect');
 const descending=await getChange(()=>page.locator('button[data-sort="expected_spend_90d"]').click(),'/api/customers',p=>p.get('direction')==='desc','Descending expected spend');
 check(descending.rows.every((r,i)=>!i||r.expected_spend_90d<=descending.rows[i-1].expected_spend_90d),'Descending sort incorrect');
 for(const key of ['days_since_last_purchase','number_of_purchases','customer_age_days','probability_of_buying_90d']){
  const sorted=await getChange(()=>page.locator(`button[data-sort="${key}"]`).click(),'/api/customers',p=>p.get('sort')===key&&p.get('direction')==='asc','Sort '+key);
  check(sorted.rows.every((r,i)=>!i||r[key]>=sorted.rows[i-1][key]),key+' sort incorrect');
 }
 await getChange(()=>page.locator('button[data-sort="customer_id"]').click(),'/api/customers',p=>p.get('sort')==='customer_id','Restore customer order');
 await page.locator('#returns').screenshot({path:'docs/screenshots/dashboard-returns.png'});
 async function campaignChange(action,predicate,label){
  const data=await getChange(action,'/api/optimize',(_,request)=>request.method()==='POST'&&predicate(request.postDataJSON()),label);
  await page.waitForFunction(()=>document.getElementById('campaign-status').textContent==='Recommendation ready'&&document.getElementById('campaign-list-status').textContent==='Recommended actions, not confirmed responses');
  check(!('assignments' in data)&&data.top_selected.length<=15,'Interactive response must not contain all customer assignments');
  return data;
 }
 const budget=await campaignChange(async()=>{await page.locator('#slider-B').focus();await page.keyboard.press('ArrowRight');},b=>b.run==='PROD'&&b.B===1683,'Budget slider');
 check((await page.locator('#campaign-investment').textContent()).includes('invest £1,683'),'Headline investment did not update');
 check(await page.locator('#net-value').textContent()===money(budget.net_value),'Campaign profit does not match response');
 const zeroCoupons=await campaignChange(()=>page.locator('#input-K').fill('0'),b=>b.run==='PROD'&&b.K===0,'Zero coupon limit');
 check(zeroCoupons.counts.coupon===0,'Zero coupon limit ignored');
 check(await page.locator('#campaign-list-next').isDisabled()&&await page.locator('#campaign-list-go').isDisabled(),'Empty campaign page controls must be disabled');
 await page.locator('#selected-table').locator('..').locator('..').screenshot({path:'docs/screenshots/dashboard-campaign-empty.png'});
 await campaignChange(()=>page.locator('#input-K').fill('250'),b=>b.run==='PROD'&&b.K===250,'Maximum coupons');
 await page.locator('#advanced-assumptions>summary').click();
 for(const [key,value] of Object.entries({m:32,tau_e:3,tau_c:20,f_e:.06,f_c:1.2,d:12})){
  await campaignChange(()=>page.locator('#input-'+key).fill(String(value)),b=>b.run==='PROD'&&b[key]===(['m','tau_e','tau_c','d'].includes(key)?value/100:value),key+' assumption');
 }
 await page.locator('#input-B').fill('-1');
 await page.waitForFunction(()=>!document.getElementById('campaign-error').hidden);
 check((await page.locator('#campaign-investment').textContent()).includes('Previous proposal shown'),'Invalid-input headline lacks stale warning');
 await campaignChange(()=>page.locator('#reset').click(),b=>b.run==='PROD'&&b.B===1682&&b.K===300&&b.m===.3,'Reset campaign');
 await page.locator('#advanced-assumptions>summary').click();
 check(await page.locator('#selected-customers tr').count()===15,'Top selected customer table incomplete');
 const clipped=await page.locator('#selected-customers').evaluate(el=>el.parentElement.parentElement.scrollHeight>el.parentElement.parentElement.clientHeight+1);
 check(!clipped,'Selected customers vertically clipped');
 await page.evaluate(()=>window.scrollTo({top:document.getElementById('campaign').offsetTop-80,behavior:'instant'}));
 await page.screenshot({path:'docs/screenshots/dashboard-campaign.png'});
 const evidenceBeforeOpen=requests.filter(url=>/\/api\/(metrics|calibration|sensitivity)/.test(url)).length;
 check(evidenceBeforeOpen===0,'Technical evidence should load only when opened');
 await page.locator('.topbar').evaluate(el=>el.style.visibility='hidden');
 await page.locator('#campaign .campaign-results article.panel').screenshot({path:'docs/screenshots/dashboard-selected-customers.png'});
 await page.locator('.topbar').evaluate(el=>el.style.visibility='');
 await page.locator('#method-evidence>summary').click();
 await page.waitForFunction(()=>document.querySelectorAll('#model-table tr').length===5&&document.querySelector('#calibration-chart svg')&&document.querySelector('#sensitivity-chart svg')&&document.getElementById('backtest-share').textContent==='83.66%');
 for(const icon of await page.locator('.method-body .info-icon').all()){
  const text=await icon.getAttribute('data-tip');
  await icon.hover();check(await page.locator('#chart-tooltip').isVisible()&&await page.locator('#chart-tooltip').textContent()===text,'Method help hover failed');
  await icon.focus();await page.keyboard.press('Shift+Tab');await page.keyboard.press('Tab');
  check(await icon.evaluate(el=>el===document.activeElement)&&await page.locator('#chart-tooltip').textContent()===text,'Method help focus failed');
  tooltipTexts.push({label:await icon.getAttribute('aria-label'),text});
 }
 check(await page.locator('#baseline-table tr').count()===3,'Stronger baselines missing');
 check((await page.locator('#solver-detail').textContent()).includes('Solved to within 0.5% of the best possible plan'),'Plain calculation status missing');
 check((await page.locator('#solver-detail .info-icon').getAttribute('data-tip')).includes('FEASIBLE_GAP_TARGET'),'Raw status missing from help');
 check(await page.locator('#greedy-improvement').textContent()===money(economics.improvement),'Current greedy improvement differs');
 check(await page.locator('#baseline-table tr:last-child td:nth-child(3)').textContent()===money(economics.improvement),'Greedy improvement is inconsistent');
 check(!(await page.locator('#method-evidence').textContent()).includes('£0.74'),'Historical exact figure remains unlabeled');
 check((await page.locator('#backtest-table').locator('..').textContent()).includes('Average predicted probability'),'Plain probability header missing');
 check((await page.locator('#sensitivity-legend').textContent()).includes('Coupon response 15%'),'Plain coupon-response legend missing');

 const comparison=page.waitForResponse(r=>r.url().includes('/api/metrics?run=B'));
 await page.locator('#comparison-run').selectOption('B');await comparison;
 check((await page.locator('#comparison-period').textContent()).includes('180-day'),'Historical horizon missing');
 await page.locator('button[data-model="logreg"]').click();
 await page.waitForFunction(()=>document.getElementById('calibration-model').textContent==='Logistic');
 const compareA=page.waitForResponse(r=>r.url().includes('/api/metrics?run=A'));
 await page.locator('#comparison-run').selectOption('A');await compareA;
 await page.locator('button[data-model="bgnbd"]').click();
 await campaignChange(()=>page.locator('#campaign-model').selectOption('logreg'),b=>b.run==='PROD'&&b.model==='logreg','Campaign model in evidence');
 await campaignChange(()=>page.locator('#extra-budget').check(),b=>b.run==='PROD'&&b.include_extra_100,'Optional extra investment');
 await page.waitForFunction(()=>document.getElementById('marginal').textContent!=='Not requested');
 await campaignChange(()=>page.locator('#reset').click(),b=>b.run==='PROD'&&b.model==='bgnbd'&&!b.include_extra_100,'Restore default campaign');
 await page.waitForFunction(()=>document.getElementById('backtest-share').textContent==='83.66%');
 const sensitivity=page.waitForResponse(r=>r.url().endsWith('/api/sensitivity'));
 await page.locator('#refresh-sensitivity').click();const sensitivityData=await (await sensitivity).json();
 check(sensitivityData.grid_points===15,'Sensitivity grid incorrect');
 await page.waitForFunction(()=>!document.getElementById('refresh-sensitivity').disabled);
 check(await page.locator('#backtest-table tr:first-child td').count()===7,'Order-value backtest missing');
 await page.locator('.topbar').evaluate(el=>el.style.visibility='hidden');
 await page.locator('#method-evidence').screenshot({path:'docs/screenshots/dashboard-method-evidence.png'});
 await page.locator('.topbar').evaluate(el=>el.style.visibility='');
 await page.locator('#method-evidence>summary').click();
 const responsive=[];
 for(const [width,height] of [[1280,800],[1440,900],[390,844]]){
  await page.setViewportSize({width,height});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  const layout=await page.evaluate(()=>{
   const intersects=(a,b)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
   const overlaps=[...document.querySelectorAll('.action-cards article,.backtest-kpis>div')].flatMap(card=>{
    const icon=card.querySelector('.info-icon').getBoundingClientRect();
    return [...card.querySelectorAll('strong,span:not(.dot)')].filter(el=>intersects(icon,el.getBoundingClientRect())).map(el=>el.textContent);
   });
   const widths=['sales','customers','returns','campaign'].map(id=>document.getElementById(id).getBoundingClientRect().width);
   const notes=[...document.querySelectorAll('.partial-note')].map(el=>({text:el.textContent,length:el.textContent.length}));
   return {overlaps,widths,notes};
  });
  check(!layout.overlaps.length,'Help icon overlaps label/number at '+width+': '+layout.overlaps.join(','));
  check(Math.max(...layout.widths)-Math.min(...layout.widths)<1,'Returns section differs in width');
  check(layout.notes.every(n=>n.length<160),'Chart note too long');

  check(!overflow,'Page-level overflow at '+width);responsive.push({width,height,page_horizontal_overflow:overflow,...layout});
 }
 await page.setViewportSize({width:1366,height:900});
 check(errors.length===0,'Unexpected console errors: '+errors.join(';'));
 check(external.length===0,'External page request attempted');
 const normalErrors=[...errors];
 // Failures are deliberately injected only after the zero-error normal checks.
 // Campaign context now arrives with its paginated cached-plan rows.
 await page.route('**/api/campaign/customers?*',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Simulated campaign list unavailable'})}));
 await page.reload();
 await page.waitForFunction(()=>!document.getElementById('campaign-list-error').hidden);
 check(await page.locator('#campaign-export').isDisabled(),'Export must be disabled when the list is unavailable');
 await page.unroute('**/api/campaign/customers?*');
 await page.locator('#campaign-list-retry').click();
 await page.waitForFunction(()=>document.getElementById('campaign-list-error').hidden&&document.querySelectorAll('#selected-customers tr').length===15);

 await page.route('**/api/optimize',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Simulated local calculation unavailable'})}));
 await page.locator('#input-B').fill('1720');
 await page.waitForFunction(()=>!document.getElementById('campaign-error').hidden);
 await page.evaluate(()=>window.scrollTo({top:document.getElementById('campaign').offsetTop-80,behavior:'instant'}));
 await page.keyboard.press('Escape');await page.evaluate(()=>document.activeElement.blur());await page.mouse.move(0,0);
 await page.screenshot({path:'docs/screenshots/dashboard-error-state.png'});
 await page.unroute('**/api/optimize');
 await campaignChange(()=>page.locator('#reset').click(),b=>b.B===1682&&b.run==='PROD','Recover campaign failure');
 await page.waitForFunction(()=>document.getElementById('campaign-error').hidden);
 const productPattern='**/api/products/top?*';
 await page.route(productPattern,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Simulated product data unavailable'})}));
 await page.locator('#product-country').selectOption('France');
 await page.waitForFunction(()=>!document.getElementById('products-error').hidden);
 await page.unroute(productPattern);
 await getChange(()=>page.locator('#product-country').selectOption(''),'/api/products/top',p=>p.get('country')==='','Recover product failure');
 await page.waitForFunction(()=>document.getElementById('products-error').hidden);
 const listPattern=/\/api\/customers\?/;
 await page.route(listPattern,async route=>{await new Promise(resolve=>setTimeout(resolve,700));await route.continue();});
 const delayed=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/customers'&&new URL(r.url()).searchParams.get('search')==='12347');
 await page.locator('#customer-search').fill('12347');
 await page.waitForFunction(()=>document.getElementById('customers-status').textContent==='Loading accounts…');
 check(await page.locator('#customers-next').isDisabled(),'Pagination active during loading');await delayed;
 await page.unroute(listPattern);
 await getChange(()=>page.locator('#customer-search').fill(''),'/api/customers',p=>p.get('search')==='','Restore customer search after loading');
 await page.goto('http://localhost:8080');
 await page.waitForFunction(()=>document.getElementById('kpi-customers').textContent==='4,260'&&document.querySelectorAll('#selected-customers tr').length===15);
 check(!await page.locator('#method-evidence').evaluate(el=>el.open),'Method default changed on localhost');
 await page.route('**/api/exec/summary',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Simulated initial data unavailable'})}));
 await page.reload();await page.waitForFunction(()=>!document.getElementById('retry-api').hidden);
 await page.unroute('**/api/exec/summary');await page.locator('#retry-api').click();
 await page.waitForFunction(()=>document.getElementById('kpi-customers').textContent==='4,260'&&document.querySelectorAll('#accounts-body tr').length===10);
 return {normal_console_errors:normalErrors,external_page_requests:external,local_request_count:requests.length,
         above_fold_text:aboveFold,executive_labels_passed:true,method_collapsed_by_default:true,advanced_collapsed_by_default:true,technical_requests_before_open:evidenceBeforeOpen,
         new_controls:{csv:csvChecks,loyalty_total:loyaltyInitial.total,loyalty_search_offset:foundLoyalty.offset,monthly_country_filter:true},gain_arithmetic:economics,partial_month_styles:partialStyles,partial_daily_comparisons:partialComparisons,tooltip_texts:tooltipTexts,tooltip_hover_and_keyboard_checks:tooltipTexts.length,default_sort:'expected_spend_90d desc',selected_customer_context: selectedContext,
         heatmap_cells:120,heatmap_hover_value:amount,customer_page_rows:10,selected_customer_rows:15,
         selected_customer_table_clipped:clipped,partial_month_labels_passed:true,responsive,interactions,
         sensitivity_points:sensitivityData.grid_points,campaign_error_recovery:true,product_error_recovery:true,
         campaign_list_error_recovery:true,loading_state_verified:true,startup_retry_passed:true,localhost_origin_passed:true};
}
