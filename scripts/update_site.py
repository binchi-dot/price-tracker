#!/usr/bin/env python3
"""Rebuild the public static report from the five MOA price feeds."""
import html
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA, HISTORY = ROOT / "data", ROOT / "history"
APIS = {"wholesale":"https://data.moa.gov.tw/Service/OpenData/TransService.aspx?UnitId=WVOiWSdDjWxx", "rice":"https://data.moa.gov.tw/Service/OpenData/FromM/RicepriceData.aspx", "livestock":"https://data.moa.gov.tw/Service/OpenData/FromM/AnimalTransData.aspx", "aquatic":"https://data.moa.gov.tw/Service/OpenData/FromM/AquaticTransData.aspx", "poultry":"https://data.moa.gov.tw/Service/OpenData/FromM/PoultryTransData.aspx"}
CATS = {"葉菜類":("白菜","菠菜","萵苣","甘藍","高麗菜","油菜"), "果菜類":("蕃茄","胡瓜","茄子","甜椒","青椒"), "根莖類":("馬鈴薯","胡蘿蔔","洋蔥","蒜頭","生薑","青蔥","辣椒")}
FRUIT = ("鳳梨","木瓜","芒果","西瓜","葡萄","梨","香蕉","酪梨")
FISH = ("吳郭魚","尼羅紅魚","鯖魚","白帶魚","虱目魚","鱸魚","草魚","鰱魚","鯉魚","石斑","蝦","蛤")
TREND_ITEMS = ("小白菜", "甘藍", "胡瓜", "牛蕃茄", "木瓜", "鳳梨", "西瓜", "洋蔥", "青蔥")

def get(url):
    with urlopen(Request(url, headers={"User-Agent":"taiwan-price-report"}), timeout=45) as r: return json.load(r)
def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def avg(rows, name_key, price_key):
    grouped = {}
    for row in rows:
        name, price = row.get(name_key), num(row.get(price_key))
        if name and price and price > 0: grouped.setdefault(name, []).append(price)
    return {name: round(sum(values)/len(values), 2) for name, values in grouped.items()}
def table(items, old):
    if not items: return "<p>本次資料尚無符合項目。</p>"
    rows=[]
    for name, price in sorted(items.items()):
        before=old.get(name)
        if before:
            pct=(price-before)/before*100; note=f"{pct:+.2f}%"; css="up" if pct>0 else "down" if pct<0 else "stable"
        else: note,css="首次建立基準","stable"
        rows.append(f"<tr><td>{html.escape(name)}</td><td>{price:.2f} 元/公斤</td><td class='{css}'>{note}</td></tr>")
    return "<table><thead><tr><th>品項</th><th>平均價格</th><th>較前次</th></tr></thead><tbody>"+"".join(rows)+"</tbody></table>"
