# 服务器访问指南：模型训练

> 适用：需要在 `liu4th` 服务器上训练模型的同事。包含完整的上传→训练→监控流程。

---

## ⛔ 进入服务器前必读：3 条红线

| 红线 | 后果 |
|------|------|
| **不要删除/修改 `~/smart-process-test/` 下的任何文件** | 网站上运行的工艺系统会崩 |
| **不要把大数据写到 `/home/` 下** | 磁盘只剩 1%，满了服务器宕机 |
| **不要改 `.env` 文件** | LLM/视觉/嵌入所有 key 会失效 |

> 想看完整的保护清单？同目录下 `DONT-TOUCH.md`

---

## 1. 服务器长什么样

```
你的电脑                      跳板机                    GPU 服务器
┌──────────┐   SSH(22)     ┌──────────────┐  SSH(12350)  ┌──────────┐
│ Mac/PC   │ ────────────→ │ 182.151.23.45 │ ───────────→ │ liu4th    │
│          │    密码 ↓      │              │   密码 ↓     │ GPU 服务器│
└──────────┘              └──────────────┘             └──────────┘
```

| 项目 | 值 |
|------|-----|
| 服务器名 | liu4th (Ubuntu 24.04) |
| 账号 | `caojiayuan` |
| 密码 | `cjy#260609`（两台一样） |
| GPU | 通过 `nvidia-smi` 查看 |
| 磁盘 | `/home/` 只剩 13G ⚠️ **数据放 `/mnt/data/`**（有 233G） |

---

## 2. 第一步：登录（选一种）

### 方式 A：简单两步（推荐新手）

打开终端：

```bash
# 第 1 步
ssh caojiayuan@182.151.23.45
# 输密码：cjy#260609

# 第 2 步（连上跳板机后）
ssh -p 12350 caojiayuan@localhost
# 输密码：cjy#260609

# 进来了！确认一下
hostname          # 应该输出 liu4th
nvidia-smi        # 看 GPU 状态
```

### 方式 B：sshpass 一行（推荐常用）

只在你的 **Mac** 上装一次 `sshpass`：

```bash
brew install sshpass
```

然后把这段加到 `~/.zshrc` 或 `~/.bashrc`：

```bash
inner() {
  SSHPASS='cjy#260609' sshpass -e ssh \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -J caojiayuan@182.151.23.45 \
    -p 12350 caojiayuan@localhost "$@"
}
```

之后每次用只需一行：

```bash
inner           # 直接登录
inner "nvidia-smi"   # 执行单条命令
```

> **注意**：如果 `-J`（ProxyJump）用不了，参考附录 A 用隧道方式。

---

## 3. 第二步：上传数据集（2GB）

**关键：数据放 `/mnt/data/`，不要放 `/home/`！** 根分区快满了。

### 3.1 在服务器上建工作目录

```bash
# 先登录服务器
mkdir -p /mnt/data/your_name/dataset
mkdir -p /mnt/data/your_name/code
mkdir -p /mnt/data/your_name/output
```

### 3.2 从本地上传

```bash
# 在你的 Mac 上打包（压缩可省一半时间）
cd ~/your_project
tar -czf /tmp/training.tar.gz code/ dataset/

# 上传到 /mnt/data（走跳板机）
scp -o "ProxyJump=caojiayuan@182.151.23.45" \
    -P 12350 \
    /tmp/training.tar.gz \
    caojiayuan@localhost:/mnt/data/your_name/

# 如果用 sshpass（免交互输密码）：
SSHPASS='cjy#260609' sshpass -e scp \
  -o StrictHostKeyChecking=no \
  -o ProxyJump=caojiayuan@182.151.23.45 \
  -P 12350 \
  /tmp/training.tar.gz \
  caojiayuan@localhost:/mnt/data/your_name/
```

### 3.3 在服务器上解压

```bash
cd /mnt/data/your_name
tar -xzf training.tar.gz
ls -la
```

**如果 scp 的 ProxyJump 不行**，用附录 A 的隧道方式传文件，更稳。

---

## 4. 第三步：跑训练

### 4.1 先看 GPU 有没有人用

```bash
nvidia-smi
```

关注 "Memory-Usage" 那列。如果有人占满显存，等一等或用 CPU 训练。

### 4.2 创建 Python 环境

```bash
# 服务器已有 Python 3.11.15（通过 uv）
# 在自己的代码目录下建虚拟环境
cd /mnt/data/your_name/code
python3 -m venv .venv
source .venv/bin/activate
pip install torch torchvision  # 你的依赖
```

