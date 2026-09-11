"""Auditable monitoring build. Never interpret legacy mixed-date snapshots as daily prices."""
import argparse
import calendar
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from source_matching import fetch_extra, add_sources, match_items

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
RAW = DATA / 'verified'
FARM = 'https://data.moa.gov.tw/Service/OpenData/FromM/FarmTransData.aspx'
RICE = 'https://data.moa.gov.tw/Service/OpenData/FromM/RicepriceData.aspx'
POLICY = {'version': '2026-09-v1', 'minimum_months': 12, 'target_months': 24,
          'window_months': 36, 'iqr_multiplier': 1.5, 'minimum_band_pp': 10,
          'formula': '(零售每公斤均價 / 同月批發每公斤均價 - 1) × 100'}
SOURCES = [
 {'name':'農產品交易行情／AMIS', 'url':'https://data.gov.tw/dataset/8066', 'state':'已介接，逐筆驗證日期與市場', 'use':'西螺鎮及其他批發市場作物代碼、上中下價、均價、交易量；按月以交易量加權。'},
 {'name':'田邊好幫手', 'url':'https://m.moa.gov.tw/Transaction/AgriculturalProduct/Index', 'state':'官方交叉查詢入口', 'use':'核對相同市場、作物及交易日；同源網站不能算第二個獨立證據。'},
 {'name':'臺南市傳統市場訪查表', 'url':'', 'state':'已匯入 2026 年 1–8 月', 'use':'7 市場、28 商品。仍需精確訪查日、品種等級、計價重量及至少 24 個月歷史，才能建立季節性價差基準。'},
 {'name':'農糧署糧價查詢', 'url':'https://data.gov.tw/dataset/17092', 'state':'已介接並修正米種與單位', 'use':'臺南市同米種白米零售與躉售；躉售每百公斤除以 100。稻穀不與白米直接比價。'},
 {'name':'農業部產銷行情資訊', 'url':'https://www.moa.gov.tw/theme_list.php?theme=tapinfo_data', 'state':'補充來源清單', 'use':'魚貨、毛豬、家禽行情。毛豬活體／整雞與切肉不同規格，需分切率、加工及運銷資料才能配對。'},
 {'name':'主計總處物價統計', 'url':'https://www.stat.gov.tw/cp.aspx?n=2665&s=2414', 'state':'建議背景來源，未自動匯入', 'use':'長期類別及民生物資指數，作整體背景；不能將指數當作每公斤價格。'},
 {'name':'中央氣象署開放資料', 'url':'https://opendata.cwa.gov.tw/devManual/insrtuction', 'state':'建議背景來源，未自動匯入', 'use':'雨量、颱風與豪雨作異常查核背景；API 授權碼尚未設定。'},
]

def number(x):
    try:
        v = float(x)
        return v if math.isfinite(v) and v > 0 else None
    except (ValueError, TypeError):
        return None

def parse_date(value):
    parts = re.findall(r'\d+', str(value))
    if len(parts) == 1 and len(parts[0]) in (7,8):
        s=parts[0]; parts=[s[:-4],s[-4:-2],s[-2:]]
    if len(parts) != 3: return None
    y,m,d=map(int,parts)
    if y < 1911: y+=1911
    try: return date(y,m,d).isoformat()
    except ValueError: return None

def dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def request(url):
    with urlopen(Request(url,headers={'User-Agent':'Tainan-price-monitor/2'}),timeout=60) as response:
        rows=json.load(response)
    if not isinstance(rows,list): raise ValueError('API 未回傳資料列')
    return rows

