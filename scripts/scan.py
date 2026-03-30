import requests
import json
import os
from datetime import datetime

# ── 設定 ──────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

WATCHLIST = [
    "0700.HK","0005.HK","0941.HK","1299.HK","0388.HK",
    "2318.HK","0003.HK","0016.HK","0011.HK","1109.HK",
    "0002.HK","0001.HK","0027.HK","0066.HK","0101.HK",
    "0175.HK","0267.HK","0288.HK","0291.HK","0386.HK",
    "0688.HK","0762.HK","0823.HK","0857.HK","0883.HK",
    "0960.HK","1038.HK","1044.HK","1088.HK","1093.HK",
    "1177.HK","1211.HK","1398.HK","1810.HK","1876.HK",
    "1928.HK","2020.HK","2269.HK","2313.HK","2382.HK",
    "2388.HK","2628.HK","3328.HK","3690.HK","3988.HK",
    "6098.HK","6862.HK","9618.HK","9888.HK","9999.HK"
]

# ── 抓股票數據 ────────────────────────────────────
def get_stock_data(symbol):
    try:
        ticker = symbol.replace(".HK", "")
        ticker_padded = ticker.zfill(4)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_padded}.HK?interval=1d&range=1y"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) < 20:
            return None
        price = closes[-1]
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else None
        ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
        prev = closes[-2] if len(closes) >= 2 else price
        change_pct = (price - prev) / prev * 100
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2) if ma60 else None,
            "ma200": round(ma200, 2) if ma200 else None,
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

# ── 判斷市況 ──────────────────────────────────────
def get_market_status(hsi_data):
    if not hsi_data or not hsi_data.get("ma200"):
        return "UNKNOWN"
    return "BULL" if hsi_data["price"] > hsi_data["ma200"] else "BEAR"

# ── 評分邏輯 ──────────────────────────────────────
def score_stock(s, market):
    if not s:
        return 0
    score = 0
    if s["price"] > s["ma20"]:
        score += 2
    if s.get("ma60") and s["price"] > s["ma60"]:
        score += 2
    if s.get("ma200") and s["price"] > s["ma200"]:
        score += 3
    if market == "BULL":
        score += 1
    if s["change_pct"] > 2:
        score += 2
    elif s["change_pct"] > 0:
        score += 1
    return score

# ── Telegram 通知 ─────────────────────────────────
def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured, skipping.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})

# ── 主程式 ────────────────────────────────────────
def main():
    print("Starting HK Quant Scan...")
    hsi = get_stock_data("^HSI")
    market = get_market_status(hsi)
    print(f"Market: {market}, HSI: {hsi['price'] if hsi else 'N/A'}")

    signals = []
    for sym in WATCHLIST:
        s = get_stock_data(sym)
        if not s:
            continue
        score = score_stock(s, market)
        if score >= 6:
            signals.append({
                "symbol": s["symbol"],
                "price": s["price"],
                "change_pct": s["change_pct"],
                "ma20": s["ma20"],
                "ma60": s["ma60"],
                "ma200": s["ma200"],
                "score": score,
                "signal": "BUY" if score >= 7 else "WATCH"
            })
        print(f"{sym}: score={score}")

    signals.sort(key=lambda x: x["score"], reverse=True)

    result = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "market_status": market,
        "hsi_price": hsi["price"] if hsi else 0,
        "hsi_ma200": hsi["ma200"] if hsi and hsi.get("ma200") else 0,
        "signals": signals,
        "total": len(signals)
    }

    os.makedirs("data", exist_ok=True)
    with open("data/results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Done. {len(signals)} signals found.")

    if signals:
        top = signals[:5]
        msg = f"🇭🇰 <b>港股掃描結果</b>\n市況：{'🐂 牛市' if market=='BULL' else '🐻 熊市'}\n\n"
        for s in top:
            emoji = "🟢" if s["signal"] == "BUY" else "🟡"
            msg += f"{emoji} <b>{s['symbol']}</b> HK${s['price']} ({s['change_pct']:+.1f}%) 評分:{s['score']}\n"
        send_telegram(msg)

if __name__ == "__main__":
    main()
