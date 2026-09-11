"""Additional official sources and reviewed commodity-family matching rules."""
import calendar
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

BASE='https://data.moa.gov.tw/Service/OpenData/FromM/'
APIS=[('native_red','紅羽土雞',BASE+'PoultryTransLocalRedChickenData.aspx','https://data.moa.gov.tw/open_detail.aspx?id=080'),
      ('native_black','黑羽土雞',BASE+'PoultryTransLocalBlackChickenData.aspx','https://data.moa.gov.tw/open_detail.aspx?id=081')]
FRUITS=('蘋果','木瓜','番石榴','奇異果','香蕉')

def fetch_extra(root, request, dump, parse_date, start, end):
    raw=root/'data'/'verified'; errors=[]; reports=[]
    for key,name,url,doc in APIS:
        try:
            rows=request(url)
            clean=[r for r in rows if parse_date(r.get('日期')) and start.isoformat()<=parse_date(r['日期'])<=end.isoformat()]
            if not clean: raise ValueError('本期範圍無有效日期資料')
            dump(raw/(key+'.json'),{'source':url,'rows':clean,'fetched_at':datetime.now().isoformat()})
            reports.append({'name':name,'rows':len(clean),'latest':max(parse_date(r['日期']) for r in clean)})
        except Exception as e: errors.append(name+'：'+str(e))
    try:
        rows=request(BASE+'SheepTransData.aspx')
        clean=[r for r in rows if parse_date(r.get('transDate')) and start.isoformat()<=parse_date(r['transDate'])<=end.isoformat()]
        if not clean:raise ValueError('無有效日期資料')
        dump(raw/'sheep.json',{'source':BASE+'SheepTransData.aspx','rows':clean,'fetched_at':datetime.now().isoformat()})
        reports.append({'name':'市場羊隻日行情','rows':len(clean),'latest':max(parse_date(r['transDate']) for r in clean)})
    except Exception as e:errors.append('羊隻行情：'+str(e))
    cursor=start.replace(day=1)
    while cursor<=end:
        target=raw/f'fruit_{cursor:%Y%m}.json'
        last=min(end,date(cursor.year,cursor.month,calendar.monthrange(cursor.year,cursor.month)[1]))
        if not (target.exists() and last<end.replace(day=1)):
            try:
                rows=[]; seen=set()
                for skip in range(0,100000,1000):
                    params={'StartDate':f'{cursor.year-1911}.{cursor:%m.%d}','EndDate':f'{last.year-1911}.{last:%m.%d}','Market':'高雄市','$top':1000,'$skip':skip}
                    batch=request(BASE+'FarmTransData.aspx?'+urlencode(params))
                    sig=hashlib.sha256(json.dumps(batch,sort_keys=True).encode()).hexdigest()
                    if sig in seen: raise ValueError('分頁重複')
                    seen.add(sig); rows.extend(batch)
                    if len(batch)<1000: break
                else: raise ValueError('頁數超限')
                clean=[r for r in rows if r.get('市場名稱')=='高雄市' and any(n in (r.get('作物名稱') or '') for n in FRUITS) and cursor.isoformat()<=(parse_date(r.get('交易日期')) or '')<=last.isoformat()]
                if not clean: raise ValueError('指定市場水果無有效資料')
                dump(target,{'source':BASE+'FarmTransData.aspx','rows':clean,'fetched_at':datetime.now().isoformat()})
                print(f'Kaohsiung fruit {cursor:%Y-%m}: {len(clean)}',flush=True)
            except Exception as e: errors.append(f'高雄水果 {cursor:%Y-%m}：{e}')
        cursor=(cursor.replace(day=28)+timedelta(days=4)).replace(day=1)
    dump(raw/'extra-status.json',{'checked_at':datetime.now().isoformat(),'errors':errors,'reports':reports})
    return errors

