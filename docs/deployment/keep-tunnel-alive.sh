#!/bin/bash
# 放在 Mac 上，自动保持 5191 端口转发
# 用法：chmod +x keep-tunnel-alive.sh && ./keep-tunnel-alive.sh

export SSHPASS='cjy#260609'

while true; do
  # 检查隧道是否还活着
  if ! curl -sf http://127.0.0.1:5191/api/health > /dev/null 2>&1; then
    echo "[$(date '+%H:%M:%S')] 隧道断了，重建..."
    pkill -f "ssh.*5191.*5190" 2>/dev/null
    sshpass -e ssh \
      -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ServerAliveInterval=10 -o ServerAliveCountMax=6 \
      -o TCPKeepAlive=yes \
      -fN -L 5191:127.0.0.1:5190 \
      -p 22222 caojiayuan@localhost 2>/dev/null
    sleep 2
  fi
  sleep 30
done