def render(date, veg, oldveg, fish, oldfish, rice, pigs, poultry):
    blocks=[]
    for label, words in CATS.items(): blocks.append(f"<h3>【{label}】</h3>"+table({k:v for k,v in veg.items() if any(w in k for w in words)},oldveg))
    fruit={k:v for k,v in veg.items() if any(w in k for w in FRUIT)}; fish={k:v for k,v in fish.items() if any(w in k for w in FISH)}
    rv=[num(x.get(k)) for x in rice for k in ("pt_1japt","pt_1tsait")]; rv=[x for x in rv if x and x>0]
    pv=[num(x.get("規格豬-平均價格")) for x in pigs]; pv=[x for x in pv if x and x>0]
    bird=poultry[0] if poultry else {}
    birdtxt="<br>".join(f"{label}：{html.escape(str(bird.get(key,'無資料')))} 元/公斤" for label,key in (("白肉雞 2.0Kg 以上","白肉雞(2.0Kg以上)"),("白肉雞 1.75–1.95Kg","白肉雞(1.75-1.95Kg)"),("白肉雞門市價高屏","白肉雞(門市價高屏)"),("雞蛋（產地）","雞蛋(產地)")))
    rice_text=f"全國平均：{sum(rv)/len(rv):.2f} 元/公斤" if rv else "本次資料取得失敗"; pig_text=f"全國平均：{sum(pv)/len(pv):.2f} 元/公斤" if pv else "本次資料取得失敗"
    return f"""<!doctype html><html lang='zh-TW'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>臺灣每日物價報告｜{date}</title><style>body{{font-family:'Microsoft JhengHei',sans-serif;background:#f5f7fa;color:#1f2937;margin:0;padding:24px;line-height:1.6}}main{{max-width:1100px;margin:auto;background:#fff;padding:32px;border-radius:14px;box-shadow:0 3px 18px #0001}}nav a{{margin-right:18px;color:#0284c7;text-decoration:none;font-weight:bold}}h1{{color:#0284c7;border-bottom:3px solid #0ea5e9;padding-bottom:12px}}h2{{color:#059669;border-left:5px solid #10b981;padding-left:10px;margin-top:32px}}h3{{color:#b45309}}.info{{background:#eff6ff;border-left:4px solid #0ea5e9;padding:12px 16px;border-radius:6px}}table{{width:100%;border-collapse:collapse;margin:10px 0 18px}}th{{background:#0284c7;color:white;text-align:left}}th,td{{padding:9px;border-bottom:1px solid #e5e7eb}}.up{{color:#dc2626;font-weight:bold}}.down{{color:#059669;font-weight:bold}}.stable{{color:#6b7280}}footer{{color:#6b7280;text-align:center;margin-top:32px;font-size:.9rem}}</style><body><main><nav><a href='index.html'>今日報告</a><a href='trend.html'>趨勢圖</a><a href='history/index.html'>歷史報告</a></nav><h1>📊 臺灣每日物價報告</h1><div class='info'>報告日期：{date}<br>資料來源：農業部 5 項公開資料 API<br>排程：每日 14:00（台北時間）更新</div><h2>🥬 主要蔬果價格</h2>{''.join(blocks)}<h2>🍎 主要水果價格</h2>{table(fruit,oldveg)}<h2>🍚 米價</h2><div class='info'>{rice_text}</div><h2>🐷 豬價</h2><div class='info'>{pig_text}</div><h2>🐟 主要魚價</h2>{table(fish,oldfish)}<h2>🐔 雞價、蛋價</h2><div class='info'>{birdtxt}</div><footer>下次更新：明日 14:00（台北時間）</footer></main></body></html>"""
def spark(values, labels=None):
    if len(values) < 2: return "<span class='stable'>資料不足</span>"
    lo, hi=min(values),max(values); span=hi-lo or 1
    points=" ".join(f"{i*190/(len(values)-1):.1f},{48-(v-lo)*42/span:.1f}" for i,v in enumerate(values))
    labels = labels or [str(i + 1) for i in range(len(values))]
    axis = "<div class='axis'>" + "".join(f"<span>{html.escape(str(label))}</span>" for label in labels) + "</div>"
    return f"<svg viewBox='0 0 190 52' role='img' aria-label='價格走勢' style='width:100%;height:52px;display:block;margin:8px 0'><path d='M0 49H190' stroke='#dbeafe'/><polyline points='{points}' fill='none' stroke='#0284c7' stroke-width='2.5'/></svg>{axis}"
