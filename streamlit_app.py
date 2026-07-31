# -*- coding: utf-8 -*-
"""
Momentum — Thunder Screener (Streamlit)
واجهة ويب تفاعلية فوق نفس المحرك thunder_screener.py
التشغيل:
    pip install -r requirements.txt
    streamlit run streamlit_app.py
"""
import streamlit as st
import plotly.graph_objects as go
import thunder_screener as ts

st.set_page_config(page_title="MOMENTUM ⚡", page_icon="⚡", layout="wide")

# ============================ i18n ============================
T = {
 "ar": {"title": "⚡ MOMENTUM", "lang": "اللغة",
   "mode": "وضع الفحص", "swing": "مضاربة أسبوع (سوينغ)", "explosion": "صيد الانفجارات",
   "pmin": "أدنى سعر $", "pmax": "أقصى سعر $", "full": "كامل السوق الأمريكي (أبطأ)",
   "run": "🔍 ابدأ الفحص", "running": "جاري الفحص… قد يستغرق دقائق حسب حجم السوق",
   "tab_stocks": "🎯 فحص الأسهم", "tab_macro": "🌍 السلع",
   "st": {"launch": "🚀 الموجة بدأت", "watch": "👁 مراقبة", "wait": "⏳ انتظار", "chase": "🚫 ممتد — لا تطارد"},
   "price": "السعر", "mcap": "القيمة السوقية", "score": "الدرجة",
   "eta0": "🚀 اختراق حديث — نافذة الدخول مفتوحة", "etaN": "⏳ باقي ~{n} أيام للاختراق (تقديري)",
   "etaF": "⏳ القاعدة لم تنضج — أكثر من 10 أيام", "etaC": "🚫 انطلق بالفعل — انتظر إعادة الاختبار",
   "sig": ["بيع قوي", "بيع", "حياد", "شراء", "شراء قوي"],
   "momM": "زخم شهر", "momW": "زخم أسبوع", "mom3": "زخم 3 أيام",
   "outlook": "تصوّر الأيام القادمة", "tv": "الشارت في TradingView",
   "empty": "اضغط «ابدأ الفحص» من الشريط الجانبي", "none": "لا نتائج ضمن الشروط",
   "disclaimer": "أداة فحص وترجيح احتمالات — ليست نصيحة مالية.",
   "filter": "التصنيف", "all": "الكل"},
 "en": {"title": "⚡ MOMENTUM", "lang": "Language",
   "mode": "Scan mode", "swing": "Weekly swing", "explosion": "Explosion hunting",
   "pmin": "Min price $", "pmax": "Max price $", "full": "Full US market (slower)",
   "run": "🔍 Run scan", "running": "Scanning… may take minutes depending on universe",
   "tab_stocks": "🎯 Stock Scan", "tab_macro": "🌍 Commodities",
   "st": {"launch": "🚀 Wave started", "watch": "👁 Watch", "wait": "⏳ Wait", "chase": "🚫 Extended — don't chase"},
   "price": "Price", "mcap": "Market cap", "score": "Score",
   "eta0": "🚀 Fresh breakout — entry window open", "etaN": "⏳ ~{n} days to breakout (est.)",
   "etaF": "⏳ Base not mature — 10+ days", "etaC": "🚫 Already launched — wait for retest",
   "sig": ["STRONG SELL", "SELL", "NEUTRAL", "BUY", "STRONG BUY"],
   "momM": "1-month", "momW": "1-week", "mom3": "3-day",
   "outlook": "Coming days outlook", "tv": "Chart on TradingView",
   "empty": "Press “Run scan” in the sidebar", "none": "No results match the filters",
   "disclaimer": "A screening & probability tool — not financial advice.",
   "filter": "Status", "all": "All"},
}
SIGC = ["#c62828", "#ef5350", "#9e9e9e", "#66bb6a", "#1b8b3f"]
STC  = {"launch": "#34c759", "watch": "#ff9500", "wait": "#8e8e93", "chase": "#ff3b30"}