def fetch(start, end):
    RAW.mkdir(parents=True,exist_ok=True)
    errors=[]
    # One month per request, paginate to avoid the legacy 9999-row truncation.
    cursor=start.replace(day=1)
    while cursor<=end:
        last=min(end,date(cursor.year,cursor.month,calendar.monthrange(cursor.year,cursor.month)[1]))
        first=max(start,cursor)
        for market in ('西螺鎮',):
            target=RAW/f'farm_{cursor:%Y%m}_{market}.json'
            if target.exists() and last < end.replace(day=1): continue
            rows=[]; seen=set()
            try:
                for skip in range(0,100000,1000):
                    params={'StartDate':f'{first.year-1911:03d}.{first:%m.%d}', 'EndDate':f'{last.year-1911:03d}.{last:%m.%d}',
                            'Market':market,'$top':1000,'$skip':skip}
                    batch=request(FARM+'?'+urlencode(params))
                    if not batch: break
                    signature=hashlib.sha256(json.dumps(batch,sort_keys=True).encode()).hexdigest()
                    if signature in seen: raise ValueError('分頁重複，資料可能不完整')
                    seen.add(signature); rows.extend(batch)
                    if len(batch)<1000: break
                else: raise ValueError('超過資料頁數上限')
                clean=[r for r in rows if r.get('市場名稱')==market and (parse_date(r.get('交易日期')) or '') >= first.isoformat() and (parse_date(r.get('交易日期')) or '9999')<=last.isoformat()]
                if not clean: raise ValueError('指定市場／期間無可驗證資料')
                dump(target,{'source':FARM,'fetched_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),'start':first.isoformat(),'end':last.isoformat(),'rows':clean})
                print(f'Farm {cursor:%Y-%m}: {len(clean)} verified records',flush=True)
            except Exception as exc: errors.append(f'{cursor:%Y-%m} {market}：{exc}')
        cursor=(cursor.replace(day=28)+timedelta(days=4)).replace(day=1)
    try:
        rows=request(RICE)
        if not rows or not any(parse_date(r.get('pt_date_day')) for r in rows): raise ValueError('糧價日期欄位不符')
        dump(RAW/'rice.json',{'source':RICE,'fetched_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),'rows':rows})
    except Exception as exc: errors.append(f'糧價：{exc}')
    for prefix,endpoint in [('poultry','PoultryTransData'),('livestock','AnimalTransData'),('aquatic','AquaticTransData')]:
        try:
            rows=request('https://data.moa.gov.tw/Service/OpenData/FromM/'+endpoint+'.aspx')
            if not rows or not any(parse_date(r.get('日期',r.get('交易日期'))) for r in rows): raise ValueError('無有效日期')
            dump(DATA/f'{prefix}_{end:%Y%m%d}.json',rows)
        except Exception as exc: errors.append(f'{prefix}：{exc}')
    errors.extend(fetch_extra(ROOT,request,dump,parse_date,start,end))
    dump(RAW/'fetch-status.json',{'checked_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),'errors':errors})
    return errors

def quantile(values,q):
    v=sorted(values); x=(len(v)-1)*q; i=int(x)
    return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(x-i)

def assess(points, approved=True):
    paired=[p for p in points if number(p.get('retail')) and number(p.get('wholesale'))]
    if not approved: return {'status':'待確認配對','reason':'零售規格未細分至批發作物代碼；僅供參考，不啟用價差警示。','n':len(paired)}
    if not paired: return {'status':'資料不足','reason':'尚無同月、同規格的批零資料。','n':0}
    paired=sorted(paired,key=lambda p:p['month'])
    latest=paired[-1]
    current=int(latest['month'][:4])*12+int(latest['month'][5:])
    past=[p for p in paired[:-1] if 0 < current-(int(p['month'][:4])*12+int(p['month'][5:])) <= POLICY['window_months']]
    if len(past)<POLICY['minimum_months']:
        return {'status':'資料不足','reason':f'需至少 12 個前期配對月，目前 {len(past)} 個；24 個月以上再評估季節性。','n':len(past)}
    ratios=[(p['retail']/p['wholesale']-1)*100 for p in past]
    q1,q3=quantile(ratios,.25),quantile(ratios,.75)
    center=median(ratios); lower=min(q1-1.5*(q3-q1),center-10); upper=max(q3+1.5*(q3-q1),center+10)
    actual=(latest['retail']/latest['wholesale']-1)*100
    stale=(date.today()-date.fromisoformat(latest['month']+'-01')).days>75
    state='資料逾期' if stale else '待查證異常' if actual<lower or actual>upper else '區間內'
    return {'status':state,'reason':'統計篩查區間，非合理利潤或違法判定。'+('未滿 24 個月，屬試行基準。' if len(past)<24 else '仍需查核季節、成本與供應量。'),
            'n':len(past),'lower':round(lower,2),'upper':round(upper,2),'actual':round(actual,2),'center':round(center,2),'month':latest['month']}

def build(out=None):
    out=Path(out or ROOT/'preview'); out.mkdir(parents=True,exist_ok=True)
    source=DATA/'retail_market_history_20260911.json'; retail=json.loads(source.read_text(encoding='utf-8'))
    grouped=defaultdict(list); codes={}; daily={}
    for file in sorted(RAW.glob('farm_*.json')):
        for r in json.loads(file.read_text(encoding='utf-8'))['rows']:
            day=parse_date(r.get('交易日期')); price=number(r.get('平均價')); volume=number(r.get('交易量'))
            if day and price and volume:
                key=(str(r.get('市場代號')),str(r.get('作物代號')),day)
                daily[key]=r
    for (market,code,day),r in daily.items():
        grouped[(code,day[:7])].append(r); codes[code]=r['作物名稱']
    monthly={}
    for (code,month),rows in grouped.items():
        v=sum(float(r['交易量']) for r in rows)
        monthly[(code,month)]=sum(float(r['平均價'])*float(r['交易量']) for r in rows)/v
    months=sorted(retail['surveys']); latest=retail['surveys'][months[-1]]
    items=[]
    # Candidate mappings are disclosed, never silently approved as identical grades.
    candidate={'高麗菜':'甘藍','小白菜':'小白菜','牛番茄':'番茄','絲瓜':'絲瓜','小黃瓜':'花胡瓜','木瓜':'木瓜','香蕉':'香蕉','芭樂':'番石榴'}
    for entry in latest['items']:
        name=entry['name']; needle=next((v for k,v in candidate.items() if name.startswith(k)),None)
        candidates=[c for c,n in codes.items() if needle and needle in n]
        # Pick no arbitrary grade: display candidates but require explicit review.
        code=candidates[0] if len(candidates)==1 else None
        points=[]; records=[]
        for month in months:
            row=next((r for r in retail['surveys'][month]['items'] if r['name']==name),None)
            obs=row['observations'] if row else []
            prices=[number(o['normalized_price']) for o in obs]; prices=[p for p in prices if p]
            points.append({'month':month,'retail':sum(prices)/len(prices)/.6 if prices else None,
                           'wholesale':monthly.get((code,month)) if code else None,
                           'low':min(prices)/.6 if prices else None,'high':max(prices)/.6 if prices else None,'n':len(prices)})
            for o in obs: records.append({'month':month,**o})
        item={'id':'retail-'+str(len(items)), 'name':name,'category':entry['category'],'kind':'retail',
              'unit':'元／公斤','source':'臺南市傳統市場訪查表','points':points,'records':records,
              'mapping':'候選批發品項：'+ '、'.join(codes[c]+' ['+c+']' for c in candidates) if candidates else '尚無確認的同規格批發對應',
              'approved':False,'market':'當月受訪市場均價','candidates':[{'code':c,'name':codes[c]} for c in candidates]}
        item['assessment']=assess(points,False); items.append(item)
    # Preserve market-specific official wholesale series rather than aggregate all names/dates.
    for code,name in sorted(codes.items()):
        points=[{'month':m,'wholesale':v} for (c,m),v in sorted(monthly.items()) if c==code]
        rows=[r for (market,c,day),r in sorted(daily.items()) if c==code]
        last=rows[-1]; previous=rows[-2] if len(rows)>1 else None
        items.append({'id':'farm-'+code,'name':name,'category':'西螺批發','kind':'farm','unit':'元／公斤','market':'西螺鎮','code':code,
            'source':'農業部農產品交易行情','mapping':'同市場同作物代碼；均價按交易量加權','points':points,'records':[],
            'latest_day':parse_date(last['交易日期']),'latest_price':float(last['平均價']),
            'previous_day':parse_date(previous['交易日期']) if previous else None,
            'change':(float(last['平均價'])/float(previous['平均價'])-1)*100 if previous and number(previous['平均價']) else None,
            'assessment':{'status':'批發參考','reason':'尚無確認配對的零售規格，不單憑批發走勢判定零售異常。','n':len(points)}})
    ricefile=RAW/'rice.json'
    if not ricefile.exists():
        files=sorted(DATA.glob('rice_*.json')); ricerows=json.loads(files[-1].read_text(encoding='utf-8')) if files else []
    else: ricerows=json.loads(ricefile.read_text(encoding='utf-8'))['rows']
    ricenames={'japt':'稉種白米（蓬萊米）','tsait':'硬秈白米','sangt':'軟秈白米','glutrt':'圓糯白米','glutlt':'長糯白米'}
    for suffix,name in ricenames.items():
        pairs={}
        for r in ricerows:
            city=str(r.get('CityName',r.get('name',''))).strip().replace('台','臺'); day=parse_date(r.get('pt_date_day'))
            rp=number(r.get('pt_1'+suffix,r.get('pt_1'+suffix+'_price'))); wp=number(r.get('pt_2'+suffix,r.get('pt_2'+suffix+'_price')))
            if city=='臺南市' and day and rp and wp: pairs[day]=(rp,wp/100)
        buckets=defaultdict(list)
        for day,prices in sorted(pairs.items()): buckets[day[:7]].append(prices)
        points=[{'month':m,'retail':sum(p[0] for p in ps)/len(ps),'wholesale':sum(p[1] for p in ps)/len(ps),'n':len(ps)} for m,ps in sorted(buckets.items())]
        items.append({'id':'rice-'+suffix,'name':name,'category':'米價','kind':'rice','unit':'元／公斤','market':'臺南市','source':'農糧署糧價查詢','mapping':'同縣市、米種、日期，躉售每百公斤已換算','approved':True,'points':points,'records':[], 'assessment':assess(points)})
        ordered=sorted(pairs.items())
        if ordered:
            item=items[-1]; item.update(latest_day=ordered[-1][0],latest_price=ordered[-1][1][0])
            if len(ordered)>1: item.update(previous_day=ordered[-2][0],change=(ordered[-1][1][0]/ordered[-2][1][0]-1)*100)
    # Existing livestock/poultry history retained with actual source dates, not fetch dates.
    for prefix,datekey,fields in [('poultry','日期',{'白肉雞(2.0Kg以上)':'白肉雞 2.0Kg 以上','白肉雞(1.75-1.95Kg)':'白肉雞 1.75–1.95Kg','白肉雞(門市價高屏)':'白肉雞高屏門市','雞蛋(產地)':'雞蛋產地價','雞蛋(大運輸價)':'雞蛋大運輸價'}),('livestock','交易日期',{'規格豬-平均價格':'毛豬規格豬'})]:
        ds={}
        for file in sorted(DATA.glob(prefix+'_*.json')):
            for r in json.loads(file.read_text(encoding='utf-8')):
                day=parse_date(r.get(datekey,r.get('日期')))
                if day:
                    for key,name in fields.items():
                        val=number(r.get(key,r.get('雞蛋(產地價)') if key=='雞蛋(產地)' else None))
                        if val: ds[(key,day,str(r.get('市場名稱','')))]=val
        for key,name in fields.items():
            markets=sorted({m for k,d,m in ds if k==key}) or ['']
            for market in markets:
                seq=[(d,v/(.6 if prefix=='poultry' else 1)) for (k,d,m),v in sorted(ds.items()) if k==key and m==market]
                bucket=defaultdict(list)
                for day,val in seq: bucket[day[:7]].append(val)
                ps=[{'month':m,'reference':sum(v)/len(v),'n':len(v)} for m,v in sorted(bucket.items())]
                item={'id':prefix+key+market,'name':name,'category':'畜禽蛋','kind':'reference','unit':'元／公斤','market':market or '來源報價','source':'農業部畜禽行情','points':ps,'records':[],
                    'mapping':('家禽蛋原價元／台斤除以 0.6；' if prefix=='poultry' else '同市場毛豬活體；')+'與零售部位／分級不同，不自動計算價差。月值為有效報價日簡單平均，非成交量加權。',
                    'assessment':{'status':'規格待配對','reason':'來源單位已核實；活體、部位及分級不同，停用批零異常判定。','n':len(ps)}}
                if seq:
                    item.update(latest_day=seq[-1][0],latest_price=seq[-1][1])
                    if len(seq)>1: item.update(previous_day=seq[-2][0],change=(seq[-1][1]/seq[-2][1]-1)*100)
                items.append(item)
    fish={}
    for file in sorted(DATA.glob('aquatic_*.json')):
        for r in json.loads(file.read_text(encoding='utf-8')):
            day=parse_date(r.get('交易日期')); market=r.get('市場名稱'); name=r.get('魚貨名稱','')
            if market in ('台南','佳里','新營') and day and any(n in name for n in ('吳郭魚','虱目魚','蛤','蚵','牡蠣','白蝦','鮭魚')) and number(r.get('平均價')) and number(r.get('交易量')):
                fish[(market,str(r.get('品種代碼')),day)]=r
    for market,code in sorted({(m,c) for m,c,d in fish}):
        seq=[(d,r) for (m,c,d),r in sorted(fish.items()) if m==market and c==code]
        buckets=defaultdict(list)
        for d,r in seq: buckets[d[:7]].append(r)
        ps=[{'month':m,'reference':sum(float(r['平均價'])*float(r['交易量']) for r in rs)/sum(float(r['交易量']) for r in rs),'n':len(rs)} for m,rs in sorted(buckets.items())]
        last=seq[-1]; item={'id':'fish-'+market+code,'name':last[1]['魚貨名稱'],'category':'魚貨','kind':'reference','unit':'元／公斤','market':market,'source':'農業部漁產品交易行情','points':ps,'records':[],
            'mapping':'同市場同品種代碼，按已取得報價交易量加權；僅為快照涵蓋期間，非完整歷史。全魚與魚肚／分切肉不直接配對。',
            'latest_day':last[0],'latest_price':float(last[1]['平均價']),
            'assessment':{'status':'規格待配對','reason':'需核對零售規格與分切成本；不啟用批零異常判定。','n':len(ps)}}
        if len(seq)>1: item.update(previous_day=seq[-2][0],change=(float(last[1]['平均價'])/float(seq[-2][1]['平均價'])-1)*100)
        items.append(item)
    status=json.loads((RAW/'fetch-status.json').read_text(encoding='utf-8')) if (RAW/'fetch-status.json').exists() else {'errors':['尚未連線更新正式交易行情']}
    for item in items:
        item['source_url']={'farm':'https://data.gov.tw/dataset/8066','rice':'https://data.gov.tw/dataset/17092','reference':'https://data.gov.tw/dataset/7536' if item['id'].startswith('poultry') else 'https://m.moa.gov.tw/Transaction/AnimalTrans/Index'}.get(item['kind'],'')
        if item['id'].startswith('fish-'): item['source_url']='https://m.moa.gov.tw/Transaction/AquaticTrans/Index'
        if item['kind']=='rice' and any('糧價' in e for e in status['errors']):
            item['assessment'].update(status='來源更新失敗',reason='保留快照供查詢，本次不作價格異常判定。')
    sources=[dict(s) for s in SOURCES]
    sources[2].update(state=f'已匯入 {months[0]} 至 {months[-1]}，共 {len(months)} 個月',
        use='28 商品；市場及有效報價筆數逐月不同，跨期均價可能受樣本組成影響。2024-01 原表缺市場欄名，僅納入整體均價、不推定市場。批發缺期不補值，仍須核實規格及配對歷史後才能建立價差警示。')
    add_sources(ROOT,items,sources,number,parse_date)
    matching=match_items(items)
    files=[source,*sorted(RAW.glob('*.json')),*sorted(DATA.glob('poultry_*.json')),*sorted(DATA.glob('livestock_*.json')),*sorted(DATA.glob('aquatic_*.json'))]
    manifest=[{'file':str(f.relative_to(ROOT)), 'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]
    payload={'generated_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),'policy':POLICY,'sources':sources,'matching':matching,'items':items,'fetch_status':status,
             'retail_months':months,'markets':sorted({market for s in retail['surveys'].values() for market in s['markets'] if not market.startswith('待確認')}),
             'retail_import_audit':retail.get('import_audit',{}),'retail_source_files':retail.get('historical_sources',[]),
             'draft':out.resolve()!=ROOT.resolve(),'source_manifest':manifest}
    dump(out/'monitor-data.json',payload)
    template=(ROOT/'web'/'monitor.html').read_text(encoding='utf-8')
    # Embedded data supports a local preview without a web server; production also serves JSON for refresh polling.
    template=template.replace('/*DATA*/',json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c'))
    for route in ('index.html','market.html','trend.html','xiluo.html'):
        (out/route).write_text(template,encoding='utf-8')
    print(f'Built {len(items)} series, {len(daily)} verified daily quotes, output {out}',flush=True)
    return payload

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--fetch',action='store_true'); p.add_argument('--start',default='2026-01-01'); p.add_argument('--out'); args=p.parse_args()
    if args.fetch: fetch(date.fromisoformat(args.start),date.today())
    build(args.out)