def render_trend():
    series={item:[] for item in TREND_ITEMS}; dates=[]
    for file in sorted(DATA.glob("wholesale_20*.json")):
        stamp=file.stem.rsplit("_",1)[1]
        try: prices=avg(json.loads(file.read_text(encoding="utf-8")),"PRODUCTNAME","AVGPRICE")
        except (json.JSONDecodeError, OSError): continue
        dates.append(stamp)
        for item in TREND_ITEMS:
            values=[v for name,v in prices.items() if item in name]
            if values: series[item].append((stamp,sum(values)/len(values)))
    usable=sorted(set(dates)); cards=[]
    for item, points in series.items():
        if not points: continue
        values=[v for _,v in points]; recent=values[-7:]; monthly=values[-30:]; change=(values[-1]-values[0])/values[0]*100 if values[0] else 0
        color="#dc2626" if change>0 else "#059669" if change<0 else "#6b7280"
        cards.append(f"<section style='border:1px solid #dbeafe;border-radius:10px;padding:14px'><strong style='font-size:1.1rem;color:#0369a1'>{html.escape(item)}</strong>{spark(values)}<div>最新：{values[-1]:.2f} 元/公斤</div><div>近 7 日均價：{sum(recent)/len(recent):.2f}</div><div>近 30 日均價：{sum(monthly)/len(monthly):.2f}</div><div style='color:{color};font-weight:bold'>期間變動：{change:+.2f}%</div></section>")
    period=f"{usable[0][:4]}-{usable[0][4:6]}-{usable[0][6:]} 至 {usable[-1][:4]}-{usable[-1][4:6]}-{usable[-1][6:]}" if usable else "尚無資料"
    body=f"""<!doctype html><html lang='zh-TW'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>物價趨勢圖｜臺灣每日物價報告</title><style>body{{font-family:'Microsoft JhengHei',sans-serif;background:#f5f7fa;color:#1f2937;margin:0;padding:24px;line-height:1.6}}main{{max-width:1100px;margin:auto;background:#fff;padding:32px;border-radius:14px;box-shadow:0 3px 18px #0001}}nav a{{margin-right:18px;color:#0284c7;text-decoration:none;font-weight:bold}}h1{{color:#0284c7;border-bottom:3px solid #0ea5e9;padding-bottom:12px}}h2{{color:#059669;border-left:5px solid #10b981;padding-left:10px;margin-top:32px}}.info{{background:#eff6ff;border-left:4px solid #0ea5e9;padding:12px 16px;border-radius:6px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}footer{{color:#6b7280;text-align:center;margin-top:32px;font-size:.9rem}}</style><body><main><nav><a href='index.html'>今日報告</a><a href='trend.html'>趨勢圖</a><a href='history/index.html'>歷史報告</a></nav><h1>📈 物價趨勢圖</h1><div class='info'>資料期間：{period}<br>可用交易日：{len(usable)} 天<br>歷史資料來源：農糧署批發市場交易行情；本頁會隨每日資料更新一併重建。</div><h2>主要蔬果走勢</h2><div class='cards'>{''.join(cards) or '<p>尚無足夠資料可顯示趨勢。</p>'}</div><footer>資料來源：農業部公開資料</footer></main></body></html>"""
    (ROOT/"trend.html").write_text(body,encoding="utf-8")
def main():
    now=datetime.now(ZoneInfo("Asia/Taipei")); stamp=now.strftime("%Y%m%d"); date=now.strftime("%Y-%m-%d"); DATA.mkdir(exist_ok=True); HISTORY.mkdir(exist_ok=True)
    feeds={name:get(url) for name,url in APIS.items()}
    for name,rows in feeds.items(): (DATA/f"{name}_{stamp}.json").write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    prior=sorted(DATA.glob("wholesale_*.json"))[-2:-1]; oldveg=oldfish={}
    if prior:
        oldveg=avg(json.loads(prior[0].read_text(encoding="utf-8")),"PRODUCTNAME","AVGPRICE"); oldstamp=prior[0].stem.rsplit("_",1)[1]; f=DATA/f"aquatic_{oldstamp}.json"
        if f.exists(): oldfish=avg(json.loads(f.read_text(encoding="utf-8")),"魚貨名稱","平均價")
    report=render(date,avg(feeds["wholesale"],"PRODUCTNAME","AVGPRICE"),oldveg,avg(feeds["aquatic"],"魚貨名稱","平均價"),oldfish,feeds["rice"],feeds["livestock"],feeds["poultry"])
    (ROOT/"index.html").write_text(report,encoding="utf-8"); (HISTORY/f"{stamp}.html").write_text(report,encoding="utf-8")
    links="".join(f"<li><a href='{p.name}'>{p.stem[:4]}-{p.stem[4:6]}-{p.stem[6:]}</a></li>" for p in sorted(HISTORY.glob("20*.html"),reverse=True))
    (HISTORY/"index.html").write_text(f"<!doctype html><meta charset='utf-8'><title>歷史物價報告</title><style>body{{font-family:'Microsoft JhengHei',sans-serif;max-width:800px;margin:40px auto;padding:20px}}a{{color:#0284c7}}</style><h1>📚 歷史物價報告</h1><ul>{links}</ul><p><a href='../index.html'>返回今日報告</a></p>",encoding="utf-8")
    render_trend()
def nav():
    return "<nav><a href='index.html'>今日報告</a><a href='trend.html'>詳盡趨勢</a><a href='market.html'>傳統市場／批發比價</a><a href='history/index.html'>歷史報告</a></nav>"