# ============================ الشريط الجانبي ============================
with st.sidebar:
    lang = "ar" if st.radio("Language / اللغة", ["العربية", "English"], horizontal=True) == "العربية" else "en"
    L = T[lang]
    st.title(L["title"])
    mode = st.radio(L["mode"], ["swing", "explosion"],
                    format_func=lambda m: L[m])
    pmin = st.number_input(L["pmin"], 0.5, 1000.0, 1.0, step=0.5)
    pmax = st.number_input(L["pmax"], 1.0, 10000.0, 12.0, step=1.0)
    full = st.checkbox(L["full"], value=False)
    run = st.button(L["run"], type="primary", use_container_width=True)
    st.caption(L["disclaimer"])

if lang == "ar":  # RTL
    st.markdown("<style>section.main div.block-container{direction:rtl;text-align:right}</style>",
                unsafe_allow_html=True)

# ============================ تشغيل الفحص ============================
def configure():
    ts.MODE = mode
    ts.P = {"explosion": dict(b1=-150, b2=-10, vs=10, vl=60, rs=63),
            "swing":     dict(b1=-40,  b2=-5,  vs=5,  vl=30, rs=21)}[mode]
    ts.PRICE_MIN, ts.PRICE_MAX, ts.FULL_MARKET = pmin, pmax, full

@st.cache_data(ttl=3600, show_spinner=False)
def run_scan(mode, pmin, pmax, full):
    import yfinance as yf
    tickers = ts.get_universe()
    if not ts.FMP_KEY:
        tickers = ts.prefilter_by_price(tickers)
    spy = yf.download("SPY", period="1y", progress=False, auto_adjust=True)["Close"].dropna()
    if hasattr(spy, "columns"): spy = spy.iloc[:, 0]
    spy_ret = float(spy.iloc[-1] / spy.iloc[-ts.P["rs"]] - 1)
    frames = ts.download_prices(tickers)
    scored = []
    for t_, df in frames.items():
        try:
            r = ts.score_stock(df, spy_ret); r["ticker"] = t_; scored.append(r)
        except Exception:
            pass
    scored.sort(key=lambda x: x["tech"], reverse=True)
    results = []
    for r in scored[:60]:
        f, mc, name, sector, industry = ts.fundamentals_score(r["ticker"])
        total = round(r["tech"] + f, 1)
        status = ("chase" if r["extended"] else
                  "launch" if total >= 72 and r["breakout"] and r["fresh"] and r["vol_confirm"] else
                  "watch" if total >= 55 else "wait")
        mc_txt = (f"{mc/1e9:.1f}B$" if mc >= 1e9 else f"{mc/1e6:.0f}M$") if mc else "—"
        results.append({**r, "score": total, "status": status, "name": name, "mcap": mc_txt,
                        "mc": mc, "sector": sector, "industry": industry})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:30], ts.macro_engine()

@st.cache_data(ttl=1800, show_spinner=False)
def run_macro_only():
    return ts.macro_engine()

if run:
    configure()
    with st.status(L["running"], expanded=False):
        stocks, macro = run_scan(mode, pmin, pmax, full)
    st.session_state["stocks"], st.session_state["macro"] = stocks, macro

# ============================ مكونات العرض ============================
def sig_idx(m):
    sc = (m.get("gauge") or 0)*0.5 + (m.get("mom5") or 0)*3 + (m.get("mom3") or 0)*4
    return 0 if sc <= -45 else 1 if sc <= -15 else 2 if sc < 15 else 3 if sc < 45 else 4

