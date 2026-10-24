// Disposable local Chrome test with synthetic prices; no user's browser/account is used.
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const deps='C:/Users/water/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {chromium}=require(path.join(deps,'playwright')),sharp=require(path.join(deps,'sharp'));
const root=path.resolve(__dirname,'..'),out=path.join(root,'output','playwright');fs.mkdirSync(out,{recursive:true});
const types={'.html':'text/html; charset=utf-8','.js':'application/javascript','.json':'application/json','.wasm':'application/wasm','.gz':'application/gzip'};
const server=http.createServer((req,res)=>{let pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);const file=path.resolve(root,'.'+pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}fs.readFile(file,(e,b)=>{if(e){res.writeHead(404);return res.end();}res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');res.end(b);});});
(async()=>{await new Promise(r=>server.listen(0,'127.0.0.1',r));const url='http://127.0.0.1:'+server.address().port;const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});const errors=[],unexpected=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(url)&&!r.url().startsWith('blob:')&&!r.url().startsWith('data:'))unexpected.push(r.url());});
try{
  await page.goto(url+'/inspection.html');await page.getByText('本頁暫存模式｜未登入，資料不會自動保存',{exact:true}).waitFor();
  await page.getByLabel('查調日期',{exact:true}).fill('2026-10-23');await page.getByLabel('市場',{exact:true}).fill('測試市場');await page.getByLabel('攤位代號（可不填）').fill('A01');await page.getByRole('button',{name:'載入此日紀錄／開始填寫'}).click();
  await page.getByLabel('案件編號',{exact:true}).fill('TEST-20261025');await page.getByLabel('查核人員',{exact:true}).fill('測試人員');await page.getByLabel('現場發現',{exact:true}).fill('測試資料，不代表正式稽查。');
  const price=page.getByRole('spinbutton',{name:'高麗菜1台斤價格',exact:true}),spec=page.getByRole('textbox',{name:'高麗菜1台斤規格',exact:true});await spec.fill('平地一般級');await price.fill('60');await page.getByRole('button',{name:'加入本頁暫存並更新趨勢'}).click();await page.getByText('已加入本頁暫存並更新趨勢；未同步雲端，離開前請下載備份。',{exact:true}).waitFor();
  await page.getByLabel('查調日期',{exact:true}).fill('2026-10-24');await page.getByRole('button',{name:'載入此日紀錄／開始填寫'}).click();assert.equal(await price.inputValue(),'');await price.fill('66');await page.locator('#inputs').getByText('▲ 10.00%',{exact:true}).waitFor();await page.getByRole('button',{name:'加入本頁暫存並更新趨勢'}).click();
  await page.getByText('已加入本頁暫存並更新趨勢；未同步雲端，離開前請下載備份。',{exact:true}).waitFor();
  const image=path.join(out,'price-tag.jpg');await sharp(Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="500"><rect width="1400" height="500" fill="white"/><text x="80" y="210" font-family="Microsoft JhengHei" font-size="105" fill="black">高麗菜 $66 /台斤</text></svg>')).jpeg().toFile(image);
  await page.getByText('拍照辨識價牌或訪查表',{exact:true}).click();await page.locator('#i-photo').setInputFiles(image);await page.getByText('照片已加入本頁，可辨識文字；請在離開前匯出文件或照片備份。',{exact:true}).waitFor();
  await page.getByRole('button',{name:'辨識最後一張照片'}).click();await page.locator('#i-ocr-status').filter({hasText:'辨識完成'}).waitFor({timeout:180000});const recognized=await page.locator('#i-ocr-text').inputValue();assert(recognized.includes('66'),recognized);
  // Test deterministic candidate parsing even if engine's word segmentation varies.
  await page.locator('#i-ocr-text').fill('高麗菜 $66 /台斤');await page.getByRole('button',{name:'從文字建立建議'}).click();await page.locator('#i-candidates button').click();await page.getByLabel('確認規格',{exact:true}).fill('平地一般級');await page.getByRole('button',{name:'將核對結果帶入表格'}).click();await page.getByText('請先核對照片，勾選確認價格與單位',{exact:true}).waitFor();
  await page.getByLabel('我已核對照片、品項、價格與單位',{exact:true}).check();page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'將核對結果帶入表格'}).click();await page.getByLabel('本批更正原因（修改舊資料時必填）').fill('測試照片核對');await page.getByRole('button',{name:'加入本頁暫存並更新趨勢'}).click();await page.getByText('已加入本頁暫存並更新趨勢；未同步雲端，離開前請下載備份。',{exact:true}).waitFor();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'下載 Word 稽查紀錄與分析報告'}).click();const doc=await download;await doc.saveAs(path.join(out,'稽查報告測試.docx'));
  const htmlDownload=page.waitForEvent('download');await page.getByRole('button',{name:'下載簡要報告 HTML'}).click();const html=await htmlDownload;await html.saveAs(path.join(out,'稽查報告測試.html'));
  const report=fs.readFileSync(path.join(out,'稽查報告測試.html'),'utf8');assert(report.includes('照片附件'));assert(report.includes('data:image/jpeg;base64,'));assert(report.includes('10.00%'));
  await page.getByLabel('只顯示已填價格',{exact:true}).check();assert.equal(await page.locator('#inputs tr:visible').count(),1);
  await page.screenshot({path:path.join(out,'inspection-mobile.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Mobile page overflows');
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[],'OCR should use only local assets');
  // Print fixture with the same report markup in A4 for layout review.
  const print=await browser.newPage({viewport:{width:1000,height:1000}});await print.goto('file:///'+path.join(out,'稽查報告測試.html').replaceAll('\\','/'));await print.pdf({path:path.join(out,'report-layout.pdf'),format:'A4',printBackground:true});
  console.log(JSON.stringify({passed:true,ocrText:recognized,externalRequests:unexpected.length,wordFile:'output/playwright/稽查報告測試.docx',pageErrors:errors}));
}finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