def add_sources(root, items, sources, number, parse_date):
    raw=root/'data'/'verified'
    for key,name,url,doc in APIS:
        file=raw/(key+'.json'); series=defaultdict(dict)
        if file.exists():
            for r in json.loads(file.read_text(encoding='utf8'))['rows']:
                day=parse_date(r.get('日期'))
                for field,value in r.items():
                    if day and name in field and number(value): series[field][day]=number(value)/.6
        for field,values in sorted(series.items()):
            items.append(reference(key+'-'+field,field,'南部' if '南雞' in field else '中部' if '中區' in field else '北部',name,doc,values))
        sources.append({'name':name+' API','url':url,'state':'已取得資料' if series else '介接待補資料','use':'來源說明：'+doc+'；原價每 600 公克換算每公斤。產地整雞與零售分切部位僅作上游參考。'})
    sheep=defaultdict(dict); sheepfile=raw/'sheep.json'
    if sheepfile.exists():
        for r in json.loads(sheepfile.read_text(encoding='utf8'))['rows']:
            d=parse_date(r.get('transDate')); v=number(r.get('avgPrice'))
            if d and v and r.get('productName'):sheep[(str(r['marketID']),r['name'],str(r['productID']),r['productName'])][d]=v
    for (marketid,market,code,name),values in sorted(sheep.items()):
        item=reference('sheep-'+marketid+'-'+code,name,market,'市場羊隻日行情',BASE+'SheepTransData.aspx',values)
        item['mapping']='同市場／產品代碼活羊每公斤報價，按快照內有效報價日取平均；非完整歷史，也不是分切羊肉價格。'
        item['assessment']['reason']='活羊與分切羊肉交易層級不同，不計批零價差率。'
        items.append(item)
    sources.append({'name':'市場羊隻日行情 API','url':BASE+'SheepTransData.aspx','state':'已取得資料' if sheep else '介接待補資料','use':'官方資料集 https://data.gov.tw/dataset/17327；活羊每公斤價，只作零售羊肉上游趨勢參考，不冒充同部位批發價。'})
    for name,endpoint in [('糧價','RicepriceData'),('白肉雞／蛋','PoultryTransData'),('毛豬','AnimalTransData'),('魚貨','AquaticTransData')]:
        sources.append({'name':name+' API','url':BASE+endpoint+'.aspx','state':'既有介接','use':'每週更新時重新取得；原始交易日、價格單位與可配對期間依各品項顯示，無資料不補零。'})
    fruits=defaultdict(dict)
    for file in sorted(raw.glob('fruit_*.json')):
        for r in json.loads(file.read_text(encoding='utf8'))['rows']:
            day=parse_date(r.get('交易日期'))
            if day and number(r.get('平均價')) and number(r.get('交易量')): fruits[(str(r['作物代號']),r['作物名稱'])][day]=r
    for (code,name),rows in sorted(fruits.items()):
        bucket=defaultdict(list)
        for d,r in rows.items(): bucket[d[:7]].append(r)
        item=reference('fruit-'+code,name,'高雄市','農產品交易行情',BASE+'FarmTransData.aspx',{d:number(r['平均價']) for d,r in rows.items()})
        item.update(kind='farm',category='高雄水果批發',code=code)
        item['points']=[{'month':m,'wholesale':sum(float(r['平均價'])*float(r['交易量']) for r in rs)/sum(float(r['交易量']) for r in rs),'n':len(rs)} for m,rs in sorted(bucket.items())]
        item['mapping']='高雄市同作物代碼，以有效交易量加權；不同品種、產地分開。'
        item['assessment']={'status':'批發參考','reason':'正式批發市場行情；與零售配對仍需核對品種、等級、產地與包裝。','n':len(item['points'])}
        items.append(item)
    sources.append({'name':'高雄水果交易 API','url':BASE+'FarmTransData.aspx','state':'已取得資料' if fruits else '介接待補資料','use':'補足西螺蔬菜市場未涵蓋的蘋果、木瓜、番石榴、奇異果與香蕉。依市場／作物代碼分列。'})

def reference(id,name,market,source,url,values):
    seq=sorted(values.items()); bucket=defaultdict(list)
    for d,v in seq: bucket[d[:7]].append(v)
    item={'id':id,'name':name,'market':market,'source':source,'source_url':url,'category':'畜禽蛋','kind':'reference','unit':'元／公斤','records':[],
          'points':[{'month':m,'reference':sum(v)/len(v),'n':len(v)} for m,v in sorted(bucket.items())],
          'mapping':'依實際報價日取月平均；整雞產地報價，不是分切部位批發價。',
          'assessment':{'status':'上游參考','reason':'交易層級與部位不同，不啟用批零警示。','n':len(bucket)}}
    if seq:
        item.update(latest_day=seq[-1][0],latest_price=seq[-1][1])
        if len(seq)>1:item.update(previous_day=seq[-2][0],change=(seq[-1][1]/seq[-2][1]-1)*100)
    return item