### 4.3 用 screen 跑（断网也不怕）

```bash
# 创建训练会话
screen -S training

# 在里面执行训练
cd /mnt/data/your_name/code
source .venv/bin/activate
python train.py --data /mnt/data/your_name/dataset --output /mnt/data/your_name/output

# 脱离 screen（训练继续跑，你可以关电脑）
# 按 Ctrl+A 然后按 D
```

### 4.4 随时回来看进度

```bash
screen -r training     # 重连训练会话
# 如果报 "Attached"，先 screen -d training 再 screen -r training
```

### 4.5 监控日志（不用进 screen）

```bash
tail -f /mnt/data/your_name/output/train.log
```

---

## 5. 文件传输速查

| 方向 | 命令（在本机执行） |
|------|-------------------|
| 上传代码 | `scp -o ProxyJump=... -P 12350 file.zip caojiayuan@localhost:/mnt/data/your_name/` |
| 下载模型 | `scp -o ProxyJump=... -P 12350 caojiayuan@localhost:/mnt/data/your_name/output/model.pt .` |
| 上传大文件（rsync 续传） | `rsync -avzP -e "ssh -J caojiayuan@182.151.23.45 -p 12350" file caojiayuan@localhost:/mnt/data/your_name/` |

---

## 6. 训练跑完后

### 下载模型

```bash
# 在 Mac 上执行
scp -o "ProxyJump=caojiayuan@182.151.23.45" -P 12350 \
  caojiayuan@localhost:/mnt/data/your_name/output/model.pt \
  ./
```

### 清理显存

```bash
# 在服务器上（训练完成后）
# 先退出 screen，再：
nvidia-smi          # 确认显存已释放
```

### 清理磁盘

```bash
# 删除不需要的中间文件
cd /mnt/data/your_name
rm -rf *.tar.gz     # 删掉上传的压缩包
# 不要删别人的东西
```

---

## 7. 多人共用规则

| 规则 | 原因 |
|------|------|
| 自己的工作目录放 `/mnt/data/your_name/` | 互不干扰 |
| 训练前 `nvidia-smi` 看一眼 | 避免抢 GPU |
| 用 `screen` 命名会话 `screen -S your_name_training` | 分清谁的 session |
| 数据先在本机压缩再上传 | 2GB 不压缩要传很久 |
| 传完删 tar 包 | 留空间给别人 |

---

## 附录 A：隧道方式（Scp 更稳）

如果 `-J ProxyJump` 不好用，先建一条隧道再操作：

```bash
# 1. 建隧道（Mac 上执行，会背景运行）
SSHPASS='cjy#260609' sshpass -e ssh \
  -o StrictHostKeyChecking=no \
  -o ServerAliveInterval=30 \
  -fN -L 22222:localhost:12350 \
  caojiayuan@182.151.23.45

# 2. 通过隧道传文件（scp -P 22222）
SSHPASS='cjy#260609' sshpass -e scp \
  -P 22222 file.zip caojiayuan@localhost:/mnt/data/your_name/

# 3. 隧道断了重建
ps aux | grep "ssh.*22222"    # 看还在不在
# 不在就重新执行第 1 步
```

---

## 附录 B：故障排查

| 现象 | 排查 |
|------|------|
| 连不上 | `curl http://182.151.23.45` — 跳板机能通吗？ |
| 密码错 | Mac 键盘特殊字符：`#` 确认没被转义 |
| 上传太慢 | 先 `tar -czf` 压缩，2GB 能压到几百 MB |
| 显存满了 | `nvidia-smi` 看谁在用，或 `top` 看 CPU |
| screen 卡住 | `screen -ls` 列出所有会话，`screen -X -S name quit` 杀会话 |
| 磁盘满了 | `df -h /` 看根分区，`du -sh /mnt/data/*` 看各人占用 |

---

## 附录 C：受保护目录 ⛔

以下目录和文件**绝对不要碰**。正在运行的工艺系统依赖它们。

```
~/smart-process-test/            ← 整个工艺系统
~/smart-process-test/.env        ← 所有 API key
~/smart-process-test/db_data/    ← 知识库数据库
~/.local/bin/uv                  ← Python 包管理器
```

系统存活验证：`curl -f http://127.0.0.1:5190/api/health`

---

*有任何问题问曹家源，别自己试。*
