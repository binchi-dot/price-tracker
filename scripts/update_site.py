#!/usr/bin/env python3
"""Rebuild the public static report from the five MOA price feeds."""
import html
import json
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
if __name__ == '__main__': main()