def page(title, body):
    return f"""<!doctype html><html lang='zh-TW'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title><style>
body{{font-family:'Microsoft JhengHei',sans-serif;background:#f5f7fa;color:#1f2937;margin:0;padding:24px;line-height:1.6}}main{{max-width:1160px;margin:auto;background:#fff;padding:32px;border-radius:14px;box-shadow:0 3px 18px #0001}}nav a{{margin-right:18px;color:#0284c7;text-decoration:none;font-weight:bold}}h1{{color:#0284c7;border-bottom:3px solid #0ea5e9;padding-bottom:12px}}h2{{color:#059669;border-left:5px solid #10b981;padding-left:10px;margin-top:32px}}h3{{color:#b45309}}.info{{background:#eff6ff;border-left:4px solid #0ea5e9;padding:12px 16px;border-radius:6px}}.warning{{background:#fff7ed;border-left-color:#f97316}}table{{width:100%;border-collapse:collapse;margin:10px 0 18px}}th{{background:#0284c7;color:white;text-align:left}}th,td{{padding:9px;border-bottom:1px solid #e5e7eb;vertical-align:top}}.up{{color:#dc2626;font-weight:bold}}.down{{color:#059669;font-weight:bold}}.stable{{color:#6b7280}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(225px,1fr));gap:14px}}.card{{border:1px solid #dbeafe;border-radius:10px;padding:14px}}.axis{{display:flex;justify-content:space-between;gap:4px;color:#64748b;font-size:.72rem;white-space:nowrap;overflow:hidden}}input{{font:inherit;padding:9px 12px;border:1px solid #93c5fd;border-radius:7px;width:min(420px,100%)}}small{{color:#6b7280}}.badge{{display:inline-block;padding:1px 7px;border-radius:10px;background:#dcfce7;color:#166534;font-size:.85em}}footer{{color:#6b7280;text-align:center;margin-top:32px;font-size:.9rem}}</style><body><main>{nav()}{body}<footer>資料來源：農業部公開資料與臺南市傳統市場訪查表；每日 14:00（台北時間）更新。</footer></main></body></html>"""


def delta(current, previous):
    if current is None or previous in (None, 0):
        return "<span class='stable'>首次建立基準</span>"
    change = (current - previous) / previous * 100
    css = "up" if change > 0 else "down" if change < 0 else "stable"
    return f"<span class='{css}'>{change:+.2f}%</span>"


def rice_breakdown(rows, previous_rows):
    labels = {"pt_1japt":"蓬萊米（零售）", "pt_1tsait":"臺灣米（零售）", "pt_1sangt":"長秈米（零售）", "pt_1glutrt":"圓糯米（零售）", "pt_1glutlt":"長糯米（零售）"}
    values = []
    for key, label in labels.items():
        nums = [num(row.get(key)) for row in rows]; nums = [x for x in nums if x and x > 0]
        old = [num(row.get(key)) for row in previous_rows]; old = [x for x in old if x and x > 0]
        if nums: values.append((label, sum(nums) / len(nums), sum(old) / len(old) if old else None))
    return "<table><thead><tr><th>米種</th><th>全國平均零售價</th><th>較前次</th></tr></thead><tbody>" + "".join(f"<tr><td>{label}</td><td>{price:.2f} 元/公斤</td><td>{delta(price, old)}</td></tr>" for label, price, old in values) + "</tbody></table>"


def retail_overview():
    history = retail_history()
    points = []
    for name in ("高麗菜", "小白菜", "牛番茄", "雞蛋", "土雞腿", "肉雞腿"):
        series = retail_series(history, name)
        if series:
            points.append(f"<section class='card'><strong>{name}</strong>{spark([v for _, v in series], [m[5:] + '月' for m,_ in series])}<div>1–8 月零售均價（元/台斤）</div><small>{'、'.join(f'{m[5:]}月 {v:.0f}' for m,v in series)}</small></section>")
    return "<h2>🧺 傳統市場數據與月趨勢</h2><div class='info'>已匯入臺南市 7 個傳統市場、115 年 1–8 月訪查資料。<a href='market.html'>查看各市場原始報價、供應情形與批零對照 →</a></div><div class='cards'>" + "".join(points) + "</div>"


