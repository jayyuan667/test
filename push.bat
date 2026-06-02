@echo off
chcp 65001 >nul 2>&1

echo 提交开始...
git add .
git commit -m "update"
git push
echo 提交完成

pause
