#!/usr/bin/env python3
"""Download official wholesale-market history used by the public trend page."""
import argparse, html, json, re, time
from datetime import date, datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; URL="https://amis.afa.gov.tw/veg/VegProdDayTransInfo.aspx"
ROW=re.compile(r"^([A-Z]{1,4}\d+\s+.+?)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+[+-]\s*[\d.]+\s+[\d,]+",re.S); TAG=re.compile(r"<[^>]+>")
def field(page,name):
    found=re.search(rf'name=\"{re.escape(name)}\"[^>]*value=\"([^\"]*)\"',page); return html.unescape(found.group(1)) if found else ""
def clean(value): return re.sub(r"\s+"," ",html.unescape(TAG.sub(" ",value).replace("&nbsp;"," "))).strip()
def fetch_day(opener,day):
    page=opener.open(Request(URL,headers={"User-Agent":"taiwan-price-report"}),timeout=60).read().decode("utf-8","replace")
    roc=f"{day.year-1911:03d}/{day:%m/%d}"
    form={"__VIEWSTATE":field(page,"__VIEWSTATE"),"__VIEWSTATEGENERATOR":field(page,"__VIEWSTATEGENERATOR"),"__EVENTVALIDATION":field(page,"__EVENTVALIDATION"),"ctl00$contentPlaceHolder$ucDateScope$rblDateScope":"D","ctl00$contentPlaceHolder$ucSolarLunar$radlSolarLunar":"S","ctl00$contentPlaceHolder$txtSTransDate":roc,"ctl00$contentPlaceHolder$txtETransDate":roc,"ctl00$contentPlaceHolder$hfldMarketNo":"","ctl00$contentPlaceHolder$hfldProductNo":"","ctl00$contentPlaceHolder$hfldProductType":"","ctl00$contentPlaceHolder$btnQuery":"查詢"}
    result=opener.open(Request(URL,data=urlencode(form).encode(),headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":"taiwan-price-report"}),timeout=90).read().decode("utf-8","replace")
    rows=[]
    for raw in re.findall(r"<tr[^>]*>(.*?)</tr>",result,re.S|re.I):
        match=ROW.match(clean(raw))
        if match:
            name=re.sub(r"^[A-Z]{1,4}\d+\s+","",match.group(1)).strip(); price=float(match.group(5).replace(",",""))
            if name and price>0: rows.append({"PRODUCTNAME":name,"AVGPRICE":f"{price:.2f}","ORGNAME":"農糧署批發市場交易行情"})
    return rows
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--from",dest="start",default="2026-08-01"); parser.add_argument("--to",dest="end",default=date.today().isoformat()); args=parser.parse_args()
    start=datetime.strptime(args.start,"%Y-%m-%d").date(); end=datetime.strptime(args.end,"%Y-%m-%d").date(); DATA.mkdir(exist_ok=True); opener=build_opener(HTTPCookieProcessor(CookieJar())); day=start; saved=skipped=0
    while day<=end:
        target=DATA/f"wholesale_{day:%Y%m%d}.json"
        if target.exists(): skipped+=1
        else:
            rows=fetch_day(opener,day)
            if rows: target.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8"); saved+=1
            time.sleep(.15)
        day+=timedelta(days=1)
    print(f"Backfill complete: saved {saved} trading days; skipped {skipped} existing days.")
if __name__=="__main__": main()