def render(date, veg, oldveg, fish, oldfish, rice, oldrice, pigs, oldpigs, poultry, oldpoultry):
    blocks = []
    for label, words in CATS.items():
        blocks.append(f"<h3>【{label}】</h3>" + table({k:v for k,v in veg.items() if any(w in k for w in words)}, oldveg))
    fruit = {k:v for k,v in veg.items() if any(w in k for w in FRUIT)}
    fish = {k:v for k,v in fish.items() if any(w in k for w in FISH)}
    pig = [num(x.get("規格豬-平均價格")) for x in pigs]; pig = [x for x in pig if x and x > 0]
    oldpig = [num(x.get("規格豬-平均價格")) for x in oldpigs]; oldpig = [x for x in oldpig if x and x > 0]
    chicken_fields = (("白肉雞 2.0 公斤以上","白肉雞(2.0Kg以上)"),("白肉雞 1.75–1.95 公斤","白肉雞(1.75-1.95Kg)"),("白肉雞門市價（高屏）","白肉雞(門市價高屏)"),("雞蛋（產地）","雞蛋(產地)"))
    bird = poultry[0] if poultry else {}; oldbird = oldpoultry[0] if oldpoultry else {}
    chicken = "<table><thead><tr><th>品項／規格</th><th>價格</th><th>較前次</th></tr></thead><tbody>" + "".join(f"<tr><td>{label}</td><td>{html.escape(str(bird.get(key,'無資料')))} 元/公斤</td><td>{delta(num(bird.get(key)), num(oldbird.get(key)))}</td></tr>" for label,key in chicken_fields) + "</tbody></table>"
    pig_price = sum(pig)/len(pig) if pig else None; old_pig_price = sum(oldpig)/len(oldpig) if oldpig else None
    body = f"<h1>📊 臺灣每日物價報告</h1><div class='info'>報告日期：{date}<br>可直接搜尋蔬果、米種、雞肉或蛋價；完整的傳統市場資料與批零比較請至<a href='market.html'>市場比價</a>。</div><h2>🔎 品項搜尋</h2><input id='siteSearch' placeholder='例如：高麗菜、圓糯米、雞蛋、虱目魚'><small>　會篩選本頁各價格表。</small>{retail_overview()}<h2>🥬 更完整的主要蔬果價格</h2>{''.join(blocks)}<h2>🍎 主要水果價格</h2>{table(fruit,oldveg)}<h2>🍚 米價（依米種細分）</h2>{rice_breakdown(rice, oldrice)}<h2>🐷 豬價</h2><div class='info'>全國平均：{pig_price:.2f} 元/公斤　較前次：{delta(pig_price, old_pig_price)}</div><h2>🐟 主要魚價</h2>{table(fish,oldfish)}<h2>🐔 雞肉、蛋價（依規格／交易層級）</h2>{chicken}<script>siteSearch.addEventListener('input',()=>{{let q=siteSearch.value.trim().toLowerCase();document.querySelectorAll('tbody tr,.card').forEach(r=>r.hidden=q&&!r.innerText.toLowerCase().includes(q))}})</script>"
    return page(f"臺灣每日物價報告｜{date}", body)


def retail_history():
    file = DATA / "retail_market_history.json"
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else {"surveys": {}, "survey_months": []}


def retail_series(history, needle):
    points=[]
    for month in sorted(history["surveys"]):
        match = next((x for x in history["surveys"][month]["items"] if needle in x["name"] and x["retail_average"] is not None), None)
        if match: points.append((month, match["retail_average"]))
    return points


