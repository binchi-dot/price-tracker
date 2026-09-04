#!/usr/bin/env python3
"""Import a traditional-market survey workbook into auditable site data.

The source is intentionally read-only.  Entries such as ``3把100`` are kept as
raw text but excluded from the normalized per-catty average.
"""
import argparse
import json
import math
import re
from datetime import date
from pathlib import Path

import pandas as pd


def plain(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def direct_number(value):
    """Return a price only when the cell is a direct numeric value."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 2)
    text = plain(value).replace(",", "")
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/retail_market_history.json"))
    args = parser.parse_args()
    workbook = pd.ExcelFile(args.workbook)
    sheets = [name for name in workbook.sheet_names if re.fullmatch(r"115年[1-8]月份", name)]
    surveys = {}
    for sheet in sheets:
        frame = pd.read_excel(workbook, sheet_name=sheet, header=None)
        markets = []
        for col in range(2, 16, 2):
            name = plain(frame.iat[2, col]).replace("公有市場", "市場")
            if name:
                markets.append({"name": name, "price_col": col, "supply_col": col + 1})
        items, category = [], ""
        for row in range(5, len(frame)):
            value = plain(frame.iat[row, 0])
            if value:
                category = value
            name = plain(frame.iat[row, 1])
            if not name:
                continue
            observations = []
            for market in markets:
                raw = plain(frame.iat[row, market["price_col"]])
                supply = plain(frame.iat[row, market["supply_col"]])
                observations.append({"market": market["name"], "raw_price": raw, "normalized_price": direct_number(frame.iat[row, market["price_col"]]), "supply": supply})
            numeric = [o["normalized_price"] for o in observations if o["normalized_price"] is not None]
            items.append({"category": category, "name": name, "unit": "台斤" if "台斤" in name or name.endswith("1斤") else "原表計價單位", "retail_average": round(sum(numeric) / len(numeric), 2) if numeric else None, "direct_quote_count": len(numeric), "observations": observations})
        month = re.search(r"115年(\d+)月份", sheet).group(1).zfill(2)
        surveys[f"2026-{month}"] = {"source_sheet": sheet, "markets": [m["name"] for m in markets], "items": items}
    payload = {
        "title": "傳統市場訪查表",
        "survey_months": sorted(surveys),
        "imported_on": date.today().isoformat(),
        "supply_legend": {"1": "正常", "2": "少量", "3": "缺貨"},
        "surveys": surveys,
        "method_note": "原表非純數字報價（例如 3把100、1支135）完整保留，但不納入每台斤／每斤的平均與跨市場比價。",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(surveys)} monthly surveys to {args.out}")


if __name__ == "__main__":
    main()
