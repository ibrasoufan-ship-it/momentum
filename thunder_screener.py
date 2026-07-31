# -*- coding: utf-8 -*-
"""
Thunder Screener — Momentum
فلتر مركّب على السوق الأمريكي: وايكوف + الحجم + الكلاسيكي + الدورات + الأساسيات
التشغيل:  pip install yfinance pandas lxml   ثم   python thunder_screener.py
اختياري:  FMP_API_KEY=xxxx python thunder_screener.py   (لفحص كامل السوق وليس المؤشرات فقط)
الناتج:   dashboard.html (لوحة بطاقات عربية) + results.json
تنبيه: أداة فحص وترجيح احتمالات — ليست نصيحة مالية.
"""
import json, math, os, sys, time, datetime as dt
import pandas as pd
import yfinance as yf
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FMP_KEY = os.environ.get("FMP_API_KEY", "").strip()

# ===================== إعدادات الفلتر =====================
PRICE_MIN = 1.0        # يشمل أسهم 1-3$ — كلها تخضع لنفس فحص التجميع والاختراق والزخم
PRICE_MAX = 12.0       # استثناء الأسهم الغالية — ضع None لإلغاء الحد
MIN_AVG_VOLUME = 500_000        # سيولة: متوسط حجم يومي (أسهم)
MIN_DOLLAR_VOL = 3_000_000      # جودة: متوسط قيمة تداول يومية بالدولار
FULL_MARKET = True     # True = كامل رموز السوق الأمريكي (أبطأ أول مرة) / False = المؤشرات فقط
MODE = "swing"         # "swing" = مضاربة أسبوع واطلع / "explosion" = صيد الانفجارات الكبرى
# نوافذ الحساب لكل وضع: قاعدة التجميع، نوافذ الحجم، فترة القوة النسبية
P = {"explosion": dict(b1=-150, b2=-10, vs=10, vl=60, rs=63),
     "swing":     dict(b1=-40,  b2=-5,  vs=5,  vl=30, rs=21)}[MODE]
# ==========================================================

# ----------------------------- 1) بناء قائمة الفحص -----------------------------
def universe_from_fmp():
    """كامل السوق عبر FMP: قيمة سوقية 200M-50B وسيولة كافية (أرض الانفجارات)."""
    pmax = f"&priceLowerThan={PRICE_MAX}" if PRICE_MAX else ""
    url = ("https://financialmodelingprep.com/api/v3/stock-screener?"
           f"marketCapMoreThan=100000000&marketCapLowerThan=50000000000"
           f"&priceMoreThan={PRICE_MIN}{pmax}"
           f"&volumeMoreThan={MIN_AVG_VOLUME}&exchange=NASDAQ,NYSE,AMEX&isEtf=false"
           f"&isActivelyTrading=true&limit=5000&apikey={FMP_KEY}")
    data = json.load(urllib.request.urlopen(url, timeout=60))
    return sorted({d["symbol"] for d in data if d.get("symbol") and "." not in d["symbol"]})

def read_wiki_tables(url):
    """ويكيبيديا ترفض الطلبات بلا هوية متصفح — نرسل User-Agent."""
    import io
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) ThunderScreener/1.0"})
    html = urllib.request.urlopen(req, timeout=30).read()
    return pd.read_html(io.BytesIO(html))

def universe_from_indices():
    """بديل مجاني: S&P500 + Nasdaq-100 من ويكيبيديا."""
    tickers = set()
    try:
        sp = read_wiki_tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        tickers |= set(sp["Symbol"].astype(str))
    except Exception as e:
        print("S&P500 list failed:", e)
    try:
        for t in read_wiki_tables("https://en.wikipedia.org/wiki/Nasdaq-100"):
            if "Ticker" in t.columns: tickers |= set(t["Ticker"].astype(str)); break
            if "Symbol" in t.columns: tickers |= set(t["Symbol"].astype(str)); break
    except Exception as e:
        print("Nasdaq-100 list failed:", e)
    tickers = {t.replace(".", "-").strip() for t in tickers if t and t != "nan"}
    if not tickers:
        print("⚠️ تعذر الوصول لويكيبيديا — سأستخدم قائمة مدمجة (~130 سهمًا نشطًا)")
        tickers = set(("AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO AMD QCOM MU INTC SMCI PLTR APP "
            "CRWD PANW NET DDOG SNOW MDB ZS OKTA TEAM SHOP SQ COIN HOOD SOFI UPST AFRM "
            "MARA RIOT CLSK IONQ RGTI QUBT ACHR JOBY RKLB ASTS LUNR SOUN BBAI AI TMDX "
            "AXON ANET VRT MOD CELH ELF DECK ONON DKNG RCL CCL UAL DAL AAL ENPH FSLR "
            "RUN NEE XOM CVX OXY FANG DVN AR TPL LLY NVO UNH ISRG HIMS EXAS NTRA TDOC "
            "GILD MRNA BNTX REGN VRTX JPM GS MS SCHW BLK BX KKR APO V MA AXP PYPL "
            "CAT DE BA GE HON LMT RTX NOC ETN EMR PH ROK URI PWR FIX STRL IESC BLDR").split())
    return sorted(tickers)

