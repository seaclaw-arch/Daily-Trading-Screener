def run_screener():
    """Menjalankan screener ke seluruh watchlist."""
    
    # ==========================================
    # WATCHLIST SAHAM LIKUID (AMAN)
    # ==========================================
    WATCHLIST_LIQUID = [
        # === PERBANKAN (Banking) ===
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK",
        "BJBR.JK", "BJTM.JK", "BNGA.JK", "BDMN.JK", "PNBN.JK",
        "BACA.JK", "BTPN.JK", "MEGA.JK", "NISP.JK",
        
        # === TELEKOMUNIKASI (Telco) ===
        "TLKM.JK", "ISAT.JK", "EXCL.JK",
        
        # === OTOMOTIF & INDUSTRI ===
        "ASII.JK", "AUTO.JK", "IMAS.JK", "INDR.JK", "GGRM.JK",
        "UNTR.JK", "UNVR.JK", "MYOR.JK", "ICBP.JK", "INDF.JK",
        "JPFA.JK", "AISA.JK",
        
        # === PERTAMBANGAN & MINERAL - LIKUID ===
        "ANTM.JK", "MDKA.JK", "NCKL.JK", "INCO.JK", "TINS.JK",
        "ADRO.JK", "PTBA.JK", "ITMG.JK", "INDY.JK",
        "AKR.JK", "BUMI.JK",
        
        # === ENERGI & MINYAK ===
        "MEDC.JK", "PGAS.JK", "KRAS.JK",
        
        # === TEKNOLOGI & MEDIA ===
        "GOTO.JK", "BUKA.JK", "EMTK.JK", "SCMA.JK", "VIVA.JK",
        "NETV.JK", "DIGI.JK",
        
        # === PROPRTI & KONSTRUKSI ===
        "BSDE.JK", "CTRA.JK", "PWON.JK", "SMRA.JK", "LPKR.JK",
        "ASRI.JK", "ADHI.JK", "PTPP.JK", "WTON.JK", "JKON.JK",
        
        # === INFRASTRUKTUR ===
        "JSMR.JK", "MNCN.JK", "SMGR.JK", "INTP.JK",
        
        # === RITEL & KONSUMER ===
        "AMRT.JK", "MIDI.JK", "HERO.JK", "ACES.JK",
        "KLBF.JK", "PYFA.JK", "CAMP.JK",
        
        # === KESEHATAN ===
        "MIKA.JK", "HEAL.JK", "SILO.JK",
        
        # === SAHAM POPULER LAIN ===
        "CPIN.JK", "TOWR.JK", "TBIG.JK", "BRPT.JK",
        "TPIA.JK", "FREN.JK", "RAJA.JK", "ASSA.JK", "ROCK.JK"
    ]
    
    # ==========================================
    # WATCHLIST SAHAM TIDAK LIKUID (BERISIKO)
    # ==========================================
    WATCHLIST_ILLIQUID = [
        "DSSA.JK",    # ⚠️ Moderat
        "MORA.JK",    # ⚠️ Tidak likuid
        "DEWA.JK",    # 🔴 Bermasalah
        "TRIN.JK",    # ⚠️ Perlu meningkatkan likuiditas
        "IRSX.JK",    # 🔴 Volume sangat rendah
        "SKBM.JK",    # 🔴 Volume sangat rendah
        "SOTS.JK",    # 🔴 Volume sangat rendah
    ]
    
    # ==========================================
    # WATCHLIST SAHAM GORENGAN (SERING TRENDING)
    # ==========================================
    WATCHLIST_GORENGAN = [
        # 🔥 SAHAM GORENGAN - VOLTILITY TINGGI - SERING PUMP & DUMP
        "TRUE.JK",    # 🔴 Disuspensi berkali-kali, naik 1000%+
        "WBSA.JK",    # 🔴 95% saham dikuasai segelintir investor
        "BOLA.JK",    # 🔥 Sering trending, volatilitas ekstrem
        "SOCA.JK",    # 🔥 Saham gorengan populer
        "MKPI.JK",    # 🔥 Sering pump & dump
        "PORT.JK",    # 🔥 Volatilitas tinggi
        "NICK.JK",    # 🔥 Sering trending di media sosial
        "DOID.JK",    # 🔥 Saham batubara volatil
        "PSAB.JK",    # 🔥 Sering ada aksi korporasi mencurigakan
        "LAND.JK",    # 🔥 Saham properti gorengan
        "RAYA.JK",    # 🔥 Volatilitas ekstrem
        "TAXI.JK",    # 🔥 Saham lama yang sering digoreng
        "KIAS.JK",    # 🔥 Sering pump & dump
        "POLU.JK",    # 🔥 Volatilitas tinggi
        "GLVA.JK",    # 🔥 Saham gorengan klasik
    ]
    
    # Gabungkan semua watchlist
    WATCHLIST = WATCHLIST_LIQUID + WATCHLIST_ILLIQUID + WATCHLIST_GORENGAN
    
    # Hapus duplikat
    WATCHLIST = list(set(WATCHLIST))
    
    logger.info(f"🚀 Memulai IDX Sniper Screener - Memindai {len(WATCHLIST)} saham...")
    logger.info(f"   - Saham Likuid: {len(WATCHLIST_LIQUID)}")
    logger.info(f"   - Saham Tidak Likuid: {len(WATCHLIST_ILLIQUID)}")
    logger.info(f"   - Saham Gorengan: {len(WATCHLIST_GORENGAN)} 🔥")
    
    signals_found = 0
    illiquid_signals = 0
    gorengan_signals = 0
    
    try:
        logger.info("📥 Mengunduh data historis (batch download)...")
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
                
                # Cek kategori saham
                is_gorengan = ticker in WATCHLIST_GORENGAN
                is_illiquid = ticker in WATCHLIST_ILLIQUID
                
                if is_gorengan:
                    # 🔥 PERINGATAN EKSTRA untuk saham gorengan
                    gorengan_signals += 1
                    
                    message = (
                        f"🔥 * SAHAM GORENGAN TRENDING!*\n\n"
                        f"📈 *Saham:* #{result['ticker']}\n"
                        f"💰 *Harga Close:* Rp {result['close']:,.0f}\n"
                        f"🔥 *Volume:* {result['vol_ratio']:.1f}x dari rata-rata\n"
                        f"🎯 *Posisi Close:* {result['close_pos']:.0f}% dari range\n\n"
                        f"⚠️ *PERINGATAN KERAS:*\n"
                        f"• 🔴 Risiko manipulasi SANGAT TINGGI\n"
                        f"• 🔴 Pump & dump sangat mungkin\n"
                        f"• 🔴 Bisa disuspensi BEI kapan saja\n"
                        f"• 🔴 Spread bid-offer sangat lebar\n"
                        f"• 🔴 Sulit exit posisi\n"
                        f"• 🔴 Sinyal teknikal sering palsu\n\n"
                        f"🎰 *HANYA untuk trader profesional!*\n"
                        f"️ *Trading cepat (scalping/day trade)*\n"
                        f"🛑 *Stop Loss WAJIB ketat (max 3-5%)*\n"
                        f"💀 *Jangan hold overnight!*\n\n"
                        f"⚡ *Risiko tinggi = Profit/loss ekstrem*"
                    )
                    logger.warning(f"🔥 Sinyal SAHAM GORENGAN: {ticker}")
                    
                elif is_illiquid:
                    # ⚠️ Peringatan untuk saham tidak likuid
                    illiquid_signals += 1
                    
                    message = (
                        f"🚨 *️ PERINGATAN: SAHAM TIDAK LIKUID!*\n\n"
                        f"📈 *Saham:* #{result['ticker']}\n"
                        f"💰 *Harga Close:* Rp {result['close']:,.0f}\n"
                        f"🔥 *Volume:* {result['vol_ratio']:.1f}x dari rata-rata\n"
                        f"🎯 *Posisi Close:* {result['close_pos']:.0f}% dari range\n\n"
                        f"⚠️ *RISIKO TINGGI:*\n"
                        f"• Spread bid-offer lebar\n"
                        f"• Risiko manipulasi tinggi\n"
                        f"• Sulit jual saat panic selling\n"
                        f"• Sinyal bisa palsu\n\n"
                        f"🛑 *HANYA untuk trader berpengalaman!*\n"
                        f"🛡️ *Stop Loss WAJIB ketat!*"
                    )
                    logger.warning(f"⚠️ Sinyal saham TIDAK LIKUID: {ticker}")
                    
                else:
                    # ✅ Sinyal normal untuk saham likuid
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
                    logger.info(f"✅ Sinyal ditemukan: {ticker}")
                
                send_telegram_alert(message)
        
        except Exception as e:
            logger.error(f"⚠️ Error proses {ticker}: {e}")
    
    # Laporan akhir
    if signals_found == 0:
        logger.info("💤 Tidak ada sinyal VPA hari ini")
        send_telegram_alert(
            "🔍 *Laporan Harian IDX Sniper*\n\n"
            f"Memindai {len(WATCHLIST)} saham:\n"
            f"• {len(WATCHLIST_LIQUID)} saham likuid ✅\n"
            f"• {len(WATCHLIST_ILLIQUID)} saham tidak likuid ⚠️\n"
            f"• {len(WATCHLIST_GORENGAN)} saham gorengan 🔥\n\n"
            "Tidak ada sinyal Akumulasi Institusi (VPA) yang terdeteksi hari ini.\n\n"
            "📊 Pasar sedang tenang.\n"
            "💵 Tetap pegang cash atau tunggu setup lain.\n"
            "🛡️ *Stay safe!*"
        )
    else:
        logger.info(f"🏁 Selesai. Total {signals_found} sinyal ditemukan")
        
        if gorengan_signals > 0 or illiquid_signals > 0:
            logger.warning(f"⚠️ {gorengan_signals + illiquid_signals} sinyal berisiko tinggi!")
        
        send_telegram_alert(
            f"📊 *Ringkasan Harian*\n\n"
            f"🎯 Total sinyal: {signals_found}\n"
            f"✅ Saham likuid: {signals_found - illiquid_signals - gorengan_signals}\n"
            f"⚠️ Saham tidak likuid: {illiquid_signals}\n"
            f"🔥 Saham gorengan: {gorengan_signals}\n\n"
            f"Dari {len(WATCHLIST)} saham yang dipindai.\n\n"
            f"{'🚨 *HATI-HATI dengan saham gorengan!' if gorengan_signals > 0 else ''}"
        )