# Order is specific-to-general. These are curated aliases, not fuzzy string distance.
RULES=[('高麗菜',r'^甘藍','family'),('小白菜',r'^小白菜','family'),('牛番茄',r'番茄.*牛番茄','family'),('絲瓜',r'^絲瓜','family'),('小黃瓜',r'^花胡瓜','family'),
 ('蘋果',r'蘋果','family'),('木瓜',r'^木瓜','family'),('芭樂',r'番石榴','family'),('奇異果',r'奇異果','family'),('香蕉',r'^香蕉','family'),
 ('梅花肉',r'毛豬規格豬','upstream'),('五花肉',r'毛豬規格豬','upstream'),('里肌肉',r'毛豬規格豬','upstream'),
 ('土雞',r'紅羽土雞|黑羽土雞','upstream'),('肉雞',r'^白肉雞','upstream'),('散裝蛋',r'雞蛋產地價|雞蛋大運輸價','family'),
 ('虱目魚肚',r'^虱目魚肚$','family'),('蚵',r'蚵|牡蠣','family'),('蛤蜊',r'^文蛤','family'),('鮭魚',r'^鮭魚(?:\(凍\))?$','family'),('吳郭魚',r'^吳郭魚$','family'),('活白蝦',r'^白蝦$','family'),('本土羊',r'羊','upstream')]

def match_items(items):
    available=[i for i in items if i['kind'] in ('farm','reference') and i['points']]
    for item in items:
        if item['kind']!='retail':continue
        rule=next((r for r in RULES if item['name'].startswith(r[0])),None)
        fish_names=('虱目魚肚','蚵','蛤蜊','鮭魚','吳郭魚','活白蝦')
        def compatible(i):
            if not rule:return False
            if rule[0] in fish_names:return i['id'].startswith('fish-')
            if rule[0] in ('梅花肉','五花肉','里肌肉'):return i['id'].startswith('livestock')
            if rule[0]=='土雞':return i['id'].startswith('native_')
            if rule[0]=='本土羊':return i['id'].startswith('sheep-')
            if rule[0] in ('肉雞','散裝蛋'):return i['id'].startswith('poultry')
            return i['kind']=='farm'
        matches=[i for i in available if compatible(i) and re.search(rule[1],i['name'])]
        def priority(i):
            local=0 if i['market'] in ('台南','臺南市','臺南安南','台南市','台南安南','西螺鎮','南部') else 1
            frozen=1 if '凍' in i['name'] else 0
            return local,frozen,i['name'],i['market'],i['id']
        matches.sort(key=priority)
        for matched in matches:
            aliases=matched.setdefault('aliases',[])
            if rule[0] not in aliases:aliases.append(rule[0])
        level=rule[2] if rule else 'none'
        reason='同商品類別／別名對應；品種、等級、產地、鮮凍或包裝仍需核對。' if level=='family' else '部位／活體及交易層級不同；只看上游走勢，不計批零價差率。'
        item['candidates']=[{'id':i['id'],'code':i.get('code',i['id']),'name':i['name'],'market':i['market'],'level':level,'reason':reason,'url':i.get('source_url',''),'rule_version':'2026-09-10-v2'} for i in matches]
        item['default_comparison']=matches[0]['id'] if matches else ''
        item['comparison_level']=level if matches else 'none'
        item['mapping']=reason if matches else '尚未找到可驗證的同類別來源；不以不相干商品湊配對。'
        item['assessment']={'status':'同類商品參考' if matches and level=='family' else '上游走勢參考' if matches else '待補來源','reason':item['mapping'],'n':0}
        for p in item['points']:p['wholesale']=None
    return {'retail_items':sum(i['kind']=='retail' for i in items),'matched':sum(i['kind']=='retail' and bool(i.get('candidates')) for i in items),'unmatched':[i['name'] for i in items if i['kind']=='retail' and not i.get('candidates')]}
