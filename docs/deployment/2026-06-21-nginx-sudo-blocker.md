# 阻塞问题：Nginx 域名配置需要 sudo 权限

**记录时间：** 2026-06-21 23:20  
**严重程度：** 🟡 中等（不影响现有功能，但域名未生效）  
**状态：** 等待管理员授权

## 问题描述

服务器用户 `caojiayuan` 不在 sudoers 中，无法完成 nginx 站点配置。

## 当前状态扫描

| 关键节点 | 状态 |
|----------|------|
| CP1: 代码冻结 | ✅ 完成（5次提交，tar包就绪） |
| CP2: 服务器部署 | ✅ 完成（health 200, capabilities 正常） |
| CP2: 前端 copyright | ✅ 已更新（`机器学习与工业智能应用教育部工程研究中心`） |
| CP3: 业务验收 | 🔄 进行中（端口转发已通，待跑流程） |
| CP4: nginx 域名 | 🟡 阻塞（需 sudo） |
| CP4: systemd 服务 | 🟡 阻塞（需 sudo） |
| CP4: 磁盘清理 | 🟡 待处理（根分区 99%） |

## 架构现状（防止漂移）

```
当前架构：
  用户 → gongyi.neusymlab.cn (DNS) → 182.151.23.45
    → [期望] nginx:80 → proxy_pass → Flask:5190
    → [当前] Flask:5190 直接监听 0.0.0.0（需要端口转发访问）

部署路径：~/smart-process-test/test
后端进程：nohup uv run python -m backend.run (PID 2940161)
Python：3.11.15 (via uv)
Node：v20.20.2 (via nvm)

不迁移项：
  - 数据库保持 SQLite（不迁移 PostgreSQL）
  - 不引入微服务/Celery/K8s
  - 不修改 API 路径和前端路由
```

## 待管理员执行的操作

已准备好的文件：`~/gongyi-nginx.conf`

```bash
# 管理员需在服务器上执行：
sudo cp ~/gongyi-nginx.conf /etc/nginx/sites-available/gongyi
sudo ln -sf /etc/nginx/sites-available/gongyi /etc/nginx/sites-enabled/gongyi
sudo nginx -t
sudo systemctl reload nginx
```

## nginx 配置内容

```
server {
    listen 80;
    server_name gongyi.neusymlab.cn;
    client_max_body_size 100m;

    location / {
        proxy_pass http://127.0.0.1:5190;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/events/ {
        proxy_pass http://127.0.0.1:5190;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        add_header X-Accel-Buffering no;
    }
}
```

## 验证命令（sudo 配置完成后）

```bash
# 从服务器本机
curl -H "Host: gongyi.neusymlab.cn" http://127.0.0.1/api/health

# 从 Mac
curl -f http://gongyi.neusymlab.cn/api/health
```

## 后续注意事项

1. nginx 配置后，端口转发 (`-L 5191:127.0.0.1:5190`) 不再需要
2. 考虑后续添加 SSL（Let's Encrypt certbot）
3. systemd 服务也需要 sudo，可一并处理
4. 磁盘清理（/tmp 1.3G，/var/log/btmp 835M）也需 sudo

---

*关联：[[task_plan]] Phase 4-CP4, [[findings]] 服务器状态*
