# Stock alert bot - auto run via GitHub Actions
import os
import requests
from datetime import datetime

STOCKS_RAW = os.environ.get("STOCKS", "FPT:65000:68000,HPG:22000:23000,BSR:25000:26000,MSN:68000:75000")
STOCKS = []
for item in STOCKS_RAW.split(","):
    parts = item.strip().split(":")
    if len(parts) == 3:
        STOCKS.append((parts[0].strip().upper(), int(parts[1].strip()), int(parts[2].strip())))

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def get_yahoo(ticker_symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}?interval=1d&range=60d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        d = r.json()
        result = d["chart"]["result"][0]
        meta = result["meta"]
        volumes = result["indicators"]["quote"][0]["volume"]
        closes = result["indicators"]["quote"][0]["close"]
        return meta, volumes, closes
    except Exception as e:
        print(f"Loi {ticker_symbol}: {e}")
    return None, None, None

def calc_vol_stats(volumes):
    valid = [v for v in volumes if v and v > 0]
    if len(valid) < 2:
        return 0, 0, 0
    vol_today   = int(valid[-1])
    avg_week    = int(sum(valid[-6:-1]) / len(valid[-6:-1])) if len(valid) >= 6 else int(sum(valid[:-1]) / max(len(valid)-1, 1))
    avg_month   = int(sum(valid[-21:-1]) / len(valid[-21:-1])) if len(valid) >= 21 else int(sum(valid[:-1]) / max(len(valid)-1, 1))
    return vol_today, avg_week, avg_month

def vol_label(vol_today, avg_ref):
    if avg_ref == 0:
        return "?"
    ratio = vol_today / avg_ref
    if ratio >= 2.0:
        return f"{ratio:.1f}x 🔥 ĐỘT BIẾN"
    elif ratio >= 1.5:
        return f"{ratio:.1f}x ⚡ cao"
    elif ratio <= 0.5:
        return f"{ratio:.1f}x thấp"
    else:
        return f"{ratio:.1f}x bình thường"

def action_label(change_pct, vol_today, avg_week):
    ratio = vol_today / avg_week if avg_week > 0 else 1
    if change_pct <= -2 and ratio >= 1.5:
        return "🔴 Bán tháo mạnh"
    elif change_pct >= 2 and ratio >= 1.5:
        return "🚀 Đẩy giá / Gom mạnh"
    elif change_pct >= 0.5 and ratio >= 1.2:
        return "🟡 Gom nhẹ"
    elif change_pct <= -0.5 and ratio >= 1.2:
        return "🟠 Xả hàng"
    elif change_pct <= -0.5 and ratio < 0.8:
        return "😴 Giảm thiếu lực — chưa rõ tín hiệu"
    else:
        return "➡️ Bình thường"

def market_conclusion(change_pct, vol_today, avg_week, avg_month):
    ratio_w = vol_today / avg_week if avg_week > 0 else 1
    ratio_m = vol_today / avg_month if avg_month > 0 else 1
    if change_pct >= 1 and ratio_w >= 1.5:
        return "📈 Thị trường tăng mạnh — dòng tiền vào tốt, xu hướng tích cực."
    elif change_pct >= 0.3:
        return "📈 Thị trường tăng nhẹ — tâm lý thận trọng, dòng tiền chưa mạnh."
    elif change_pct <= -1 and ratio_w >= 1.5:
        return "📉 Thị trường giảm mạnh — KL lớn, có dấu hiệu bán tháo, cẩn thận."
    elif change_pct <= -0.5:
        return "📉 Thị trường điều chỉnh — giảm nhẹ, KL trung bình, chưa đáng lo."
    else:
        return "➡️ Thị trường đi ngang — chưa có xu hướng rõ ràng, chờ tín hiệu."

def fmt(n):
    return f"{int(n):,}".replace(",", ".")

def fmt_m(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f} triệu"
    elif n >= 1_000:
        return f"{n/1_000:.0f} nghìn"
    return str(n)

def get_weekday_vn():
    days = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    now = datetime.utcnow()
    return days[now.weekday()], now.strftime("%d/%m/%Y")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
    print(f"Telegram: {r.status_code}")

