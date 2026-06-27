# 管理员操作清单

> 服务器 liu4th，账号 caojiayuan。完成后系统即可通过 gongyi.neusym.cn 公网访问。

---

## 操作 1：启用 nginx 域名

配置文件已经写好在 `~/gongyi-nginx.conf`，需要管理员复制到 nginx 目录：

```bash
sudo cp /home/caojiayuan/gongyi-nginx.conf /etc/nginx/sites-available/gongyi
sudo ln -sf /etc/nginx/sites-available/gongyi /etc/nginx/sites-enabled/gongyi
sudo nginx -t
sudo systemctl reload nginx
```

验证：
```bash
curl -H "Host: gongyi.neusym.cn" http://127.0.0.1/api/health
# 应返回 {"status":"ok"}
```

## 操作 2：清理磁盘空间

根分区已用 99%，需要清理：

```bash
# 清理旧登录失败日志（~800MB）
sudo rm -f /var/log/btmp.1 /var/log/btmp

# 清理系统日志到 200MB 以内
sudo journalctl --vacuum-size=200M

# 查看结果
df -h /
```

## 操作 3（可选但建议）：systemd 开机自启

让系统重启后后端自动启动。服务文件模板在 `~/smart-process-test/test/deploy/linux/smart-process.service`，需要根据当前环境调整：

```bash
sudo tee /etc/systemd/system/smart-process.service << 'EOF'
[Unit]
Description=Smart Process System
After=network.target

[Service]
Type=simple
User=caojiayuan
WorkingDirectory=/home/caojiayuan/smart-process-test/test
Environment=FLASK_DEBUG=0
EnvironmentFile=/home/caojiayuan/smart-process-test/test/.env
ExecStart=/home/caojiayuan/.local/bin/uv run python -m backend.run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable smart-process
sudo systemctl start smart-process
```

> 注意：启用 systemd 前先停掉当前的 nohup 进程：
> ```bash
> pkill -f "python -m backend.run"
> ```

---

## 完成后验证

```bash
# 从公网访问
curl -f http://gongyi.neusym.cn/api/health

# 检查服务状态
sudo systemctl status smart-process

# 检查磁盘
df -h /
```

---

*有任何问题联系 caojiayuan。*
