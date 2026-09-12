// Logic/DOM-contract checks, not a rendered-browser visual inspection.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('preview/index.html','utf8');
assert(html.includes('href="https://script.google.com/macros/s/AKfycbzE1ZYdZsbJuMLQMWXTeO21bR-fb3BvRMzcxOz9P5gcBbYJRxzEZZtVJAZHqefwRrw/exec" target="_blank" rel="noopener noreferrer"'));
assert(html.includes('登入填報／當日查價'));
assert(!html.includes('binchi@gmail.com'));
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();let exported;
function el(id){if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:'',hidden:false,open:false,addEventListener(){},append(){},setAttribute(){},showModal(){this.open=true},close(){this.open=false}});return elements.get(id)}
const context=vm.createContext({console,Blob,location:{pathname:'/',protocol:'file:'},document:{getElementById:el,querySelectorAll:()=>[],createElement:()=>({click(){}})},sessionStorage:{getItem(){return null},setItem(){}},URL:{createObjectURL(b){exported=b;return 'blob:test'},revokeObjectURL(){}},setTimeout(){},setInterval(){},window:{print(){}}});
vm.runInContext(script,context);
assert(el('cards').innerHTML.includes('價格基準 0'));
vm.runInContext("view='retail';show()",context);
assert(el('count').textContent.startsWith('28 '));
vm.runInContext("$('q').value='高麗菜';show();csv()",context);
assert(el('count').textContent.startsWith('1 '));
assert(el('cards').innerHTML.includes('2026-08'));
vm.runInContext("$('q').value='';$('market').value=DATA.markets[0];show()",context);
assert(vm.runInContext("pointsFor(shown[0]).some(p=>valid(p.wholesale))",context));
assert(vm.runInContext("pointsFor(shown[0]).filter(p=>p.month==='2026-08')[0].n<=1",context));
vm.runInContext("comparisons[shown[0].id]=''",context);
assert(vm.runInContext("pointsFor(shown[0]).every(p=>!valid(p.wholesale))",context));
vm.runInContext("DATA.items[0].assessment={status:'待查證異常',month:'2026-09',actual:99,lower:10,upper:30};alerts()",context);
assert(el('alert-dialog').open);
assert(el('alert-body').innerHTML.includes('99.00'));
(async()=>{const csv=await exported.text();assert(csv.includes('判斷月份'));assert(csv.includes('高麗菜'));assert(csv.includes('甘藍'));assert(csv.includes('SHA256'));assert(!csv.includes('NaN'));console.log('PASS: render contract, filters, semantic matching, market isolation, export provenance, alert dialog; visual QA not performed.');})();