def main():
    weekday, date_str = get_weekday_vn()

    # ── VNINDEX ──────────────────────────────────────────
    meta_vn, vols_vn, closes_vn = get_yahoo("^VNINDEX")
    vnindex_block = ""
    if meta_vn:
        price_vn    = float(meta_vn["regularMarketPrice"])
        prev_vn     = float(meta_vn.get("chartPreviousClose", price_vn))
        chg_vn      = ((price_vn - prev_vn) / prev_vn) * 100 if prev_vn else 0
        chg_str_vn  = f"{chg_vn:+.2f}%"
        vol_vn, avg_w_vn, avg_m_vn = calc_vol_stats(vols_vn)

        ratio_w_vn = vol_vn / avg_w_vn if avg_w_vn > 0 else 1
        ratio_m_vn = vol_vn / avg_m_vn if avg_m_vn > 0 else 1
        mkt_note   = market_conclusion(chg_vn, vol_vn, avg_w_vn, avg_m_vn)

        vnindex_block = (
            f"🇻🇳 <b>VNINDEX</b>  {price_vn:,.2f}  ({chg_str_vn})\n"
            f"   KL hôm nay : {fmt_m(vol_vn)}\n"
            f"   So TB tuần : {vol_label(vol_vn, avg_w_vn)}  |  So TB tháng : {vol_label(vol_vn, avg_m_vn)}\n"
            f"   {mkt_note}"
        )
    else:
        vnindex_block = "🇻🇳 <b>VNINDEX</b>: không lấy được dữ liệu"

    # ── CÁC MÃ ──────────────────────────────────────────
    lines = []
    alert_count = 0
    warn_count = 0

    for symbol, target_low, target_high in STOCKS:
        meta, volumes, closes = get_yahoo(f"{symbol}.VN")
        if meta is None:
            lines.append(f"❓ <b>{symbol}</b>: không lấy được giá")
            continue

        price      = float(meta["regularMarketPrice"])
        prev_close = float(meta.get("chartPreviousClose", price))
        change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
        change_str = f"{change_pct:+.1f}%"
        dist_pct   = ((price - target_low) / target_low) * 100

        vol_today, avg_week, avg_month = calc_vol_stats(volumes)
        act_line = action_label(change_pct, vol_today, avg_week)

        vol_line = (
            f"KL: {fmt(vol_today)}\n"
            f"   So TB tuần  : {vol_label(vol_today, avg_week)}\n"
            f"   So TB tháng : {vol_label(vol_today, avg_month)}"
        )

        if price <= target_low:
            alert_count += 1
            lines.append(
                f"✅ <b>{symbol}  ◀ VÀO VÙNG MUA!</b>\n"
                f"   <b>{fmt(price)} đ</b>  {change_str}\n"
                f"   Mua: {fmt(target_low)} đ  |  Tới: {fmt(target_high)} đ\n"
                f"   {vol_line}\n"
                f"   {act_line}"
            )
        elif dist_pct <= 5:
            warn_count += 1
            lines.append(
                f"⚠️ <b>{symbol}  ◀ SẮP CHẠM!</b>  (còn {dist_pct:.1f}%)\n"
                f"   <b>{fmt(price)} đ</b>  {change_str}\n"
                f"   Vùng mua: {fmt(target_low)} đ\n"
                f"   {vol_line}\n"
                f"   {act_line}"
            )
        else:
            lines.append(
                f"🗞️ <b>{symbol}</b>  {fmt(price)} đ  ({change_str})\n"
                f"   Vùng mua: {fmt(target_low)} đ  (còn {dist_pct:.1f}%)\n"
                f"   {vol_line}\n"
                f"   {act_line}"
            )

    # ── HEADER ──────────────────────────────────────────
    if alert_count > 0 and warn_count > 0:
        h_icon   = "✅" * alert_count + "⚠️" * warn_count
        h_status = f"<b>{alert_count} MÃ VÀO VÙNG MUA  +  {warn_count} MÃ SẮP TỚI</b>"
    elif alert_count > 0:
        h_icon   = "✅" * alert_count
        h_status = f"<b>{alert_count} MÃ ĐÃ VÀO VÙNG MUA!</b>"
    elif warn_count > 0:
        h_icon   = "⚠️" * warn_count
        h_status = f"<b>{warn_count} MÃ SẮP CHẠM NGƯỠNG!</b>"
    else:
        h_icon   = "📈"
        h_status = "Tất cả bình thường"

    header = (
        f"📊 <b>BÁO CÁO CỔ PHIẾU</b>  {h_icon}\n"
        f"{weekday}, {date_str}\n"
        f"▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
        f"{h_status}\n"
        f"▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n\n"
    )

    # ── KẾT LUẬN TỔNG ──────────────────────────────────
    if alert_count > 0:
        ket_luan = f"Có {alert_count} mã vào vùng mua — xem xét giải ngân nếu thị trường xác nhận."
    elif warn_count > 0:
        ket_luan = f"Có {warn_count} mã sắp chạm vùng mua — theo dõi sát, chuẩn bị sẵn sàng."
    else:
        ket_luan = "Chưa có mã nào vào vùng mua — tiếp tục quan sát, không cần hành động vội."

    footer = (
        f"\n▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
        f"📝 <b>Kết luận:</b> {ket_luan}"
    )

    message = (
        header
        + vnindex_block
        + "\n\n"
        + "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n\n"
        + "\n\n".join(lines)
        + footer
    )

    send_telegram(message)
    print("Xong!")

if __name__ == "__main__":
    main()
