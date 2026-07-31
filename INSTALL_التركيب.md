# تشغيل Momentum لايف — تحديث تلقائي مرتين يومياً

يخلّي فحص Thunder يعيد نفسه تلقائياً **7:00 صباحاً** و**11:00 مساءً** أيام
الإثنين–الجمعة، ويحدّث `dashboard.html`. تفتح اللوحة وقت ما تبي وتلقاها طازجة.

الملفات الجديدة كلها داخل مجلد `~/Documents/Thunder`:
- `run_thunder.sh` — يشغّل الفحص ويسجّل الناتج في `thunder.log`
- `com.momentum.thunder.plist` — جدول launchd (المواعيد)

---

## 1) التركيب (مرة واحدة)

افتح تطبيق **Terminal** والصق هالأوامر (سطر سطر):

```bash
chmod +x ~/Documents/Thunder/run_thunder.sh
cp ~/Documents/Thunder/com.momentum.thunder.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.momentum.thunder 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.momentum.thunder.plist
launchctl enable gui/$(id -u)/com.momentum.thunder
```

> ملاحظة: أمر `launchctl load` القديم يعطي خطأ `Input/output error 5` في
> إصدارات macOS الحديثة — استخدم `bootstrap` كما بالأعلى.

خلاص — من الحين يشتغل تلقائياً في مواعيده.

للتأكد إنه اتسجّل:
```bash
launchctl print gui/$(id -u)/com.momentum.thunder | head
```
لازم يطلع بلوك فيه `com.momentum.thunder`.

---

## 2) اختبار فوري (بدون انتظار الموعد)

عشان تتأكد إن كل شي يشتغل، شغّله الحين يدوياً:
```bash
launchctl kickstart -k gui/$(id -u)/com.momentum.thunder
```
الفحص ياخذ عدة دقائق (يمسح السوق). تابع التقدّم من السجل:
```bash
tail -f ~/Documents/Thunder/thunder.log
```
(اضغط `Ctrl+C` للخروج من المتابعة). لمّا يخلص، افتح `dashboard.html` — تاريخ التوليد بالأعلى لازم يكون الحين.

---

## 3) تغيير الأوقات

عدّل الأرقام داخل `com.momentum.thunder.plist`:
`Hour` = الساعة (0–23)، `Minute` = الدقيقة. `Weekday`: 1=الإثنين … 5=الجمعة.

بعد أي تعديل، أعِد التحميل:
```bash
cp ~/Documents/Thunder/com.momentum.thunder.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u)/com.momentum.thunder
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.momentum.thunder.plist
```

---

## 4) إيقاف الجدولة

```bash
launchctl bootout gui/$(id -u)/com.momentum.thunder
rm ~/Library/LaunchAgents/com.momentum.thunder.plist
```

---

## 5) تفعيل الأسعار الحيّة (intraday) — اختياري لكنه "الخيار القوي"

اللوحة الآن تقدر تعرض **السعر الحالي و% التغيّر لحظياً** فوق كل بطاقة، وتحدّث
نفسها كل 60 ثانية وأنت فاتحها — عبر مزوّد **Finnhub** المجاني.

1. سجّل مجاناً وخُذ مفتاحك من: https://finnhub.io/register (دقيقة واحدة).
2. افتح `dashboard.html` بمحرر نصوص، ودوّر على السطر:
   ```js
   const FINNHUB_KEY = "PUT_YOUR_KEY_HERE";
   ```
   وبدّل `PUT_YOUR_KEY_HERE` بمفتاحك بين علامتي التنصيص. احفظ.
3. افتح `dashboard.html` في المتصفح — بيطلع مؤشر **🟢 مباشر** بأعلى الصفحة،
   والأسعار تبدأ تتحدّث لحظياً.

ملاحظات:
- بدون مفتاح، تبقى الأسعار = أسعار آخر فحص (ثابتة) وكل شي يشتغل عادي.
- المفتاح يظهر داخل ملف HTML على جهازك فقط — لا تنشر الملف للعامة وفيه مفتاحك.
- الباقة المجانية = 60 طلب/دقيقة. الإعداد الحالي آمن ضمنه. لو زدت عدد الأسهم
  كثير، ارفع `REFRESH_SEC` في نفس الملف.
- التحديث الحي **يبقى شغّال بعد كل فحص تلقائي** — أضفناه خارج منطقة البيانات
  اللي يعيد الفحص كتابتها.

---

## ملاحظات مهمة (بصراحة)

- **الجهاز لازم يكون شغّال** وقت الموعد. لو كان نائماً، launchd يشغّله عند أول
  استيقاظ. لو مطفي تماماً، يفوت الموعد لين المرة الجاية.
- لو طلع في `thunder.log` إن `yfinance` ناقص، ثبّت المكتبات:
  ```bash
  python3 -m pip install yfinance pandas lxml
  ```
  ولو Python عندك في مسار غريب، افتح `run_thunder.sh` وحط مساره في متغير
  `PYTHON` بأعلى الملف.
- البيانات من `yfinance` = شمعة يومية بتأخير بسيط (مو تِك لحظي). لسكرينر
  السوينغ الأسبوعي هذا كافٍ. لو حبيت لاحقاً أسعار intraday حيّة أو نشر على
  الإنترنت، أقدر أضيفها.
- هذي أداة فحص وترجيح احتمالات — **ليست نصيحة مالية**.
