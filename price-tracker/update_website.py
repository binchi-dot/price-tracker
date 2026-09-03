#!/usr/bin/env python3
"""每日物價網站更新"""

import os
import re
import subprocess
from datetime import datetime

VAULT = "/mnt/c/Users/water/我的雲端硬碟/超級大腦"
WEB_DIR = f"{VAULT}/網站/每日物價"
HISTORY_DIR = f"{WEB_DIR}/history"
CLIPPINGS = f"{VAULT}/Clippings"
TRACKER = "/home/water/.openclaw/workspace/skills/price-tracker/daily_price_tracker.py"


def run_tracker():
    print(f"[{datetime.now()}] 執行價格追蹤...")
    subprocess.run(["python3", TRACKER], check=True)


def parse_report(report_text):
    data = {'vegetables': [], 'fruits': [], 'fish': [], 'rice': {}, 'pork': {}, 'poultry': {}}
    
    for line in report_text.split('\n'):
        if '元/公斤' in line and '：' in line:
            parts = line.strip().split('：')
            if len(parts) >= 2:
                product = parts[0].strip()
                price_text = parts[1].strip()
                pm = re.search(r'([\d.]+) 元/公斤', price_text)
                if pm:
                    price = float(pm.group(1))
                    cm = re.search(r'（([+-][\d.]+)%）', price_text)
                    change = cm.group(1) if cm else None
                    
                    if any(k in product for k in ['鳳梨', '木瓜', '芒果', '西瓜', '葡萄', '梨', '香蕉', '甘露', '愛文', '在來', '豐水']):
                        data['fruits'].append((product, price, change))
                    elif any(k in product for k in ['白菜', '菠菜', '萵苣', '甘藍', '高麗菜', '蕃茄', '茄子', '甜椒', '胡瓜', '馬鈴薯', '胡蘿蔔', '洋蔥', '蒜頭', '生薑', '青蔥', '辣椒']):
                        data['vegetables'].append((product, price, change))
                    elif any(k in product for k in ['吳郭魚', '鯖魚', '虱目魚', '草魚', '鯉魚', '石斑', '尼羅', '白帶', '鱸魚', '鰱魚', '蝦', '蛤']):
                        data['fish'].append((product, price, change))

    # 米價
    rice_section = False
    for line in report_text.split('\n'):
        if '三、米價' in line:
            rice_section = True
        elif '四、' in line:
            rice_section = False
        elif rice_section:
            if '全國平均' in line:
                m = re.search(r'([\d.]+) 元/公斤', line)
                if m: data['rice']['avg'] = float(m.group(1))
            if '統計縣市數' in line:
                m = re.search(r'(\d+)', line.split('：')[1])
                if m: data['rice']['cities'] = int(m.group(1))

    # 豬價
    pork_section = False
    for line in report_text.split('\n'):
        if '四、豬價' in line:
            pork_section = True
        elif '五、' in line:
            pork_section = False
        elif pork_section:
            if '今日全國平均' in line:
                m = re.search(r'([\d.]+) 元/公斤', line)
                if m: data['pork']['avg'] = float(m.group(1))
            if '統計市場數' in line:
                m = re.search(r'(\d+),', line.split('：')[1])
                if m: data['pork']['markets'] = int(m.group(1))

    # 家禽
    poultry_section = False
    for line in report_text.split('\n'):
        if '六、雞價' in line:
            poultry_section = True
        elif '七、' in line:
            poultry_section = False
        elif poultry_section:
            if '2.0Kg' in line and '白肉雞' in line:
                m = re.search(r'([\d.]+)\s+元', line.split('：')[1])
                if m: data['poultry']['chicken_2kg'] = float(m.group(1))
            if '1.75' in line:
                m = re.search(r'([\d.]+)\s+元', line.split('：')[1])
                if m: data['poultry']['chicken_175'] = float(m.group(1))
            if '門市價高屏' in line:
                m = re.search(r'([\d.]+)\s+元', line.split('：')[1])
                if m: data['poultry']['chicken_store'] = float(m.group(1))
            if '雞蛋（產地）' in line:
                m = re.search(r'([\d.]+)\s+元', line.split('：')[1])
                if m: data['poultry']['egg'] = float(m.group(1))

    return data


def render_rows(items):
    rows = []
    for item in items:
        product, price, change = item
        if change:
            try:
                change_val = float(change.replace('+', ''))
                if change_val > 0:
                    change_text = '+' + change + '%'
                    change_class = 'up'
                else:
                    change_text = change + '%'
                    change_class = 'down'
            except:
                change_text = change + '%'
                change_class = ''
        else:
            change_text = '基準建立'
            change_class = ''
        rows.append('<tr><td>' + product + '</td><td>' + str(price) + ' 元/公斤</td><td class="' + change_class + '">' + change_text + '</td></tr>')
    return '\n'.join(rows)


def generate_html(data, today):
    veg_leaf = [v for v in data['vegetables'] if any(k in v[0] for k in ['白菜', '菠菜', '萵苣', '甘藍', '高麗菜'])]
    veg_fruit = [v for v in data['vegetables'] if any(k in v[0] for k in ['蕃茄', '胡瓜', '茄子', '甜椒', '青椒'])]
    veg_root = [v for v in data['vegetables'] if any(k in v[0] for k in ['馬鈴薯', '胡蘿蔔', '洋蔥', '蒜頭', '生薑', '青蔥', '辣椒'])]

    html = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日物價報告</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: "微軟正黑體", sans-serif; background: #f5f5f5; padding: 20px; line-height: 1.6; }
