# Stock alert bot - auto run via GitHub Actions
import os
import requests

STOCKS = [
    ("FPT",  65000,   68000),
    ("HPG",  22000,   23000),
    ("BSR",  25000,   26000),
    ("MSN",  68000,   75000),
]

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def get_data(symbol):
    ticker = f"{symbol}.VN"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=6d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        d = r.json()
        result = d["chart"]["result"][0]
        meta = result["meta"]
        volumes = result["indicators"]["quote"][0]["volume"]

        price = float(meta["regularMarketPrice"])
        prev_close = float(meta.get("chartPreviousClose", price))
        change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0

        # Lấy KL hôm nay trực tiếp từ meta (chính xác hơn)
        volume_today = int(meta.get("regularMarketVolume", 0))

        # Tính avg từ các ngày trước (bỏ ngày hôm nay ra)
        past_vols = [v for v in volumes[:-1] if v and v > 0]
        avg_volume = int(sum(past_vols) / len(past_vols)) if past_vols else 0

        return {
            "price": price,
            "change_pct": change_pct,
            "volume_today": volume_today,
            "avg_volume": avg_volume
        }
    except Exception as e:
        print(f"Loi {symbol}: {e}")
    return None

def vol_info(volume_today, avg_volume):
    if avg_volume == 0:
        return "KL: ?"
    ratio = volume_today / avg_volume
    vol_str = f"{volume_today:,}".replace(",", ".")
    if ratio >= 2.0:
        return f"🔥 KL {vol_str} ({ratio:.1f}x) — DOT BIEN"
    elif ratio >= 1.5:
        return f"⚡ KL {vol_str} ({ratio:.1f}x) — cao"
    elif ratio <= 0.5:
        return f"KL {vol_str} ({ratio:.1f}x) — thap"
    else:
        return f"📊 KL {vol_str} ({ratio:.1f}x)"

def action_info(change_pct, volume_today, avg_volume):
    ratio = volume_today / avg_volume if avg_volume > 0 else 1
    if change_pct <= -2 and ratio >= 1.5:
        return "🔴 BAN THAO manh"
    elif change_pct >= 2 and ratio >= 1.5:
        return "🚀 DAY GIA / GOM manh"
    elif change_pct >= 0.5 and ratio >= 1.2:
        return "🟡 GOM nhe"
    elif change_pct <= -0.5 and ratio >= 1.2:
        return "🟠 XA hang"
    else:
        return "➡️ Binh thuong"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
    print(f"Telegram: {r.status_code}")

def fmt(n):
    return f"{int(n):,}".replace(",", ".")

def main():
    lines = []
    alert_count = 0
    warn_count = 0

    for symbol, target_low, target_high in STOCKS:
        data = get_data(symbol)
        if data is None:
            lines.append(f"❓ <b>{symbol}</b>: khong lay duoc gia")
            continue

        price = data["price"]
        change_pct = data["change_pct"]
        volume_today = data["volume_today"]
        avg_volume = data["avg_volume"]
        change_str = f"{change_pct:+.1f}%"
        dist_pct = ((price - target_low) / target_low) * 100
        vol_line = vol_info(volume_today, avg_volume)
        act_line = action_info(change_pct, volume_today, avg_volume)

        if price <= target_low:
            alert_count += 1
            lines.append(
                f"✅ <b>{symbol}  ◀ VAO VUNG MUA!</b>\n"
                f"   <b>{fmt(price)} đ</b>  {change_str}\n"
                f"   Mua: {fmt(target_low)} đ  |  Toi: {fmt(target_high)} đ\n"
                f"   {vol_line}\n"
                f"   {act_line}"
            )
        elif dist_pct <= 5:
            warn_count += 1
            lines.append(
                f"⚠️ <b>{symbol}  ◀ SAP CHAM!</b>  (con {dist_pct:.1f}%)\n"
                f"   <b>{fmt(price)} đ</b>  {change_str}\n"
                f"   Vung mua: {fmt(target_low)} đ\n"
                f"   {vol_line}\n"
                f"   {act_line}"
            )
        else:
            lines.append(
                f"🗞️ <b>{symbol}</b>  {fmt(price)} đ  ({change_str})\n"
                f"   Vung mua: {fmt(target_low)} đ  (con {dist_pct:.1f}%)\n"
                f"   {vol_line}  |  {act_line}"
            )

    if alert_count > 0 and warn_count > 0:
        h_icon = "✅" * alert_count + "⚠️" * warn_count
        h_status = f"<b>{alert_count} MA VAO VUNG MUA  +  {warn_count} MA SAP TOI</b>"
    elif alert_count > 0:
        h_icon = "✅" * alert_count
        h_status = f"<b>{alert_count} MA DA VAO VUNG MUA!</b>"
    elif warn_count > 0:
        h_icon = "⚠️" * warn_count
        h_status = f"<b>{warn_count} MA SAP CHAM NGUONG!</b>"
    else:
        h_icon = "📈"
        h_status = "Tat ca binh thuong"

    header = (
        f"📊 BAO CAO CO PHIEU  {h_icon}\n"
        f"▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
        f"{h_status}\n"
        f"▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n\n"
    )

    send_telegram(header + "\n\n".join(lines))
    print("Xong!")

if __name__ == "__main__":
    main()
