@echo off
chcp 65001 >nul 2>&1

echo 开始拉取...
git pull
echo 拉取完成
echo 开始同步子仓库...
git submodule update --remote
echo 子仓库同步完成

pause