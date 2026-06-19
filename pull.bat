@echo off
chcp 65001 >nul 2>&1

echo 开始拉取...
git pull
echo 拉取完成

pause
