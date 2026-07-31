#!/bin/zsh
# MOMENTUM — فحص السوق ثم النشر التلقائي على Netlify (نفس الرابط)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
cd ~/Thunder || exit 1
/usr/bin/python3 thunder_screener.py >> scan.log 2>&1
mkdir -p publish
cp dashboard.html publish/index.html
/opt/homebrew/bin/netlify deploy --prod --dir=publish --site d37a252b-2f7d-406b-a069-e78adc8bcf8a >> publish.log 2>&1
echo "$(date '+%Y-%m-%d %H:%M') published" >> publish.log
