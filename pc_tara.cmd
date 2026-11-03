@echo off
cd /d C:\Users\hacke\kamu-ilan-takip
set PYTHONIOENCODING=utf-8
echo %date% %time% > son_tarama.log
"C:\Users\hacke\AppData\Local\Programs\Python\Python312\python.exe" tara.py >> son_tarama.log 2>&1
if errorlevel 1 exit /b 1
git add -A docs
git diff --cached --quiet || git commit -q -m "Tarama (PC)"
git pull -q --rebase >> son_tarama.log 2>&1
git push -q >> son_tarama.log 2>&1