def render_market_comparison(latest_wholesale):
    history = retail_history(); surveys = history.get("surveys", {}); latest_month = max(surveys) if surveys else None
    survey = surveys.get(latest_month, {"items": [], "markets": []})
    aliases = {"高麗菜":"甘藍", "牛番茄":"牛蕃茄", "小黃瓜":"胡瓜", "木瓜":"木瓜", "香蕉":"香蕉", "小白菜":"小白菜", "絲瓜":"絲瓜", "吳郭魚":"吳郭魚", "蛤蜊":"蛤蜊", "活白蝦":"蝦"}
    rows=[]
    for item in survey["items"]:
        clean=re.sub(r"1(?:台)?斤.*$", "", item["name"])
        key=next((v for k,v in aliases.items() if k in clean), None)
        matches=[v for n,v in latest_wholesale.items() if key and key in n]
        wholesale=round(sum(matches)/len(matches),2) if matches else None
        normalized=round(item["retail_average"] / 0.6,2) if item["retail_average"] is not None and item["unit"]=="台斤" else None
        comparison=f"{normalized:.2f} 元/公斤" if normalized is not None else "原表計價，未換算"
        wholesale_text=f"{wholesale:.2f} 元/公斤" if wholesale is not None else "暫無同品項批發資料"
        detail="；".join(f"{o['market']}：{o['raw_price'] or '未報價'}（供應{history.get('supply_legend',{}).get(o['supply'],o['supply'] or '未填')}）" for o in item["observations"])
        rows.append(f"<tr data-search='{html.escape((item['category']+' '+item['name']+' '+clean).lower())}'><td>{html.escape(item['category'])}</td><td><b>{html.escape(item['name'])}</b><br><small>{html.escape(detail)}</small></td><td>{item['retail_average'] if item['retail_average'] is not None else '—'} 元/台斤<br><small>直接報價 {item['direct_quote_count']} 處</small></td><td>{comparison}</td><td>{wholesale_text}</td></tr>")
    cards=[]
    for item in survey["items"]:
        name = re.sub(r"1(?:台)?斤.*$", "", item["name"])
        points=retail_series(history,name)
        if points:
            vals=[v for _,v in points]; labels="、".join(f"{m[5:]}月 {v:.0f}" for m,v in points)
            direct=[o["normalized_price"] for o in item["observations"] if o["normalized_price"] is not None]
            spread=f"本月市場直接報價 {min(direct):.0f}–{max(direct):.0f} 元/台斤" if direct else "本月多為非標準包裝報價"
            cards.append(f"<section class='card' data-search='{html.escape(item['category']+' '+name)}'><strong>{html.escape(item['name'])}</strong>{spark(vals, [m[5:] + '月' for m,_ in points])}<div>{spread}</div><small>月均價：{labels}</small></section>")
    body=f"<h1>🧺 傳統市場零售價／批發價比對</h1><div class='info'>零售資料：臺南市傳統市場訪查表，{latest_month or '—'}，涵蓋 {len(survey.get('markets',[]))} 個市場、{len(survey.get('items',[]))} 項商品。每個品項皆已提供 1–8 月趨勢圖與月份軸。</div><div class='info warning'>批發資料為農業部最新批發行情；零售訪查是月資料，兩者日期不同。僅在商品與計價單位可合理對應時提供每公斤參考，不能視為同期價差或利潤。</div><h2>🔎 檢索品項</h2><input id='marketSearch' placeholder='輸入品項、類別或市場名稱，例如：雞蛋、蔬菜、蛤蜊'><h2>📋 {latest_month or ''} 零售訪查與批發參考</h2><table id='compare'><thead><tr><th>類別</th><th>商品與各市場原始報價</th><th>零售平均</th><th>換算每公斤</th><th>批發參考</th></tr></thead><tbody>{''.join(rows)}</tbody></table><h2>📈 全品項零售市場月趨勢（1–8 月）</h2><div class='cards'>{''.join(cards)}</div><script>marketSearch.addEventListener('input',()=>{{let q=marketSearch.value.trim().toLowerCase();document.querySelectorAll('#compare tbody tr,.card').forEach(e=>e.hidden=q&&!e.innerText.toLowerCase().includes(q))}})</script>"
    (ROOT / "market.html").write_text(page("傳統市場／批發價格比對", body), encoding="utf-8")


