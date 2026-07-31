#!/bin/zsh
# ============================================================
# Thunder Screener — runner script (مشغّل الفحص التلقائي)
# يشغّله launchd مرتين يومياً. يحدّث dashboard.html + results.json
# ============================================================

# --- مسارات Python الشائعة على macOS حتى يجد launchd المفسّر الصحيح ---
export PATH="/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# --- (اختياري) لو Python عندك في مكان غير قياسي، حط مساره الكامل هنا ---
# مثال: PYTHON="/opt/homebrew/bin/python3.12"
PYTHON=""

# ينتقل لمجلد السكربت (مجلد Thunder) مهما كان مكان التشغيل
cd "$(dirname "$0")" || exit 1

# يحدد أمر python3
if [ -z "$PYTHON" ]; then
  PYTHON="$(command -v python3 || echo /usr/bin/python3)"
fi

LOG="thunder.log"
echo "" >> "$LOG"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') | بدء الفحص | python=$PYTHON =====" >> "$LOG"

# تحقق سريع أن yfinance مثبت — وإلا رسالة واضحة بدل فشل صامت
if ! "$PYTHON" -c "import yfinance" >/dev/null 2>&1; then
  echo "⚠️ المكتبات ناقصة (yfinance). ثبّتها بالأمر:" >> "$LOG"
  echo "   $PYTHON -m pip install yfinance pandas lxml" >> "$LOG"
  exit 1
fi

# تشغيل الفحص
"$PYTHON" thunder_screener.py >> "$LOG" 2>&1
RC=$?

echo "===== $(date '+%Y-%m-%d %H:%M:%S') | انتهى | كود الخروج=$RC =====" >> "$LOG"
exit $RC
