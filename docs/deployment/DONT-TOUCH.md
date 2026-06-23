# ⛔ 服务器保护清单

> 给所有需要登录 `liu4th` 服务器的同事。**这些操作会导致系统宕机，请勿执行。**

---

## 🚫 绝对不能碰的 5 件事

1. **不要 `rm` `~/smart-process-test/test/` 下的任何东西** — 系统在跑
2. **不要改 `.env` 文件** — key 被覆盖后视觉/LLM/检索全废
3. **不要手动操作 `db_data/*.db`** — 删了就丢了所有知识库记录
4. **不要 `pkill python`** — 后端停了网站就挂了
5. **不要 `rm -rf frontend-react/dist/`** — 前端直接 404

## 🔒 受保护目录

```
~/smart-process-test/test/             ← 整个目录，不 rm
~/smart-process-test/test/.env          ← 密钥文件，不改
~/smart-process-test/test/db_data/      ← 数据库，不碰
~/smart-process-test/test/frontend-react/dist/  ← 前端，不删
~/smart-process-test/test.old/          ← 回退副本，不删
~/smart-process-test/.env.backup.*      ← 密钥备份，不删
```

## ✅ 可以安全做的事

- 在自己的目录下放文件（`~/your_project/`）
- 用 `/mnt/data` 存大数据（有 233G 可用）
- `nvidia-smi` 看 GPU
- `screen` / `nohup` 跑训练
- 读 `server.log` 看日志（不要覆盖写）
- `curl http://127.0.0.1:5190/api/health` 看状态

## ⚠️ 磁盘注意

根分区 **99% 已满**，不要把大文件写到 `/home/caojiayuan/`下。大数据集放 `/mnt/data/`。

## ❓ 不确定能不能操作？

问曹家源。别猜。

---

*此文件故意简短，只读不执行。*
