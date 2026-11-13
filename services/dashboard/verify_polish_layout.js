// Additional screenshot and geometry review for the current dashboard.
async page=>{
 const errors=[],external=[],checks=[];
 const check=(v,m)=>{if(!v)throw new Error(m);};
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route('**/*',route=>{
  const u=new URL(route.request().url());
  if(['localhost','127.0.0.1'].includes(u.hostname))return route.continue();
  external.push(u.href);return route.abort();
 });
 await page.setViewportSize({width:1366,height:1100});
 await page.goto('http://127.0.0.1:8080');
 const ready=()=>page.waitForFunction(()=>document.getElementById('campaign-status').textContent==='Recommendation ready'&&document.getElementById('product-revenue-country').textContent==='All countries'&&document.querySelectorAll('#products-revenue tr').length===10);
 await ready();
 const brazil=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/products/top'&&new URL(r.url()).searchParams.get('country')==='Brazil');
 await page.locator('#product-country').selectOption('Brazil');await brazil;
 await page.reload();await ready();
 await page.addStyleTag({content:'html{scroll-behavior:auto!important}'});
 check(await page.locator('#product-country').inputValue()==='','Country restored Brazil after reload');
 checks.push('Brazil selection resets to All countries on reload; table and selector agree');
 await page.screenshot({path:'docs/screenshots/dashboard-overview.png'});
 await page.locator('#sales').screenshot({path:'docs/screenshots/dashboard-sales.png'});
 await page.setViewportSize({width:1366,height:900});
 await page.evaluate(()=>window.scrollTo({top:document.getElementById('campaign').offsetTop-85,behavior:'instant'}));
 const icon=page.locator('[data-help=orderValue]');
 await icon.hover();await page.screenshot({path:'docs/screenshots/dashboard-tooltip-hover.png'});
 await icon.focus();await page.keyboard.press('Shift+Tab');await page.keyboard.press('Tab');
 check(await icon.evaluate(el=>el===document.activeElement),'Typical-order help not keyboard reachable');
 await page.screenshot({path:'docs/screenshots/dashboard-tooltip-focus.png'});
 await page.keyboard.press('Escape');await page.mouse.move(0,0);
 await page.setViewportSize({width:1366,height:1200});
 await page.locator('#advanced-assumptions>summary').click();
 await page.locator('.topbar').evaluate(el=>el.style.visibility='hidden');
 await page.locator('.campaign-inputs').screenshot({path:'docs/screenshots/dashboard-advanced-assumptions.png'});
 await page.locator('.topbar').evaluate(el=>el.style.visibility='');
 await page.locator('#advanced-assumptions>summary').click();
 await page.setViewportSize({width:1366,height:900});
 await page.locator('#method-evidence>summary').click();
 await page.waitForFunction(()=>document.getElementById('backtest-share').textContent==='83.66%'&&document.querySelector('#sensitivity-chart svg'));
 const geometry=[];
 for(const width of [1280,1440]){
  await page.setViewportSize({width,height:900});
  const g=await page.evaluate(()=>{
   const intersects=(a,b)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
   const overlaps=[...document.querySelectorAll('.action-cards article,.backtest-kpis>div')].flatMap(card=>{
    const i=card.querySelector('.info-icon').getBoundingClientRect();
    return [...card.querySelectorAll('strong,span:not(.dot)')].filter(el=>intersects(i,el.getBoundingClientRect())).map(el=>el.textContent);
   });
   const widths=['sales','customers','returns','campaign'].map(id=>document.getElementById(id).getBoundingClientRect().width);
   const returnsNotes=[...document.querySelectorAll('#returns .partial-note')].map(el=>({text:el.textContent,characters:el.textContent.length}));
   return {overlaps,widths,returnsNotes,backtest_visible:document.getElementById('backtest').getBoundingClientRect().height>0};
  });
  check(g.backtest_visible&&!g.overlaps.length,'Action/Run A icon overlap at '+width);
  check(Math.max(...g.widths)-Math.min(...g.widths)<1,'Returns width differs at '+width);
  // Use text line boxes; paragraph padding does not count as another text line.
  const lines=await page.locator('#returns .partial-note').evaluateAll(els=>els.map(el=>{const r=document.createRange();r.selectNodeContents(el);return r.getClientRects().length;}));
  check(lines.every(n=>n<=3),'Returns note exceeds three readable lines at '+width);
  geometry.push({width,...g,return_note_text_lines:lines});
  await page.locator('.topbar').evaluate(el=>el.style.visibility='hidden');
  await page.locator('.action-cards').screenshot({path:`docs/screenshots/dashboard-action-cards-${width}.png`});
  await page.locator('.backtest-kpis').screenshot({path:`docs/screenshots/dashboard-run-a-kpis-${width}.png`});
  await page.locator('.topbar').evaluate(el=>el.style.visibility='');
 }
 await page.setViewportSize({width:1366,height:900});
 await page.locator('#input-B').fill('1683');
 await page.waitForFunction(()=>document.getElementById('campaign-status').textContent==='Recommendation ready'&&document.getElementById('campaign-investment').textContent.includes('£1,683'));
 check(await page.locator('#sensitivity-status').evaluate(el=>getComputedStyle(el).color)===await page.locator('#method-evidence>summary p').evaluate(el=>getComputedStyle(el).color),'Previous-assumptions note is not neutral');
 await page.locator('.topbar').evaluate(el=>el.style.visibility='hidden');
 await page.locator('#sensitivity-chart').locator('..').screenshot({path:'docs/screenshots/dashboard-sensitivity-note.png'});
 await page.locator('.topbar').evaluate(el=>el.style.visibility='');
 await page.locator('#reset').click();
 await page.waitForFunction(()=>document.getElementById('campaign-status').textContent==='Recommendation ready'&&document.getElementById('campaign-investment').textContent.includes('£1,682'));
 await page.locator('#refresh-sensitivity').click();
 await page.waitForFunction(()=>!document.getElementById('refresh-sensitivity').disabled&&document.getElementById('backtest-share').textContent==='83.66%');
 await page.locator('#method-evidence>summary').click();
 await page.setViewportSize({width:390,height:844});
 await page.evaluate(()=>{document.activeElement.blur();window.scrollTo({top:0,behavior:'instant'});});await page.mouse.move(0,0);
 const controlsFit=await page.locator('.campaign-inputs').evaluate(panel=>{
  const box=panel.getBoundingClientRect();
  return [...panel.querySelectorAll('#primary-controls input')].every(el=>{const r=el.getBoundingClientRect();return r.left>=box.left&&r.right<=box.right;});
 });
 check(controlsFit,'Mobile campaign controls extend beyond their panel');
 const rankingNoteLines=await page.locator('.ranking-note').evaluate(el=>{const r=document.createRange();r.selectNodeContents(el);return r.getClientRects().length;});
 check(rankingNoteLines===1,'Loyalty footnote must stay on one line on mobile');
 await page.screenshot({path:'docs/screenshots/dashboard-mobile.png',fullPage:true});
 await page.screenshot({path:'docs/screenshots/dashboard-mobile-top.png'});
 await page.setViewportSize({width:1366,height:900});
 await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
 check(!errors.length,'Console errors: '+errors.join(';'));
 check(!external.length,'External requests attempted');
 return {checks,geometry,neutral_sensitivity_note:true,mobile_controls_fit:true,loyalty_note_one_line:true,normal_console_errors:errors,external_requests:external};
}