def universe_full_free():
    """كامل رموز السوق الأمريكي من ملفات NASDAQ الرسمية المجانية."""
    tickers = set()
    urls = ["https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
            "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"]
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        lines = urllib.request.urlopen(req, timeout=45).read().decode().splitlines()
        head = lines[0].split("|")
        i_sym = 0
        i_etf = head.index("ETF") if "ETF" in head else None
        i_test = head.index("Test Issue") if "Test Issue" in head else None
        for ln in lines[1:-1]:
            p = ln.split("|")
            if len(p) <= max(i_etf or 0, i_test or 0): continue
            sym = p[i_sym].strip()
            if not sym or not sym.replace("-", "").isalpha(): continue
            if i_etf is not None and p[i_etf].strip() == "Y": continue
            if i_test is not None and p[i_test].strip() == "Y": continue
            if len(sym) > 5: continue   # استبعاد رموز الوحدات/الإذونات الغريبة
            tickers.add(sym)
    return sorted(tickers)

def get_universe():
    if FMP_KEY:
        try:
            u = universe_from_fmp()
            print(f"FMP universe: {len(u)} tickers (full-market, price {PRICE_MIN}-{PRICE_MAX}$)")
            return u
        except Exception as e:
            print("FMP failed, falling back:", e)
    if FULL_MARKET:
        try:
            u = universe_full_free()
            print(f"Full-market universe (NASDAQ official lists): {len(u)} tickers")
            return u
        except Exception as e:
            print("Full-market list failed, falling back to indices:", e)
    u = universe_from_indices()
    print(f"Index universe: {len(u)} tickers (S&P500 + Nasdaq-100)")
    if not u:
        sys.exit("لم أستطع بناء قائمة الفحص — تحقق من الإنترنت أو أضف FMP_API_KEY")
    return u

def prefilter_by_price(tickers):
    """مرحلة أولى سريعة: أسبوع أسعار فقط — نبقي أسهم 3-12$ ذات سيولة كافية."""
    keep = []
    B = 400
    for i in range(0, len(tickers), B):
        chunk = tickers[i:i+B]
        print(f"prefilter {i+1}-{i+len(chunk)} / {len(tickers)} ...")
        try:
            df = yf.download(chunk, period="5d", interval="1d", group_by="ticker",
                             progress=False, threads=True, auto_adjust=True)
        except Exception:
            continue
        for t in chunk:
            try:
                sub = df[t].dropna()
                px = float(sub["Close"].iloc[-1]); vol = float(sub["Volume"].mean())
                ok_price = px >= PRICE_MIN and (PRICE_MAX is None or px <= PRICE_MAX)
                if ok_price and vol >= MIN_AVG_VOLUME and px*vol >= MIN_DOLLAR_VOL:
                    keep.append(t)
            except Exception:
                pass
        time.sleep(0.5)
    print(f"✅ اجتاز فلتر السعر ({PRICE_MIN}-{PRICE_MAX}$) والجودة: {len(keep)} سهمًا")
    return keep

# ----------------------------- 2) تحميل الأسعار -----------------------------
def download_prices(tickers, period="2y"):
    frames = {}
    B = 150
    for i in range(0, len(tickers), B):
        chunk = tickers[i:i+B]
        print(f"downloading {i+1}-{i+len(chunk)} / {len(tickers)} ...")
        df = yf.download(chunk, period=period, interval="1d",
                         group_by="ticker", progress=False, threads=True, auto_adjust=True)
        for t in chunk:
            try:
                sub = df[t].dropna()
                if len(sub) >= 220: frames[t] = sub
            except Exception:
                pass
        time.sleep(1)
    print(f"usable histories: {len(frames)}")
    return frames

# ----------------------------- 3) المعادلة المركبة -----------------------------
def scale(x, lo, hi, pts):
    """تحويل قيمة إلى نقاط خطيًا بين lo و hi."""
    if x <= lo: return 0.0
    if x >= hi: return float(pts)
    return (x - lo) / (hi - lo) * pts

def back(series, n):
    """قراءة آمنة للخلف: لو السلسلة أقصر من n، نأخذ أقدم قيمة متاحة (يمنع IndexError)."""
    n = min(n, len(series))
    return float(series.iloc[-n]) if n >= 1 else float(series.iloc[0])

