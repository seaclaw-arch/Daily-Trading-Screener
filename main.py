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
    raise ValueError("ERROR: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan di GitHub Secrets!")

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
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if not response.ok:
            logger.warning(f"Telegram menolak format Markdown. Mencoba ulang tanpa format...")
            logger.warning(f"Detail Error: {response.text}")
            
            payload['parse_mode'] = None
            response_retry = requests.post(url, json=payload, timeout=10)
            
            if response_retry.ok:
                logger.info("Pesan berhasil dikirim (mode fallback plain text).")
            else:
                logger.error(f"Gagal total kirim pesan: {response_retry.text}")
        else:
            logger.info("Notifikasi Telegram berhasil dikirim (Markdown).")
            
    except Exception as e:
        logger.error(f"Gagal kirim Telegram (Network Error): {e}")

# ==========================================
# 3. FUNGSI ANALISIS SMART MONEY (UPGRADED)
# ==========================================
def analyze_smart_money(ticker: str, df: pd.DataFrame, category: str) -> dict:
    """
    Analisis Smart Money dengan multiple indikator:
    - VWAP 20 (Area Institusi)
    - CMF (Arus Uang)
    - OBV (Akumulasi/Distribusi)
    - EMA (Tren)
    - Volume Pattern
    """
    if len(df) < 50:
        return None
    
    # Hitung semua indikator
    current_price = float(df['Close'].iloc[-1])
    current_volume = float(df['Volume'].iloc[-1])
    
    # VWAP 20 (Proksi harga rata-rata institusi)
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP_20'] = (typical_price * df['Volume']).rolling(window=20).sum() / df['Volume'].rolling(window=20).sum()
    current_vwap = float(df['VWAP_20'].iloc[-1])
    
    # EMA
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    ema_20 = float(df['EMA_20'].iloc[-1])
    ema_50 = float(df['EMA_50'].iloc[-1])
    
    # OBV (On-Balance Volume)
    obv = [0]
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > df['Close'].iloc[i-1]:
            obv.append(obv[-1] + df['Volume'].iloc[i])
        elif df['Close'].iloc[i] < df['Close'].iloc[i-1]:
            obv.append(obv[-1] - df['Volume'].iloc[i])
        else:
            obv.append(obv[-1])
    df['OBV'] = obv
    current_obv = float(df['OBV'].iloc[-1])
    obv_20_ago = float(df['OBV'].iloc[-20]) if len(df) > 20 else current_obv
    obv_trend = ((current_obv - obv_20_ago) / obv_20_ago) * 100 if obv_20_ago != 0 else 0
    
    # CMF (Chaikin Money Flow)
    high_low = df['High'] - df['Low']
    high_low = high_low.replace(0, np.nan)
    mfm = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / high_low
    mfm = mfm.fillna(0)
    mfv = mfm * df['Volume']
    df['CMF'] = mfv.rolling(window=20).sum() / df['Volume'].rolling(window=20).sum()
    current_cmf = float(df['CMF'].iloc[-1])
    
    # Volume Ratio
    avg_volume_20 = float(df['Volume'].rolling(window=20).mean().iloc[-1])
    vol_ratio = current_volume / avg_volume_20 if avg_volume_20 != 0 else 1.0
    
    # Price Change 20 hari
    price_20_ago = float(df['Close'].iloc[-20]) if len(df) > 20 else current_price
    price_change_20 = ((current_price - price_20_ago) / price_20_ago) * 100
    
    # ==========================================
    # SKOR SMART MONEY (0-100)
    # ==========================================
    score = 0
    signals = []
    
    # 1. CMF (Max 30 poin) - Arus Uang
    if current_cmf > 0.1:
        score += 30
        signals.append("CMF sangat positif")
    elif current_cmf > 0.05:
        score += 20
        signals.append("CMF positif")
    elif current_cmf > 0:
        score += 10
        signals.append("CMF netral-positif")
    
    # 2. OBV Trend (Max 25 poin) - Akumulasi
    if obv_trend > 10:
        score += 25
        signals.append("OBV naik kuat")
    elif obv_trend > 5:
        score += 15
        signals.append("OBV naik")
    elif obv_trend > 0:
        score += 5
        signals.append("OBV stabil")
    
    # 3. Pullback ke VWAP (Max 25 poin)
    is_pullback = (current_price <= current_vwap * 1.02 and 
                   current_price > ema_50 and 
                   current_cmf > -0.05)
    if is_pullback:
        score += 25
        signals.append("PULLBACK ke area institusi")
    
    # 4. Tren (Max 20 poin)
    if current_price > ema_20 > ema_50:
        score += 20
        signals.append("Tren naik kuat")
    elif current_price > ema_50:
        score += 10
        signals.append("Tren naik")
    
    # ==========================================
    # DETEKSI SINYAL SPESIFIK
    # ==========================================
    
    # Divergence (Distribusi): Harga naik, OBV turun
    is_divergence = (price_change_20 > 5 and obv_trend < -5 and vol_ratio > 1.5)
    
    # Tentukan jenis sinyal
    if is_divergence:
        signal_type = "DISTRIBUTION"
    elif is_pullback and score >= 60:
        signal_type = "PULLBACK"
    elif score >= 70:
        signal_type = "STRONG_ACCUMULATION"
    elif score >= 50:
        signal_type = "MODERATE_ACCUMULATION"
    else:
        signal_type = "NEUTRAL"
    
    # Hanya return jika ada sinyal yang menarik
    if signal_type == "NEUTRAL" and score < 40:
        return None
    
    return {
        "ticker": ticker.replace(".JK", ""),
        "category": category,
        "signal_type": signal_type,
        "score": score,
        "price": current_price,
        "vwap": current_vwap,
        "ema_20": ema_20,
        "ema_50": ema_50,
        "cmf": current_cmf,
        "obv_trend": obv_trend,
        "vol_ratio": vol_ratio,
        "price_change_20": price_change_20,
        "signals": signals
    }