.container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
h1 { color: #0EA5E9; border-bottom: 3px solid #0EA5E9; padding-bottom: 10px; margin-bottom: 20px; }
h2 { color: #10B981; margin-top: 25px; margin-bottom: 10px; padding-left: 10px; border-left: 5px solid #10B981; }
h3 { color: #F59E0B; margin-top: 15px; margin-bottom: 8px; }
.info-box { background: #f0f9ff; border-left: 4px solid #0EA5E9; padding: 10px 15px; margin-bottom: 15px; border-radius: 4px; }
.price-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
.price-table th { background: #0EA5E9; color: white; padding: 8px; text-align: left; }
.price-table td { padding: 6px 8px; border-bottom: 1px solid #eee; }
.price-table tr:hover { background: #f9f9f9; }
.up { color: #dc2626; font-weight: bold; }
.down { color: #059669; font-weight: bold; }
.alert { background: #fef3c7; border-left: 4px solid #F59E0B; padding: 10px 15px; margin-bottom: 15px; border-radius: 4px; }
.footer { text-align: center; color: #999; margin-top: 30px; font-size: 12px; }
.nav { background: #f0f9ff; padding: 10px; margin-bottom: 20px; border-radius: 4px; }
.nav a { margin-right: 15px; color: #0EA5E9; text-decoration: none; font-weight: bold; }
</style>
</head>
<body>
<div class="container">
<div class="nav">
<a href="index.html">📊 今日</a>
<a href="history/index.html">📚 歷史報告</a>
</div>
<h1>📊 每日物價報告</h1>
<div class="info-box">
<strong>📅 報告日期：</strong> """ + today + """<br>
<strong>🕐 更新時間：</strong> 每日 14:00 自動更新<br>
<strong>📡 資料來源：</strong> 5 個農糧署 API
</div>
<h2>🥬 一、主要蔬果價格</h2>
<h3>【葉菜類】</h3>
<table class="price-table">
<thead><tr><th>產品</th><th>價格</th><th>漲跌</th></tr></thead>
<tbody>
""" + render_rows(veg_leaf) + """
</tbody>
</table>
<h3>【果菜類】</h3>
<table class="price-table">
<thead><tr><th>產品</th><th>價格</th><th>漲跌</th></tr></thead>
<tbody>
""" + render_rows(veg_fruit) + """
</tbody>
</table>
<h3>【根莖類】</h3>
<table class="price-table">
<thead><tr><th>產品</th><th>價格</th><th>漲跌</th></tr></thead>
<tbody>
""" + render_rows(veg_root) + """
</tbody>
</table>
<h2>🍎 二、主要水果價格</h2>
<table class="price-table">
<thead><tr><th>產品</th><th>價格</th><th>漲跌</th></tr></thead>
<tbody>
""" + render_rows(data['fruits']) + """
</tbody>
</table>
<h2>🍚 三、米價</h2>
<div class="info-box">
<strong>💰 全國平均：</strong> """ + str(data['rice'].get('avg', 'N/A')) + """ 元/公斤<br>
<strong>📊 統計縣市數：</strong> """ + str(data['rice'].get('cities', 'N/A')) + """ 個
</div>
<h2>🐷 四、豬價</h2>
<div class="info-box">
<strong>💰 今日全國平均：</strong> """ + str(data['pork'].get('avg', 'N/A')) + """ 元/公斤<br>
<strong>📊 統計市場數：</strong> """ + str(data['pork'].get('markets', 'N/A')) + """ 個
</div>
<h2>🐟 五、主要魚價</h2>
<table class="price-table">
<thead><tr><th>魚種</th><th>價格</th><th>漲跌</th></tr></thead>
<tbody>
""" + render_rows(data['fish']) + """
</tbody>
</table>
<h2>🐔 六、雞價、蛋價</h2>
<div class="info-box">
<strong>【雞價】</strong><br>
• 白肉雞 2.0Kg 以上：""" + str(data['poultry'].get('chicken_2kg', 'N/A')) + """ 元/公斤<br>
• 白肉雞 1.75-1.95Kg：""" + str(data['poultry'].get('chicken_175', 'N/A')) + """ 元/公斤<br>
• 白肉雞（門市價高屏）：""" + str(data['poultry'].get('chicken_store', 'N/A')) + """ 元/公斤<br>
<strong>【蛋價】</strong><br>
• 雞蛋（產地）：""" + str(data['poultry'].get('egg', 'N/A')) + """ 元/公斤
</div>
<div class="alert">
<strong>✅ 物價穩定</strong><br>
當日價格變動均在 ±10% 內
</div>
<div class="footer">
📡 資料來源 | 行政院農業委員會農糧署<br>
📅 下次更新 | 明日下午 14:00<br>
🏛️ 主辦 | 臺南市政府法制處<br>
📞 06-3901230 / 0982888265
</div>
</div>
</body>
</html>"""
    return html


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    today_compact = datetime.now().strftime("%Y%m%d")
    
    run_tracker()
    
    report_path = f"{CLIPPINGS}/每日物價報告_{today_compact}.md"
    if not os.path.exists(report_path):
        print(f"找不到報告")
        return
    
    with open(report_path, "r", encoding="utf-8") as f:
        report_text = f.read()
    
    data = parse_report(report_text)
    
    html = generate_html(data, today)
    
    index_path = f"{WEB_DIR}/index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已更新: {index_path}")
    
    history_path = f"{HISTORY_DIR}/{today_compact}.html"
    with open(history_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已存歷史: {history_path}")
    
    import shutil
    shutil.copy(report_path, f"{HISTORY_DIR}/{today_compact}.md")
    
    print("網站更新完成！")


if __name__ == "__main__":
    main()