def score_stock(df, spy_ret3m):
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    close = float(c.iloc[-1])
    chg = round((close / float(c.iloc[-2]) - 1) * 100, 2) if len(c) > 1 else 0.0  # تغير اليوم %
    sig = []   # إشارات نصية للبطاقة

    # --- وايكوف / بنية التجميع (30) — نافذة قصيرة في وضع السوينغ ---
    base = df.iloc[P["b1"]:P["b2"]]
    b_hi, b_lo = float(base["High"].max()), float(base["Low"].min())
    tight = (b_hi - b_lo) / max(b_lo, 1e-9)
    s_tight = scale(0.60 - tight, 0.0, 0.40, 10)          # قاعدة أضيق = أفضل
    breakout = close > b_hi * 0.995
    near = close > b_hi * 0.93
    s_pos = 10 if breakout else (6 if near else scale((close - b_lo) / max(b_hi - b_lo, 1e-9), 0.3, 1.0, 4))
    half = len(base)//2
    hl = float(base["Low"].iloc[half:].min()) > float(base["Low"].iloc[:half].min())
    s_hl = 5 if hl else 0
    sp_win = 30 if MODE == "explosion" else 10
    last30_lo = float(l.iloc[-sp_win:].min())
    spring = last30_lo < b_lo * 1.02 and close > b_lo * (1.10 if MODE == "explosion" else 1.05)
    s_spring = 5 if spring else 0
    wyckoff = s_tight + s_pos + s_hl + s_spring
    if breakout and not (close > b_hi * 1.04):   # لا نكرّر "اختراق" لو صار ممتدًا
        sig.append(("اختراق سقف قاعدة التجميع", "Breakout above base resistance"))
    if tight < 0.30: sig.append((f"قاعدة ضيقة ({tight*100:.0f}%) — تجميع وايكوف",
                                 f"Tight base ({tight*100:.0f}%) — Wyckoff accumulation"))
    if spring: sig.append(("نموذج Spring — كسر كاذب ثم ارتداد", "Spring — false break then recovery"))

    # --- الحجم والسيولة (25) — نوافذ قصيرة في السوينغ ---
    v_s, v_l = float(v.iloc[-P["vs"]:].mean()), float(v.iloc[-P["vl"]:].mean())
    vol_ratio = v_s / max(v_l, 1)
    s_vr = scale(vol_ratio, 1.0, 2.5, 10)
    v_base = float(v.iloc[-P["vl"]:-P["vs"]].mean()); v_long = float(v.iloc[-max(P["vl"]*3, 90):].mean())
    dryup = v_base < v_long * 0.85
    s_dry = 7 if dryup else 0
    ch = c.diff().iloc[-50:]; vv = v.iloc[-50:]
    upv = float(vv[ch > 0].sum()); dnv = float(vv[ch < 0].sum())
    udr = upv / max(dnv, 1)
    s_ud = scale(udr, 1.0, 1.8, 8)
    volume = s_vr + s_dry + s_ud
    if vol_ratio >= 1.8: sig.append((f"انفجار حجم التداول ×{vol_ratio:.1f}", f"Volume surge ×{vol_ratio:.1f}"))
    if dryup: sig.append(("جفاف السيولة قبل الانطلاق", "Volume dry-up before launch"))
    if udr >= 1.3: sig.append(("حجم الصعود يفوق الهبوط — تجميع مؤسسي",
                               "Up-volume beats down-volume — institutional accumulation"))

    # --- الكلاسيكي: الاتجاه والقوة النسبية (20) ---
    sma200 = float(c.rolling(200).mean().iloc[-1])
    sma50  = float(c.rolling(50).mean().iloc[-1])
    s_t = (6 if close > sma200 else 0) + (4 if sma50 > sma200 else 0)
    above = int((c.iloc[-60:] > c.rolling(200).mean().iloc[-60:]).sum())
    s_hold = scale(above, 30, 55, 4)
    ret_p = close / back(c, P["rs"]) - 1
    rs = ret_p - spy_ret3m
    s_rs = scale(rs, 0.0, 0.25, 6)
    trend = s_t + s_hold + s_rs
    if close > sma200 and above >= 50: sig.append(("فوق متوسط 200 ومحافظ عليه", "Above 200-MA and holding"))
    if rs > 0.10: sig.append((f"قوة نسبية +{rs*100:.0f}% على SPY", f"Relative strength +{rs*100:.0f}% vs SPY"))

    # --- الدورة الزمنية (10) — منهج الكتاب: موجة دافعة أولى من قاع ---
    # 1) قاع حديث: أدنى 252 يومًا تشكّل خلال آخر 6 أشهر (الدورة وليدة)
    win = c.iloc[-252:]
    lo52_idx = int(win.values.argmin())
    weeks_since_low = (252 - lo52_idx) / 5.0
    bottom_recent = 3 <= weeks_since_low <= 34          # قاع تكوّن، وبدأت الحركة منه
    # 2) موجة أولى: ارتداد واضح من القاع دون امتداد مفرط (لم تكتمل الدورة)
    low52 = float(win.min())
    up_from_low = close / low52 - 1
    first_wave = 0.08 <= up_from_low <= 1.20            # انطلقت لكن ما زالت مبكرة
    # 3) هيكل صاعد وليد: قاع أعلى حديث فوق القاع الأصلي (تأكيد بداية الدورة)
    recent_lo = float(l.iloc[-20:].min())
    higher_bottom = recent_lo > low52 * 1.04
    cycle_start = bottom_recent and first_wave          # بداية الدورة الزمنية
    s_cyc1 = 6 if cycle_start else (3 if bottom_recent else 0)
    s_cyc2 = 4 if (higher_bottom and up_from_low < 1.0) else (2 if up_from_low < 2.0 else 0)
    cycle = s_cyc1 + s_cyc2
    if cycle_start:
        sig.append(("بداية دورة زمنية — موجة أولى من قاع (منهج الفراكتال)",
                    "Cycle start — first impulse wave off a bottom (fractal method)"))
    elif bottom_recent:
        sig.append(("موقع مبكر في الدورة — غير ممتد", "Early in cycle — not extended"))

    # --- عدّاد القرب من الاختراق: المسافة لسقف القاعدة ÷ متوسط الحركة اليومية ---
    atr = float(((h - l) / c).iloc[-14:].mean())          # متوسط المدى اليومي %

    # --- منع المطاردة + كشف "المحمّل": نضارة الاختراق، امتداده، استمرار السيولة ---
    fresh, extended, vol_confirm, loaded = False, False, False, False
    if breakout:
        ab = [bool(x) for x in (c.iloc[-15:] > b_hi * 0.995)]
        days_since = (len(ab) - 1 - ab.index(True)) if True in ab else 0
        ext_pct = close / b_hi - 1
        limit = max(0.05, 2.0 * atr) if days_since <= 1 else max(0.04, 1.2 * atr)
        extended = ext_pct > limit or days_since > 3
        fresh = (days_since <= 2) and not extended
        vol_confirm = float(v.iloc[-(days_since + 1)]) >= 1.5 * v_l

        # المحمّل: ممتد لكن السيولة ما زالت داخلة أسبوعًا + السعر ممسوك فوق الاختراق
        # (بصمة إعادة التجميع قبل الانفجار الكبير — حالة CPHL)
        v5 = float(v.iloc[-5:].mean())
        sma10 = float(c.rolling(10).mean().iloc[-1])
        vol_sustained = v5 >= 1.5 * v_l                      # حجم مرتفع مستمر
        # "ممسوك" = ما زال فوق مستواه قبل الاختراق ولم يتراجع (قياس غير ملوّث بالقاعدة)
        pre_bo = float(c.iloc[-min(days_since + 1, 10)])
        held = float(l.iloc[-3:].min()) > pre_bo             # قيعان أخيرة فوق مستوى ما قبل الاختراق
        holding = close > sma10 and held
        # قرار المستخدم: أُلغيت حالة "لا تطارد" — كل سهم اخترق وامتد = استمرار اتجاه
        loaded = extended            # أي اختراق ممتد يُصنّف "استمرار الاتجاه"

        if loaded:
            sig.insert(0, ("🔥 اخترق وما زال في اتجاهه — مرشح استمرار، ادخل على تصحيح",
                           "🔥 Broke out and still trending — continuation candidate, buy the pullback"))
        elif fresh and vol_confirm:
            sig.insert(0, ("✅ اختراق حديث ومؤكد بالحجم — نافذة الدخول مفتوحة",
                           "✅ Fresh volume-confirmed breakout — entry window open"))
        elif not vol_confirm:
            sig.append(("⚠️ اختراق بلا حجم مؤكد — احذر الاختراق الكاذب",
                        "⚠️ Breakout lacks volume — beware false breakout"))

    if breakout:
        eta = 0
    else:
        dist_pivot = max(b_hi - close, 0) / close
        eta = round(dist_pivot / max(atr * 0.6, 1e-6))    # 60% من المدى تقدم صافٍ متفائل
        eta = min(eta, 99)

    # --- خطة الصفقة (وضع السوينغ): دخول/وقف/هدف من تذبذب السهم الفعلي ---
    plan = plan_en = None
    if MODE == "swing":
        if loaded:
            pull = close * (1 - 1.2 * atr)                  # منطقة تصحيح للدخول
            stp  = b_hi * 0.97
            tgt2 = close * (1 + 4.0 * atr)
            plan = f"ادخل على تصحيح نحو {pull:.2f}$ · وقف {stp:.2f}$ · هدف ممتد {tgt2:.2f}$"
            plan_en = f"Buy the pullback toward {pull:.2f}$ · Stop {stp:.2f}$ · Extended target {tgt2:.2f}$"
        else:
            entry = close if breakout else b_hi * 1.002
            stop  = entry * (1 - 1.5 * atr)
            tgt   = entry * (1 + 3.0 * atr)
            plan = (f"دخول فوق {entry:.2f}$ · وقف {stop:.2f}$ (−{1.5*atr*100:.1f}%) · "
                    f"هدف الأسبوع {tgt:.2f}$ (+{3*atr*100:.1f}%)")
            plan_en = (f"Entry above {entry:.2f}$ · Stop {stop:.2f}$ (−{1.5*atr*100:.1f}%) · "
                       f"Weekly target {tgt:.2f}$ (+{3*atr*100:.1f}%)")

    # --- شيك-ليست المراحل: هل تخطّى السهم كل مرحلة؟ (✓ / ✗) ---
    checklist = [
        {"k": "acc",   "ar": "التجميع",          "en": "Accumulation", "ok": bool(s_tight >= 6 or hl or spring)},
        {"k": "vol",   "ar": "الحجم",            "en": "Volume",       "ok": bool(vol_ratio >= 1.3 or dryup or udr >= 1.3)},
        {"k": "trend", "ar": "الاتجاه",          "en": "Trend",        "ok": bool(close > sma200 or rs > 0.05)},
        {"k": "cycle", "ar": "بداية الدورة",     "en": "Cycle start",  "ok": bool(cycle_start)},
        {"k": "brk",   "ar": "الاختراق",         "en": "Breakout",     "ok": bool(breakout and vol_confirm and not extended)},
    ]

    tech = wyckoff + volume + trend + cycle   # من 85
    return {"tech": round(tech, 1), "volx": round(vol_ratio, 2),
            "wyckoff": round(wyckoff,1), "volume": round(volume,1),
            "trend": round(trend,1), "cycle": round(cycle,1), "breakout": bool(breakout),
            "cycle_start": bool(cycle_start), "checklist": checklist,
            "fresh": fresh, "extended": extended, "loaded": loaded, "vol_confirm": vol_confirm,
            "eta": eta, "plan": plan, "plan_en": plan_en, "close": round(close, 2), "chg": chg,
            "signals": [p[0] for p in sig[:4]], "signals_en": [p[1] for p in sig[:4]]}