def gauge_fig(m):
    fig = go.Figure(go.Indicator(
        mode="gauge", value=m["gauge"],
        gauge={"axis": {"range": [-90, 90], "visible": False},
               "bar": {"color": "#1d1d1f", "thickness": 0.25},
               "steps": [{"range": [-90, -20], "color": "#ff3b30"},
                         {"range": [-20, 20], "color": "#d1d1d6"},
                         {"range": [20, 90], "color": "#34c759"}]}))
    fig.update_layout(height=180, margin=dict(t=10, b=10, l=20, r=20),
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig

def stock_card(s):
    color = STC[s["status"]]
    sigs = s["signals_en"] if lang == "en" else s["signals"]
    plan = (s.get("plan_en") if lang == "en" else s.get("plan"))
    eta = (L["etaC"] if s["status"] == "chase" else
           L["eta0"] if s["eta"] == 0 else
           L["etaN"].format(n=s["eta"]) if s["eta"] <= 10 else L["etaF"])
    with st.container(border=True):
        c1, c2 = st.columns([2, 1])
        c1.subheader(f'{s["ticker"]} · {s["name"][:28]}')
        act = " · ".join(x for x in [s.get("sector"), s.get("industry")] if x)
        if act: c1.caption(f"🏭 {act}")
        c2.markdown(f'<div style="text-align:center;background:{color}22;color:{color};'
                    f'padding:8px;border-radius:12px;font-weight:700">{L["st"][s["status"]]}</div>',
                    unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric(L["score"], f'{s["score"]}/100')
        m2.metric(L["price"], f'{s["close"]}$')
        m3.metric(L["mcap"], s["mcap"])
        st.progress(min(int(s["score"]), 100))
        st.info(eta)
        if plan: st.success(f"🎯 {plan}")
        for x in sigs: st.write("⚡", x)
        st.link_button(f'📈 {L["tv"]}', f'https://www.tradingview.com/chart/?symbol={s["ticker"]}',
                       use_container_width=True)

def macro_card(m):
    with st.container(border=True):
        st.subheader(m["name_en"] if lang == "en" else m["name"])
        st.caption(f'{m["priceLabel"]} · {L["momM"]}: {m["mom"]:+}% · '
                   f'{L["momW"]}: {m["mom5"]:+}% · {L["mom3"]}: {m["mom3"]:+}%')
        st.plotly_chart(gauge_fig(m), use_container_width=True,
                        config={"displayModeBar": False}, key="g" + m["name"])
        k = sig_idx(m)
        st.markdown(f'<div style="text-align:center;font-size:22px;font-weight:800;'
                    f'color:{SIGC[k]}">{L["sig"][k]}</div>', unsafe_allow_html=True)
        ol = m.get("outlook_en") if lang == "en" else m.get("outlook")
        if ol: st.info(f'**{L["outlook"]}:** {ol}')
        note = m.get("note_en") if lang == "en" else m.get("note")
        if note: st.caption(note)
        st.link_button(f'📈 {L["tv"]}', f'https://www.tradingview.com/chart/?symbol={m["tv"]}',
                       use_container_width=True)

# ============================ الصفحة ============================
st.title(L["title"])
tab1, tab2 = st.tabs([L["tab_stocks"], L["tab_macro"]])

with tab1:
    stocks = st.session_state.get("stocks")
    if not stocks:
        st.info(L["empty"])
    else:
        opts = ["all", "launch", "watch", "wait", "chase"]
        c1, c2, c3 = st.columns([2, 1, 1])
        flt = c1.radio(L["filter"], opts, horizontal=True,
                       format_func=lambda o: L["all"] if o == "all" else L["st"][o])
        sorts = {"score": "⭐", "priceAsc": "💲⬇", "priceDesc": "💲⬆", "volx": "📊", "mc": "🏢"}
        srt = c2.selectbox("Sort", list(sorts), format_func=lambda k: sorts[k] + " " + k)
        secs = ["all"] + sorted({s["sector"] for s in stocks if s.get("sector")})
        sec = c3.selectbox("Sector", secs)
        items = [s for s in stocks if (flt == "all" or s["status"] == flt)
                 and (sec == "all" or s.get("sector") == sec)]
        key = {"score": lambda s: -s["score"], "priceAsc": lambda s: s["close"],
               "priceDesc": lambda s: -s["close"], "volx": lambda s: -(s.get("volx") or 0),
               "mc": lambda s: s.get("mc") or 9e15}[srt]
        items.sort(key=key)
        if not items: st.warning(L["none"])
        cols = st.columns(3)
        for i, s in enumerate(items):
            with cols[i % 3]: stock_card(s)

with tab2:
    macro = st.session_state.get("macro")
    if macro is None:
        configure()
        with st.spinner(L["running"]):
            macro = run_macro_only()
        st.session_state["macro"] = macro
    cols = st.columns(3)
    for i, m in enumerate(macro):
        with cols[i % 3]: macro_card(m)

st.caption(L["disclaimer"])