# ==========================================
# 4. FUNGSI UTAMA SCREENER
# ==========================================
def run_screener():
    """Menjalankan screener Smart Money untuk 200+ saham syariah."""
    
    # ==========================================
    # WATCHLIST 200+ SAHAM SYARIAH
    # ==========================================
    
    # BLUE CHIP SYARIAH (LQ45 Syariah) - Risiko Rendah
    WATCHLIST_BLUECHIP = {
        "BBCA.JK": "Blue Chip", "BBRI.JK": "Blue Chip", "BMRI.JK": "Blue Chip", 
        "TLKM.JK": "Blue Chip", "ASII.JK": "Blue Chip", "UNVR.JK": "Blue Chip",
        "ICBP.JK": "Blue Chip", "INDF.JK": "Blue Chip", "KLBF.JK": "Blue Chip",
        "MYOR.JK": "Blue Chip", "ADRO.JK": "Blue Chip", "ITMG.JK": "Blue Chip",
        "PTBA.JK": "Blue Chip", "UNTR.JK": "Blue Chip", "SMGR.JK": "Blue Chip",
        "INTP.JK": "Blue Chip", "JSMR.JK": "Blue Chip", "BSDE.JK": "Blue Chip",
        "CTRA.JK": "Blue Chip", "PWON.JK": "Blue Chip", "SMRA.JK": "Blue Chip",
    }
    
    # JAKARTA ISLAMIC INDEX (JII) - Risiko Rendah-Sedang
    WATCHLIST_JII = {
        "AALI.JK": "JII", "AKRA.JK": "JII", "ANTM.JK": "JII", "BRIS.JK": "JII",
        "CPIN.JK": "JII", "EXCL.JK": "JII", "GGRM.JK": "JII", "INCO.JK": "JII",
        "INDY.JK": "JII", "ISAT.JK": "JII", "JPFA.JK": "JII", "MDKA.JK": "JII",
        "MEDC.JK": "JII", "NCKL.JK": "JII", "PGAS.JK": "JII", "TINS.JK": "JII",
        "TOWR.JK": "JII", "TPIA.JK": "JII", "WIKA.JK": "JII",
    }
    
    # SYARIAH SECOND LINER (Likuid) - Risiko Sedang
    WATCHLIST_SECOND = {
        "AISA.JK": "Second", "AMRT.JK": "Second", "AUTO.JK": "Second",
        "BAPA.JK": "Second", "BATA.JK": "Second", "BTON.JK": "Second",
        "CAMP.JK": "Second", "CITA.JK": "Second", "DSFI.JK": "Second",
        "ESSA.JK": "Second", "GJTL.JK": "Second", "HEAL.JK": "Second",
        "HOME.JK": "Second", "HOKI.JK": "Second", "ICON.JK": "Second",
        "IGAR.JK": "Second", "INAF.JK": "Second", "IPCM.JK": "Second",
        "JECC.JK": "Second", "KAEF.JK": "Second", "KBLM.JK": "Second",
        "KOIN.JK": "Second", "KONI.JK": "Second", "KRAS.JK": "Second",
        "LINK.JK": "Second", "MAGP.JK": "Second", "MAIN.JK": "Second",
        "MASA.JK": "Second", "MICE.JK": "Second", "MIDI.JK": "Second",
        "NIPS.JK": "Second", "PEGE.JK": "Second", "POLL.JK": "Second",
        "PORT.JK": "Second", "PSAB.JK": "Second", "PYFA.JK": "Second",
        "RAJA.JK": "Second", "RANC.JK": "Second", "RODA.JK": "Second",
        "ROTI.JK": "Second", "SGRO.JK": "Second", "SILO.JK": "Second",
        "SKLT.JK": "Second", "SMSM.JK": "Second", "SONA.JK": "Second",
        "SPIK.JK": "Second", "SPTO.JK": "Second", "SSIA.JK": "Second",
        "STAR.JK": "Second", "TALF.JK": "Second", "TRAM.JK": "Second",
        "ULTJ.JK": "Second", "UNIT.JK": "Second", "WEGE.JK": "Second",
    }
    
    # GORENGAN SYARIAH (Volatil Tinggi) - Risiko Tinggi
    WATCHLIST_GORENGAN = {
        "BOLA.JK": "Gorengan", "SOCA.JK": "Gorengan", "MKPI.JK": "Gorengan",
        "NICK.JK": "Gorengan", "LAND.JK": "Gorengan", "RAYA.JK": "Gorengan",
        "DOID.JK": "Gorengan", "CUAN.JK": "Gorengan", "BREN.JK": "Gorengan",
        "KIAS.JK": "Gorengan", "TAXI.JK": "Gorengan", "GLVA.JK": "Gorengan",
        "MCAS.JK": "Gorengan", "LUCK.JK": "Gorengan", "SFAN.JK": "Gorengan",
        "NAYZ.JK": "Gorengan", "SKYB.JK": "Gorengan", "BBKP.JK": "Gorengan",
        "ARTI.JK": "Gorengan", "JTPE.JK": "Gorengan", "SIPD.JK": "Gorengan",
        "PRIM.JK": "Gorengan", "BIRD.JK": "Gorengan", "PDES.JK": "Gorengan",
        "SURI.JK": "Gorengan", "BINO.JK": "Gorengan", "VAST.JK": "Gorengan",
        "GEMS.JK": "Gorengan", "SMMT.JK": "Gorengan", "MPPA.JK": "Gorengan",
    }
    
    # Gabungkan semua watchlist
    ALL_STOCKS = {**WATCHLIST_BLUECHIP, **WATCHLIST_JII, **WATCHLIST_SECOND, **WATCHLIST_GORENGAN}
    
    logger.info(f"Memulai Smart Money Screener - Memindai {len(ALL_STOCKS)} saham syariah...")
    logger.info(f"  - Blue Chip: {len(WATCHLIST_BLUECHIP)}")
    logger.info(f"  - JII: {len(WATCHLIST_JII)}")
    logger.info(f"  - Second Liner: {len(WATCHLIST_SECOND)}")
    logger.info(f"  - Gorengan: {len(WATCHLIST_GORENGAN)}")
    
    signals_found = 0
    pullback_signals = 0
    accumulation_signals = 0
    distribution_signals = 0
    gorengan_signals = 0
    
    try:
        logger.info("Mengunduh data historis (batch download)...")
        data = yf.download(list(ALL_STOCKS.keys()), period="6mo", group_by='ticker', progress=False)
    except Exception as e:
        logger.error(f"Gagal unduh data: {e}")
        send_telegram_alert("ERROR SISTEM: Gagal mengunduh data pasar.")
        return
    
    for ticker, category in ALL_STOCKS.items():
        try:
            df = data[ticker].dropna() if len(ALL_STOCKS) > 1 else data.dropna()
            if df.empty:
                continue
            
            result = analyze_smart_money(ticker, df, category)
            
            if result:
                signals_found += 1
                is_gorengan = category == "Gorengan"
                
                if is_gorengan:
                    gorengan_signals += 1
                
                # Format pesan berdasarkan jenis sinyal
                if result['signal_type'] == "DISTRIBUTION":
                    distribution_signals += 1
                    message = (
                        f"🔴 *PERINGATAN DISTRIBUSI!*\n\n"
                        f"📈 *Saham:* #{result['ticker']} ({result['category']})\n"
                        f"💰 *Harga:* Rp {result['price']:,.0f}\n"
                        f"📊 *Skor:* {result['score']}/100\n\n"
                        f"⚠️ *SINYAL DISTRIBUSI:*\n"
                        f"- Harga naik {result['price_change_20']:.1f}% (20 hari)\n"
                        f"- OBV turun {result['obv_trend']:.1f}% (Smart Money jual)\n"
                        f"- Volume spike {result['vol_ratio']:.1f}x\n\n"
                        f"🛑 *AKSI:*\n"
                        f"- JANGAN BELI (potensi pump & dump)\n"
                        f"- Jika pegang, pertimbangkan JUAL\n"
                        f"- Pasang Trailing Stop Loss ketat\n\n"
                        f"⚡ *Smart Money sedang exit!*"
                    )
                    logger.warning(f"🔴 Sinyal DISTRIBUSI: {ticker}")
                    
                elif result['signal_type'] == "PULLBACK":
                    pullback_signals += 1
                    emoji = "🟢" if not is_gorengan else "🟡"
                    message = (
                        f"{emoji} *ZONA PULLBACK INSTITUSI!*\n\n"
                        f"📈 *Saham:* #{result['ticker']} ({result['category']})\n"
                        f"💰 *Harga:* Rp {result['price']:,.0f}\n"
                        f"📊 *Skor:* {result['score']}/100\n\n"
                        f"✅ *SINYAL PULLBACK:*\n"
                        f"- Harga koreksi ke VWAP (Rp {result['vwap']:,.0f})\n"
                        f"- Tren utama masih naik (di atas EMA 50)\n"
                        f"- CMF: {result['cmf']:.3f} (uang masih masuk)\n"
                        f"- OBV trend: {result['obv_trend']:.1f}%\n\n"
                        f"🎯 *AKSI:*\n"
                        f"- Area IDEAL untuk cicil beli\n"
                        f"- Entry: Dekati VWAP (Rp {result['vwap']:,.0f})\n"
                        f"- Stop Loss: Di bawah EMA 50\n"
                    )
                    
                    if is_gorengan:
                        message += (
                            f"\n⚠️ *PERINGATAN: SAHAM GORENGAN!*\n"
                            f"- Risiko manipulasi TINGGI\n"
                            f"- Hanya untuk trader berpengalaman\n"
                            f"- Stop Loss WAJIB ketat (max 3-5%)\n"
                        )
                    
                    logger.info(f"{emoji} Sinyal PULLBACK: {ticker}")
                    
                elif result['signal_type'] == "STRONG_ACCUMULATION":
                    accumulation_signals += 1
                    message = (
                        f"🔥 *AKUMULASI SMART MONEY KUAT!*\n\n"
                        f"📈 *Saham:* #{result['ticker']} ({result['category']})\n"
                        f"💰 *Harga:* Rp {result['price']:,.0f}\n"
                        f"📊 *Skor:* {result['score']}/100\n\n"
                        f"✅ *INDIKATOR:*\n"
                        f"- CMF: {result['cmf']:.3f} (uang masuk kuat)\n"
                        f"- OBV trend: {result['obv_trend']:.1f}% (akumulasi)\n"
                        f"- Volume: {result['vol_ratio']:.1f}x rata-rata\n"
                        f"- Tren: Di atas EMA 20 & 50\n\n"
                        f"🎯 *AKSI:*\n"
                        f"- Pertimbangkan untuk AKUMULASI\n"
                        f"- Tunggu pullback ke VWAP untuk entry\n"
                        f"- Stop Loss: 2x ATR di bawah harga\n"
                    )
                    
                    if is_gorengan:
                        message += (
                            f"\n⚠️ *PERINGATAN: SAHAM GORENGAN!*\n"
                            f"- Meski ada akumulasi, risiko tetap tinggi\n"
                            f"- Gunakan position sizing kecil (max 5%)\n"
                        )
                    
                    logger.info(f"🔥 Sinyal AKUMULASI KUAT: {ticker}")
                    
                elif result['signal_type'] == "MODERATE_ACCUMULATION":
                    accumulation_signals += 1
                    message = (
                        f"🟡 *AKUMULASI MODERAT*\n\n"
                        f"📈 *Saham:* #{result['ticker']} ({result['category']})\n"
                        f"💰 *Harga:* Rp {result['price']:,.0f}\n"
                        f"📊 *Skor:* {result['score']}/100\n\n"
                        f"📋 *INDIKATOR:*\n"
                        f"- CMF: {result['cmf']:.3f}\n"
                        f"- OBV trend: {result['obv_trend']:.1f}%\n"
                        f"- Volume: {result['vol_ratio']:.1f}x\n\n"
                        f"🎯 *AKSI:*\n"
                        f"- Masuk WATCHLIST\n"
                        f"- Tunggu konfirmasi tambahan\n"
                        f"- Jangan FOMO beli\n"
                    )
                    
                    logger.info(f"🟡 Sinyal AKUMULASI MODERAT: {ticker}")
                
                send_telegram_alert(message)
        
        except Exception as e:
            logger.error(f"Error proses {ticker}: {e}")
    
    # ==========================================
    # LAPORAN AKHIR
    # ==========================================
    if signals_found == 0:
        logger.info("Tidak ada sinyal hari ini")
        send_telegram_alert(
            f"🔍 *Laporan Harian Smart Money*\n\n"
            f"Memindai {len(ALL_STOCKS)} saham syariah:\n"
            f"- {len(WATCHLIST_BLUECHIP)} Blue Chip\n"
            f"- {len(WATCHLIST_JII)} JII\n"
            f"- {len(WATCHLIST_SECOND)} Second Liner\n"
            f"- {len(WATCHLIST_GORENGAN)} Gorengan\n\n"
            f"Tidak ada sinyal Smart Money hari ini.\n\n"
            f"📊 Pasar sedang tenang/konsolidasi.\n"
            f"💵 Tetap pegang cash atau tunggu setup lain.\n"
            f"🛡️ *Stay safe!*"
        )
    else:
        logger.info(f"Selesai. Total {signals_found} sinyal ditemukan")
        
        summary_msg = (
            f"📊 *Ringkasan Harian Smart Money*\n\n"
            f"🎯 Total sinyal: {signals_found}\n"
            f"🟢 Pullback: {pullback_signals}\n"
            f"🔥 Akumulasi: {accumulation_signals}\n"
            f"🔴 Distribusi: {distribution_signals}\n"
            f"⚠️ Gorengan: {gorengan_signals}\n\n"
            f"Dari {len(ALL_STOCKS)} saham syariah yang dipindai.\n"
        )
        
        if distribution_signals > 0:
            summary_msg += "\n🚨 *HATI-HATI: Ada sinyal distribusi!*"
        if pullback_signals > 0:
            summary_msg += "\n✅ *Ada peluang pullback untuk dicicil!*"
            
        send_telegram_alert(summary_msg)

# ==========================================
# 5. EKSEKUSI
# ==========================================
if __name__ == "__main__":
    run_screener()