def next_earnings(t):
    """أقرب موعد إعلان أرباح قادم (المحفز المجدول الأقوى) — أو None."""
    try:
        ed = yf.Ticker(t).calendar
        d = None
        if isinstance(ed, dict):
            v = ed.get("Earnings Date") or ed.get("EarningsDate")
            if v: d = v[0] if isinstance(v, (list, tuple)) else v
        elif ed is not None and hasattr(ed, "loc"):
            try: d = ed.loc["Earnings Date"][0]
            except Exception: pass
        if d is not None:
            d = pd.Timestamp(d).date()
            if d >= dt.date.today(): return str(d)
    except Exception:
        pass
    return None

def fundamentals_score(t):
    """15 نقطة: القيمة السوقية المثالية + الفلوت — تُحسب لأفضل المرشحين فقط."""
    try:
        info = yf.Ticker(t).info
        mc = info.get("marketCap") or 0
        flt = info.get("floatShares") or 0
        name = info.get("shortName") or t
        sector = info.get("sector") or ""
        industry = info.get("industry") or ""
        if 3e8 <= mc <= 2e10:   s_mc = 8      # المنطقة الذهبية للانفجارات
        elif 1e8 <= mc < 3e8:   s_mc = 6
        elif mc <= 1e11:        s_mc = 4
        else:                   s_mc = 2
        s_fl = 7 if 0 < flt <= 8e7 else (5 if flt <= 2e8 else 3)
        return s_mc + s_fl, mc, name, sector, industry
    except Exception:
        return 7, 0, t, "", ""

