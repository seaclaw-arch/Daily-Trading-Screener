import os
import logging
import requests
import pandas as pd
import numpy as np
import yfinance as yf

# ==========================================
# 1. KONFIGURASI & LOGGING
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("🚨 ERROR: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan di GitHub Secrets!")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==========================================
# 2. FUNGSI KIRIM TELEGRAM (DENGAN FALLBACK)
# ==========================================
def send_telegram_alert(message: str):
    """Mengirim notifikasi ke Telegram. Jika Markdown error, otomatis kirim plain text."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Coba kirim dengan Markdown dulu
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        # Jika Telegram menolak karena format Markdown salah
        if not response.ok:
            logger.warning(f"⚠️ Telegram menolak format Markdown. Mencoba ulang tanpa format...")
            logger.warning(f"Detail Error: {response.text}")
            
            # Fallback: Kirim ulang tanpa parse_mode (plain text)
            payload['parse_mode'] = None
            response_retry = requests.post(url, json=payload, timeout=10)
            
            if response_retry.ok:
                logger.info("✅ Pesan berhasil dikirim (mode fallback plain text).")
            else:
                logger.error(f" Gagal total kirim pesan: {response_retry.text}")
        else:
            logger.info("✅ Notifikasi Telegram berhasil dikirim (Markdown).")
            
    except Exception as e:
        logger.error(f"❌ Gagal kirim Telegram (Network Error): {e}")

# ==========================================
# 3. FUNGSI ANALISIS VPA
# ==========================================
def analyze_vpa(ticker: str, df: pd.DataFrame) -> dict:
    """Analisis Volume Price Analysis (VPA) untuk mencari jejak akumulasi."""
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
    
    # 2. Volume Anomaly: Volume > 2x rata-rata 20 hari
    avg_volume_20 = float(prev_rows['Volume'].mean())
    if avg_volume_20 == 0 or volume <= (avg_volume_20 * 2.0):
        return None
    
    # 3. Price Action: Close di 20% teratas dari range harian
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
# 4. FUNGSI UTAMA SCREENER
# ==========================================
def run_screener():
    """Menjalankan screener ke seluruh watchlist."""
    
    # === WATCHLIST SAHAM LIKUID (AMAN) ===
    WATCHLIST_LIQUID = [
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK", "BJBR.JK", "BJTM.JK", 
        "BNGA.JK", "BDMN.JK", "PNBN.JK", "BACA.JK", "BTPN.JK", "MEGA.JK", "NISP.JK",
        "TLKM.JK", "ISAT.JK", "EXCL.JK",
        "ASII.JK", "AUTO.JK", "IMAS.JK", "INDR.JK", "GGRM.JK", "UNTR.JK", "UNVR.JK", 
        "MYOR.JK", "ICBP.JK", "INDF.JK", "JPFA.JK", "AISA.JK",
        "ANTM.JK", "MDKA.JK", "NCKL.JK", "INCO.JK", "TINS.JK", "ADRO.JK", "PTBA.JK", 
        "ITMG.JK", "INDY.JK", "AKR.JK", "BUMI.JK",
        "MEDC.JK", "PGAS.JK", "KRAS.JK",
        "GOTO.JK", "BUKA.JK", "EMTK.JK", "SCMA.JK", "VIVA.JK", "NETV.JK", "DIGI.JK",
        "BSDE.JK", "CTRA.JK", "PWON.JK", "SMRA.JK", "LPKR.JK", "ASRI.JK", "ADHI.JK", 
        "PTPP.JK", "WTON.JK", "JKON.JK",
        "JSMR.JK", "MNCN.JK", "SMGR.JK", "INTP.JK",
        "AMRT.JK", "MIDI.JK", "HERO.JK", "ACES.JK", "KLBF.JK", "PYFA.JK", "CAMP.JK",
        "MIKA.JK", "HEAL.JK", "SILO.JK",
        "CPIN.JK", "TOWR.JK", "TBIG.JK", "BRPT.JK", "TPIA.JK", "FREN.JK", "RAJA.JK", 
        "ASSA.JK", "ROCK.JK"
    ]
    
    # === WATCHLIST SAHAM TIDAK LIKUID (BERISIKO) ===
    WATCHLIST_ILLIQUID = [
        "DSSA.JK", "MORA.JK", "DEWA.JK", "TRIN.JK", "IRSX.JK", "SKBM.JK", "SOTS.JK"
    ]
    
    # === WATCHLIST SAHAM GORENGAN (SERING TRENDING) ===
    WATCHLIST_GORENGAN = [
        "TRUE.JK", "WBSA.JK", "BOLA.JK", "SOCA.JK", "MKPI.JK", "PORT.JK", "NICK.JK", 
        "DOID.JK", "PSAB.JK", "LAND.JK", "RAYA.JK", "TAXI.JK", "KIAS.JK", "POLU.JK", "GLVA.JK"
    ]
    
    # Gabungkan dan hapus duplikat
    WATCHLIST = list(set(WATCHLIST_LIQUID + WATCHLIST_ILLIQUID + WATCHLIST_GORENGAN))
    
    logger.info(f"🚀 Memulai IDX Sniper Screener - Memindai {len(WATCHLIST)} saham...")
    
    signals_found = 0
    illiquid_signals = 0
    gorengan_signals = 0
    
    try:
        logger.info("📥 Mengunduh data historis (batch download)...")
        data = yf.download(WATCHLIST, period="3mo", group_by='ticker', progress=False)
    except Exception as e:
        logger.error(f"❌ Gagal unduh data: {e}")
        send_telegram_alert("🚨 ERROR SISTEM: Gagal mengunduh data pasar.")
        return
    
    for ticker in WATCHLIST:
        try:
            df = data[ticker].dropna() if len(WATCHLIST) > 1 else data.dropna()
            if df.empty:
                continue
            
            result = analyze_vpa(ticker, df)
            
            if result:
                signals_found += 1
                is_gorengan = ticker in WATCHLIST_GORENGAN
                is_illiquid = ticker in WATCHLIST_ILLIQUID
                
                # --- FORMAT PESAN TELEGRAM (SUDAH DIPERBAIKI AGAR VALID) ---
                if is_gorengan:
                    gorengan_signals += 1
                    message = (
                        f"🔥 *SAHAM GORENGAN TRENDING!*\n\n"
                        f"📈 *Saham:* #{result['ticker']}\n"
                        f"💰 *Harga Close:* Rp {result['close']:,.0f}\n"
                        f" *Volume:* {result['vol_ratio']:.1f}x dari rata-rata\n"
                        f"🎯 *Posisi Close:* {result['close_pos']:.0f}% dari range\n\n"
                        f"⚠️ *PERINGATAN KERAS:*\n"
                        f"- Risiko manipulasi SANGAT TINGGI\n"
                        f"- Pump & dump sangat mungkin\n"
                        f"- Bisa disuspensi BEI kapan saja\n"
                        f"- Spread bid-offer sangat lebar\n"
                        f"- Sulit exit posisi\n"
                        f"- Sinyal teknikal sering palsu\n\n"
                        f"🎰 *HANYA untuk trader profesional!*\n"
                        f"⏱️ *Trading cepat (scalping/day trade)*\n"
                        f"🛑 *Stop Loss WAJIB ketat (max 3-5%)*\n"
                        f"💀 *Jangan hold overnight!*\n\n"
                        f"⚡ *Risiko tinggi = Profit/loss ekstrem*"
                    )
                    logger.warning(f"🔥 Sinyal SAHAM GORENGAN: {ticker}")
                    
                elif is_illiquid:
                    illiquid_signals += 1
                    message = (
                        f"🚨 *PERINGATAN: SAHAM TIDAK LIKUID!*\n\n"
                        f"📈 *Saham:* #{result['ticker']}\n"
                        f"💰 *Harga Close:* Rp {result['close']:,.0f}\n"
                        f"🔥 *Volume:* {result['vol_ratio']:.1f}x dari rata-rata\n"
                        f"🎯 *Posisi Close:* {result['close_pos']:.0f}% dari range\n\n"
                        f"⚠️ *RISIKO TINGGI:*\n"
                        f"- Spread bid-offer lebar\n"
                        f"- Risiko manipulasi tinggi\n"
                        f"- Sulit jual saat panic selling\n"
                        f"- Sinyal bisa palsu\n\n"
                        f"🛑 *HANYA untuk trader berpengalaman!*\n"
                        f"🛡️ *Stop Loss WAJIB ketat!*"
                    )
                    logger.warning(f"⚠️ Sinyal saham TIDAK LIKUID: {ticker}")
                    
                else:
                    message = (
                        f"🚨 *SINYAL AKUMULASI INSTITUSI!*\n\n"
                        f"📈 *Saham:* #{result['ticker']}\n"
                        f"💰 *Harga Close:* Rp {result['close']:,.0f}\n"
                        f"📊 *Tren:* Di atas SMA50 (Rp {result['sma_50']:,.0f})\n"
                        f"🔥 *Volume:* {result['vol_ratio']:.1f}x dari rata-rata!\n"
                        f" *Posisi Close:* {result['close_pos']:.0f}% dari range\n\n"
                        f"🧠 *Aksi:* Cek chart manual sebelum entry\n"
                        f"🛡️ *Stop Loss:* Di bawah low hari ini"
                    )
                    logger.info(f"✅ Sinyal ditemukan: {ticker}")
                
                send_telegram_alert(message)
        
        except Exception as e:
            logger.error(f"⚠️ Error proses {ticker}: {e}")
    
    # --- LAPORAN AKHIR ---
    if signals_found == 0:
        logger.info("💤 Tidak ada sinyal VPA hari ini")
        send_telegram_alert(
            f"🔍 *Laporan Harian IDX Sniper*\n\n"
            f"Memindai {len(WATCHLIST)} saham:\n"
            f"- {len(WATCHLIST_LIQUID)} saham likuid ✅\n"
            f"- {len(WATCHLIST_ILLIQUID)} saham tidak likuid ⚠️\n"
            f"- {len(WATCHLIST_GORENGAN)} saham gorengan 🔥\n\n"
            f"Tidak ada sinyal Akumulasi Institusi (VPA) hari ini.\n\n"
            f"📊 Pasar sedang tenang.\n"
            f"💵 Tetap pegang cash atau tunggu setup lain.\n"
            f"🛡️ *Stay safe!*"
        )
    else:
        logger.info(f"🏁 Selesai. Total {signals_found} sinyal ditemukan")
        
        summary_msg = (
            f" *Ringkasan Harian*\n\n"
            f"🎯 Total sinyal: {signals_found}\n"
            f"✅ Saham likuid: {signals_found - illiquid_signals - gorengan_signals}\n"
            f"⚠️ Saham tidak likuid: {illiquid_signals}\n"
            f"🔥 Saham gorengan: {gorengan_signals}\n\n"
            f"Dari {len(WATCHLIST)} saham yang dipindai."
        )
        if gorengan_signals > 0:
            summary_msg += "\n\n🚨 *HATI-HATI dengan saham gorengan!*"
            
        send_telegram_alert(summary_msg)

# ==========================================
# 5. EKSEKUSI
# ==========================================
if __name__ == "__main__":
    run_screener()