def render_trend():
    history=retail_history(); series={item:[] for item in TREND_ITEMS}; dates=[]
    for file in sorted(DATA.glob("wholesale_20*.json")):
        stamp=file.stem.rsplit("_",1)[1]
        try: prices=avg(json.loads(file.read_text(encoding="utf-8")),"PRODUCTNAME","AVGPRICE")
        except (json.JSONDecodeError, OSError): continue
        dates.append(stamp)
        for item in TREND_ITEMS:
            values=[v for name,v in prices.items() if item in name]
            if values: series[item].append((stamp,sum(values)/len(values)))
    cards=[]
    for item, points in series.items():
        if not points: continue
        vals=[v for _,v in points]; recent=vals[-7:]; monthly=vals[-30:]; change=(vals[-1]-vals[0])/vals[0]*100 if vals[0] else 0
        labels=[f"{p[4:6]}/{p[6:]}" for p,_ in points]
        cards.append(f"<section class='card' data-search='{item}'><strong>{item}｜批發</strong>{spark(vals, labels)}<div>最新 {vals[-1]:.2f} 元/公斤</div><div>近 7 日 {sum(recent)/len(recent):.2f}；近 30 日 {sum(monthly)/len(monthly):.2f}</div><div class='{'up' if change>0 else 'down' if change<0 else 'stable'}'>期間 {change:+.2f}%</div></section>")
    for name in ("高麗菜","小白菜","牛番茄","絲瓜","小黃瓜","雞蛋","土雞腿","肉雞腿"):
        points=retail_series(history,name)
        if points:
            vals=[v for _,v in points]
            cards.append(f"<section class='card' data-search='{name}'><strong>{name}｜零售</strong>{spark(vals, [m[5:] + '月' for m,_ in points])}<div>1–8 月平均（元/台斤）</div><div>{'、'.join(f'{m[5:]}月 {v:.0f}' for m,v in points)}</div></section>")
    period=f"{dates[0][:4]}-{dates[0][4:6]}-{dates[0][6:]} 至 {dates[-1][:4]}-{dates[-1][4:6]}-{dates[-1][6:]}" if dates else "尚無資料"
    body=f"<h1>📈 詳盡物價趨勢</h1><div class='info'>批發行情期間：{period}；零售市場趨勢：2026 年 1–8 月。趨勢頁在每日更新時連同批發資料重建。</div><h2>🔎 搜尋趨勢品項</h2><input id='trendSearch' placeholder='例如：高麗菜、雞蛋、木瓜'><h2>批發與零售趨勢</h2><div class='cards'>{''.join(cards)}</div><script>trendSearch.addEventListener('input',()=>{{let q=trendSearch.value.trim().toLowerCase();document.querySelectorAll('.card').forEach(e=>e.hidden=q&&!e.innerText.toLowerCase().includes(q))}})</script>"
    (ROOT / "trend.html").write_text(page("詳盡物價趨勢", body), encoding="utf-8")


def main():
    now=datetime.now(ZoneInfo("Asia/Taipei")); stamp=now.strftime("%Y%m%d"); date=now.strftime("%Y-%m-%d"); DATA.mkdir(exist_ok=True); HISTORY.mkdir(exist_ok=True)
    feeds={name:get(url) for name,url in APIS.items()}
    for name,rows in feeds.items(): (DATA/f"{name}_{stamp}.json").write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    prior=sorted(DATA.glob("wholesale_*.json"))[-2:-1]; oldveg=oldfish={}; oldrice=[]; oldpigs=[]; oldpoultry=[]
    if prior:
        oldveg=avg(json.loads(prior[0].read_text(encoding="utf-8")),"PRODUCTNAME","AVGPRICE"); oldstamp=prior[0].stem.rsplit("_",1)[1]; f=DATA/f"aquatic_{oldstamp}.json"
        if f.exists(): oldfish=avg(json.loads(f.read_text(encoding="utf-8")),"魚貨名稱","平均價")
        for name, target in (("rice", "oldrice"), ("livestock", "oldpigs"), ("poultry", "oldpoultry")):
            file = DATA / f"{name}_{oldstamp}.json"
            if file.exists():
                if target == "oldrice": oldrice = json.loads(file.read_text(encoding="utf-8"))
                elif target == "oldpigs": oldpigs = json.loads(file.read_text(encoding="utf-8"))
                else: oldpoultry = json.loads(file.read_text(encoding="utf-8"))
    wholesale=avg(feeds["wholesale"],"PRODUCTNAME","AVGPRICE")
    report=render(date,wholesale,oldveg,avg(feeds["aquatic"],"魚貨名稱","平均價"),oldfish,feeds["rice"],oldrice,feeds["livestock"],oldpigs,feeds["poultry"],oldpoultry)
    (ROOT/"index.html").write_text(report,encoding="utf-8"); (HISTORY/f"{stamp}.html").write_text(report,encoding="utf-8")
    links="".join(f"<li><a href='{p.name}'>{p.stem[:4]}-{p.stem[4:6]}-{p.stem[6:]}</a></li>" for p in sorted(HISTORY.glob("20*.html"),reverse=True))
    (HISTORY/"index.html").write_text(f"<!doctype html><meta charset='utf-8'><title>歷史物價報告</title><h1>歷史物價報告</h1><ul>{links}</ul><p><a href='../index.html'>返回今日報告</a></p>",encoding="utf-8")
    render_market_comparison(wholesale); render_trend()


if __name__ == '__main__': main()