# ----------------------------- 4) الماكرو -----------------------------
MACRO = {"DX-Y.NYB": "الدولار", "GC=F": "الذهب", "CL=F": "النفط",
         "BTC-USD": "البتكوين", "^TNX": "عوائد السندات 10س"}
TV_MAP = {"الدولار": "CAPITALCOM:DXY", "الذهب": "TVC:GOLD", "النفط": "TVC:USOIL",
          "البتكوين": "BITSTAMP:BTCUSD", "عوائد السندات 10س": "TVC:US10Y"}
MACRO_EN = {"الدولار": "US Dollar", "الذهب": "Gold", "النفط": "Oil (WTI)",
            "البتكوين": "Bitcoin", "عوائد السندات 10س": "10Y Treasury Yield"}
NOTE_EN = {"الدولار": "Moves with bond yields — watch the 50-MA",
           "الذهب": "Rising dollar & yields = pressure on gold; the reverse is strong support",
           "النفط": "Follows its own trend; a weak dollar supports it",
           "البتكوين": "Weak-dollar liquidity fuels bitcoin",
           "عوائد السندات 10س": "Rising yields pressure gold and growth stocks"}

def macro_engine():
    out = []
    data = {}
    for sym, name in MACRO.items():
        try:
            d = yf.download(sym, period="1y", interval="1d", progress=False, auto_adjust=True)["Close"].dropna()
            if hasattr(d, "columns"): d = d.iloc[:, 0]
            data[sym] = d
        except Exception:
            pass
    def state(s):
        c = float(s.iloc[-1]); s50 = float(s.rolling(50).mean().iloc[-1])
        mom = c / float(s.iloc[-21]) - 1          # زخم شهر
        mom5 = c / float(s.iloc[-6]) - 1          # زخم أسبوع
        mom3 = c / float(s.iloc[-4]) - 1          # زخم 3 أيام
        dist = c / s50 - 1
        # العداد يمزج الاتجاه (بُعد عن متوسط 50 + زخم شهر) مع الزخم القصير
        # حتى لا تعلق الإبرة وسطًا أثناء التعافي القوي (مثل ارتداد النفط)
        gauge = max(-90, min(90, dist*450 + mom*300 + mom5*250 + mom3*150))
        reversal = (c < s50 and mom > 0.01) or (c > s50 and mom < -0.01)
        d = "up" if c > s50 and mom > 0 else "down" if c < s50 and mom < 0 else "flat"
        return d, mom, mom5, mom3, c, gauge, reversal

    def outlook(d, mom5, mom3):
        """تصوّر 3-5 أيام قادمة (عربي، إنجليزي): الاتجاه الشهري × الزخم القصير."""
        sh = mom3 * 0.6 + mom5 * 0.4
        if d == "down" and sh >= 0.01:
            return ("⬆️ ارتداد نشط داخل هبوط — الأيام 3-5 القادمة تميل للتعافي، وتحوّل حقيقي إن استمر",
                    "⬆️ Active bounce within a downtrend — next 3-5 days lean recovery; a real turn if it holds")
        if d == "down" and sh <= -0.01:
            return ("⬇️ الضغط الهابط مستمر — الأرجح مزيد من الضعف الأيام القادمة",
                    "⬇️ Downward pressure persists — more weakness likely in coming days")
        if d == "down":
            return ("↔️ تهدئة داخل هبوط — انتظر انحياز الزخم القصير",
                    "↔️ Pause within a downtrend — wait for short-term momentum to pick a side")
        if d == "up" and sh <= -0.01:
            return ("⬇️ جني أرباح داخل صعود — تراجع قصير محتمل ثم استئناف",
                    "⬇️ Profit-taking within an uptrend — brief dip likely, then resumption")
        if d == "up":
            return ("⬆️ الصعود مرشح للاستمرار الأيام 3-5 القادمة",
                    "⬆️ Uptrend likely to continue over the next 3-5 days")
        return ("↔️ حركة عرضية مرجحة — لا انحياز واضحًا",
                "↔️ Sideways action likely — no clear bias")
    st = {k: state(v) for k, v in data.items() if len(v) > 60}
    def s(k): return st.get(k, ("flat", 0, 0, 0, 0, 0, False))[0]
    rules = {
        "الدولار":  ("up" if s("DX-Y.NYB")=="up" else "down" if s("DX-Y.NYB")=="down" else "flat",
                    "يتحرك مع عوائد السندات — راقب كسر متوسط 50"),
        "الذهب":   ("down" if (s("DX-Y.NYB")=="up" and s("^TNX")=="up") else
                    "up" if (s("DX-Y.NYB")=="down" and s("^TNX")=="down") else s("GC=F"),
                    "دولار وعوائد صاعدة = ضغط على الذهب، والعكس دعم قوي"),
        "النفط":   (s("CL=F"), "اتجاهه الخاص + دولار ضعيف يدعمه"),
        "البتكوين": ("up" if (s("DX-Y.NYB")=="down" and s("BTC-USD")!="down") else s("BTC-USD"),
                    "سيولة الدولار الضعيف وقود البتكوين"),
        "عوائد السندات 10س": (s("^TNX"), "صعودها يضغط على الذهب وأسهم النمو"),
    }
    for sym, name in MACRO.items():
        if sym not in st: continue
        direction, note = rules[name]
        _, mom, mom5, mom3, px, gauge, reversal = st[sym]
        ol_ar, ol_en = outlook(direction, mom5, mom3)
        out.append({"name": name, "name_en": MACRO_EN.get(name, name), "live": True,
                    "tv": TV_MAP.get(name, ""),
                    "priceLabel": f"{px:,.2f}", "mom": round(mom*100, 1),
                    "mom5": round(mom5*100, 1), "mom3": round(mom3*100, 1),
                    "outlook": ol_ar, "outlook_en": ol_en,
                    "dir": direction, "gauge": round(gauge), "reversal": reversal,
                    "note": note + (" · ⚠️ زخم معاكس للاتجاه" if reversal else ""),
                    "note_en": NOTE_EN.get(name, "") + (" · ⚠️ Momentum against trend" if reversal else "")})
    return out

