import os
import logging
import requests
import pandas as pd
import numpy as np
import yfinance as yf

# ==========================================
# KONFIGURASI - Baca dari GitHub Secrets
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Validasi
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("🚨 ERROR: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan di GitHub Secrets!")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==========================================
# FUNGSI KIRIM TELEGRAM
# ==========================================
def send_telegram_alert(message: str):
    """Mengirim notifikasi ke Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("✅ Notifikasi Telegram berhasil dikirim")
    except Exception as e:
        logger.error(f"❌ Gagal kirim Telegram: {e}")

# ==========================================
# FUNGSI ANALISIS VPA
# ==========================================
def analyze_vpa(ticker: str, df: pd.DataFrame) -> dict:
    """
    Analisis Volume Price Analysis (VPA)
    Mencari akumulasi institusi
    """
    if len(df) < 50:
        return None
    
    last_row = df.iloc[-1]
    prev_rows = df.iloc[-21:-1]
    
    close = float(last_row['Close'])
    high = float(last_row['High'])
    low = float(last_row['Low'])
    volume = float(last_row['Volume'])
    
    # 1. Trend Filter: Close > SMA 50
    sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
    if close <= sma_50:
        return None
    
    # 2. Volume Anomaly: Volume > 2x rata-rata
    avg_volume_20 = float(prev_rows['Volume'].mean())
    if avg_volume_20 == 0 or volume <= (avg_volume_20 * 2.0):
        return None
    
    # 3. Price Action: Close di 20% teratas
    price_range = high - low
    if price_range == 0:
        return None
    
    close_position = (close - low) / price_range
    if close_position < 0.80:
        return None
    
    return {
        "ticker": ticker.replace(".JK", ""),
        "close": close,
        "sma_50": sma_50,
        "vol_ratio": volume / avg_volume_20,
        "close_pos": close_position * 100
    }

# ==========================================
# FUNGSI UTAMA SCREENER
# ==========================================
def run_screener():
    """Menjalankan screener ke seluruh watchlist."""
    WATCHLIST = [
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK",
        "TLKM.JK", "ISAT.JK", "EXCL.JK",
        "ASII.JK", "AUTO.JK",
        "ANTM.JK", "MDKA.JK", "NCKL.JK",
        "GOTO.JK", "BUKA.JK", "EMTK.JK",
        "ICBP.JK", "INDF.JK", "MYOR.JK"
    ]
    
    logger.info(f"🚀 Memulai IDX Sniper Screener - Memindai {len(WATCHLIST)} saham...")
    signals_found = 0
    
    try:
        logger.info("📥 Mengunduh data historis...")
        data = yf.download(WATCHLIST, period="3mo", group_by='ticker', progress=False)
    except Exception as e:
        logger.error(f"❌ Gagal unduh data: {e}")
        send_telegram_alert("🚨 *ERROR SISTEM:* Gagal mengunduh data pasar.")
        return
    
    for ticker in WATCHLIST:
        try:
            df = data[ticker].dropna() if len(WATCHLIST) > 1 else data.dropna()
            if df.empty:
                continue
            
            result = analyze_vpa(ticker, df)
            
            if result:
                signals_found += 1
                message = (
                    f"🚨 *SINYAL AKUMULASI INSTITUSI!*\n\n"
                    f"📈 *Saham:* #{result['ticker']}\n"
                    f"💰 *Harga Close:* Rp {result['close']:,.0f}\n"
                    f"📊 *Tren:* Di atas SMA50 (Rp {result['sma_50']:,.0f})\n"
                    f"🔥 *Volume:* {result['vol_ratio']:.1f}x dari rata-rata!\n"
                    f"🎯 *Posisi Close:* {result['close_pos']:.0f}% dari range\n\n"
                    f"🧠 *Aksi:* Cek chart manual sebelum entry\n"
                    f"🛡️ *Stop Loss:* Di bawah low hari ini"
                )
                send_telegram_alert(message)
                logger.info(f"✅ Sinyal ditemukan: {ticker}")
        
        except Exception as e:
            logger.error(f"⚠️ Error proses {ticker}: {e}")
    
    if signals_found == 0:
        logger.info("💤 Tidak ada sinyal VPA hari ini")
        send_telegram_alert(
            "🔍 *Laporan Harian IDX Sniper*\n\n"
            "Tidak ada sinyal Akumulasi Institusi (VPA) yang terdeteksi hari ini.\n\n"
            "📊 Pasar sedang tenang.\n"
            "💵 Tetap pegang cash atau tunggu setup lain.\n"
            "🛡️ *Stay safe!*"
        )
    else:
        logger.info(f"🏁 Selesai. Total {signals_found} sinyal ditemukan")

# ==========================================
# EKSEKUSI
# ==========================================
if __name__ == "__main__":
    run_screener()