# ----------------------------- 4.5) التحليل: القطاعات والارتباطات -----------------------------
BENCH = {"SPY": "SPY", "QQQ": "QQQ", "DIA": "DIA",
         "gold": "GC=F", "oil": "CL=F", "btc": "BTC-USD", "bonds": "TLT"}
SEC_CACHE = os.path.join(HERE, "sectors.json")

def load_sec_cache():
    try:
        with open(SEC_CACHE, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {}

def save_sec_cache(d):
    try:
        with open(SEC_CACHE, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass

def analysis_engine(frames, sec_map):
    """دوران القطاعات + عكس التيار + أقمار السلع — من الأسعار المحملة أصلًا."""
    closes = pd.DataFrame({t: f["Close"] for t, f in frames.items()}).dropna(how="all")
    rets = closes.pct_change().iloc[-90:]                      # نافذة ارتباط 90 يومًا
    bench, bret = {}, {}
    for k, sym in BENCH.items():
        try:
            s = yf.download(sym, period="1y", progress=False, auto_adjust=True)["Close"].dropna()
            if hasattr(s, "columns"): s = s.iloc[:, 0]
            bench[k] = s
            bret[k] = s.pct_change().reindex(rets.index)
        except Exception:
            pass
    def corr_with(k):
        return rets.corrwith(bret[k]) if k in bret else pd.Series(dtype=float)

    # 1) أقمار السلع: أعلى الأسهم ارتباطًا بكل أصل
    sats = {}
    for k in ["gold", "oil", "btc", "bonds"]:
        c = corr_with(k).dropna().sort_values(ascending=False)
        sats[k] = [{"ticker": t, "corr": round(float(v), 2),
                    "close": round(float(closes[t].iloc[-1]), 2)}
                   for t, v in c.head(5).items() if v >= 0.30]

    # 2) عكس التيار: ارتباط سالب مع ناسداك وداو معًا
    mkt = (corr_with("QQQ") + corr_with("DIA")) / 2
    counter = [{"ticker": t, "corr": round(float(v), 2),
                "close": round(float(closes[t].iloc[-1]), 2),
                "sector": sec_map.get(t, "")}
               for t, v in mkt.dropna().sort_values().head(10).items() if v <= -0.20]

    # 3) دوران القطاعات: عوائد 3 و6 أشهر مقابل SPY + قادة كل قطاع
    n63, n126 = min(63, len(closes)-1), min(126, len(closes)-1)
    ret3 = closes.iloc[-1] / closes.iloc[-n63] - 1
    ret6 = closes.iloc[-1] / closes.iloc[-n126] - 1
    spy3 = float(bench["SPY"].iloc[-1] / back(bench["SPY"], 63) - 1) if "SPY" in bench and len(bench["SPY"]) else 0.0
    groups = {}
    for t in closes.columns:
        sec = sec_map.get(t)
        if sec and not pd.isna(ret3.get(t)): groups.setdefault(sec, []).append(t)
    sectors = []
    for sec, ts in groups.items():
        if len(ts) < 3: continue
        leaders = ret3[ts].sort_values(ascending=False).head(3)
        sectors.append({"name": sec, "n": len(ts),
                        "ret3": round(float(ret3[ts].mean())*100, 1),
                        "ret6": round(float(ret6[ts].mean())*100, 1),
                        "rs": round((float(ret3[ts].mean()) - spy3)*100, 1),
                        "leaders": [{"ticker": t2, "ret": round(float(v)*100, 1)}
                                    for t2, v in leaders.items()]})
    sectors.sort(key=lambda x: x["rs"], reverse=True)
    return {"window": 90, "sectors": sectors, "counter": counter, "sat": sats}

def fill_sector_cache(frames, sec_map, cap=300):
    """جلب قطاعات الرموز غير المعروفة (بحد أقصى لكل تشغيل — الكاش يكتمل عبر التشغيلات)."""
    missing = [t for t in frames if t not in sec_map][:cap]
    for i, t in enumerate(missing):
        try:
            sec_map[t] = yf.Ticker(t).info.get("sector") or ""
        except Exception:
            sec_map[t] = ""
        if i % 25 == 0: print(f"sector cache {i+1}/{len(missing)} ...")
        time.sleep(0.15)
    save_sec_cache(sec_map)
    return sec_map

# ----------------------------- 5) توليد اللوحة -----------------------------
def render(results, macro, analysis=None, tasi=None):
    tpl_path = os.path.join(HERE, "dashboard.html")
    with open(tpl_path, encoding="utf-8") as f: tpl = f.read()
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    mode_txt = "مضاربة أسبوع (سوينغ)" if MODE == "swing" else "صيد الانفجارات"
    mode_en = "Weekly swing" if MODE == "swing" else "Explosion hunting"
    payload = {"generated": now + " · وضع: " + mode_txt,
               "generated_en": now + " · Mode: " + mode_en,
               "demo": False, "stocks": results, "macro": macro,
               "analysis": analysis or {}, "tasi": tasi or []}
    js = json.dumps(payload, ensure_ascii=False)
    a, b = tpl.find("/*DATA_START*/"), tpl.find("/*DATA_END*/")
    tpl = tpl[:a] + "/*DATA_START*/ const DATA = " + js + "; " + tpl[b:]
    out = os.path.join(HERE, "dashboard.html")
    with open(out, "w", encoding="utf-8") as f: f.write(tpl)
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("✅ dashboard.html jahiz —", out)

# ----------------------------- 5.5) السوق السعودي (تاسي) -----------------------------
SCAN_TASI = True   # فحص السوق السعودي مع الأمريكي · اجعله False لإيقافه
# رموز تداول السعودية على ياهو تنتهي بـ .SR — أبرز الشركات النشطة
TASI_UNIVERSE = ("2222 1120 2010 7010 1180 1211 2280 1150 4300 2350 1050 1060 4001 4002 "
    "2380 1010 1080 1140 2020 2030 2060 2090 2170 2190 2210 2250 2290 2310 2330 2360 "
    "3020 3030 3040 3050 3060 3080 3090 4003 4004 4008 4009 4013 4020 4030 4040 4050 "
    "4061 4070 4080 4090 4100 4110 4140 4150 4160 4161 4162 4163 4164 4180 4190 4200 "
    "4220 4230 4240 4250 4260 4270 4280 4290 4321 4322 5110 6001 6002 6004 6010 6015 "
    "6020 6040 6050 6060 6070 6090 7020 7030 7040 7200 8010 8012 8020 8030 8040 8050 "
    "1201 1202 1210 1212 1213 1214 1301 1302 1303 1304 1320 1321 1322 1810 1820 1830 "
    "2001 2040 2050 2070 2080 2081 2100 2110 2120 2130 2140 2150 2160 2180 2200 2220 "
    "2230 2240 2270 2300 2320 2340 2370 2382 4031 4051 4191 4192 4291 4292 4310 4331").split()

def scan_tasi():
    """فحص السوق السعودي بنفس المعادلة — القوة النسبية على مؤشر تاسي."""
    syms = [f"{c}.SR" for c in TASI_UNIVERSE]
    print(f"فحص السوق السعودي (تاسي): {len(syms)} سهمًا ...")
    try:
        idx = yf.download("^TASI.SR", period="1y", progress=False, auto_adjust=True)["Close"].dropna()
        if hasattr(idx, "columns"): idx = idx.iloc[:, 0]
        idx_ret = float(idx.iloc[-1] / back(idx, P["rs"]) - 1) if len(idx) > 1 else 0.0
    except Exception:
        idx_ret = 0.0
    frames = {}
    for i in range(0, len(syms), 50):
        chunk = syms[i:i+50]
        try:
            df = yf.download(chunk, period="1y", interval="1d", group_by="ticker",
                             progress=False, threads=True, auto_adjust=True)
        except Exception:
            continue
        for s in chunk:
            try:
                sub = df[s].dropna()
                if len(sub) >= 120: frames[s] = sub
            except Exception:
                pass
        time.sleep(1)
    out = []
    for s, dfs in frames.items():
        try:
            r = score_stock(dfs, idx_ret)
        except Exception:
            continue
        code = s.replace(".SR", "")
        status = ("launch" if (r["loaded"] or (r["breakout"] and r["fresh"] and r["vol_confirm"]))
                  else "watch")
        out.append({"ticker": code, "name": code, "score": round(r["tech"] + 10, 1),
                    "earnings": None, "sector": "TASI", "industry": "", "mc": 0, "volx": r["volx"],
                    "status": status, "close": r["close"], "chg": r["chg"], "mcap": "—",
                    "eta": r["eta"], "plan": r["plan"], "plan_en": r["plan_en"],
                    "signals": r["signals"], "signals_en": r["signals_en"],
                    "checklist": r["checklist"], "cycle_start": r["cycle_start"],
                    "tv": f"TADAWUL:{code}"})
    out.sort(key=lambda x: x["score"], reverse=True)
    print(f"✅ تاسي: {len(out)} سهمًا مفحوصًا")
    return out[:40]

def main():
    tickers = get_universe()
    if not FMP_KEY:   # FMP يفلتر السعر من المصدر؛ غيره يحتاج المرحلة الأولى
        tickers = prefilter_by_price(tickers)
    if not tickers:
        sys.exit("لا أسهم ضمن نطاق السعر والجودة المطلوب")
    spy = yf.download("SPY", period="1y", progress=False, auto_adjust=True)["Close"].dropna()
    if hasattr(spy, "columns"): spy = spy.iloc[:, 0]
    spy_ret3m = float(spy.iloc[-1] / back(spy, P["rs"]) - 1) if len(spy) > 1 else 0.0
    frames = download_prices(tickers)

    scored = []
    for t, df in frames.items():
        try:
            r = score_stock(df, spy_ret3m); r["ticker"] = t; scored.append(r)
        except Exception:
            pass
    scored.sort(key=lambda x: x["tech"], reverse=True)

    top = scored[:60]   # الأساسيات لأفضل 60 فقط (لتسريع الفحص)
    results = []
    sec_map = load_sec_cache()
    for r in top:
        f, mc, name, sector, industry = fundamentals_score(r["ticker"])
        if sector: sec_map[r["ticker"]] = sector
        total = round(r["tech"] + f, 1)
        # دمج: أي اختراق = "منطلق" · وكل ما دونه = "مراقبة" (أُلغيت "انتظار")
        status = ("launch" if (r["loaded"] or (r["breakout"] and r["fresh"] and r["vol_confirm"]))
                  else "watch")
        mc_txt = (f"{mc/1e9:.1f}B$" if mc >= 1e9 else f"{mc/1e6:.0f}M$") if mc else "—"
        results.append({"ticker": r["ticker"], "name": name, "score": total,
                        "earnings": next_earnings(r["ticker"]),
                        "sector": sector, "industry": industry,
                        "mc": mc, "volx": r["volx"],
                        "status": status, "close": r["close"], "chg": r["chg"], "mcap": mc_txt,
                        "eta": r["eta"], "plan": r["plan"], "plan_en": r["plan_en"],
                        "signals": r["signals"], "signals_en": r["signals_en"],
                        "checklist": r["checklist"], "cycle_start": r["cycle_start"]})
        time.sleep(0.3)
    results.sort(key=lambda x: x["score"], reverse=True)
    macro = macro_engine()
    print("بناء التحليل: القطاعات والارتباطات ...")
    sec_map = fill_sector_cache(frames, sec_map)
    analysis = analysis_engine(frames, sec_map)
    tasi = []
    if SCAN_TASI:
        try: tasi = scan_tasi()
        except Exception as e: print("فحص تاسي فشل:", e)
    render(results[:50], macro, analysis, tasi)

if __name__ == "__main__":
    main()
