# online-ver 分支来源

本分支来自 203 服务器当前线上代码的安全导出。

- 导出时间: 2026-07-26 CST
- 服务器: 203.25.216.15 / gongyis.neusym.cn:5190
- 源目录: /opt/smart-process-system/app
- 运行方式: systemd + nginx + gunicorn + 独立 YOLO uvicorn，未切 Docker

导出时已排除 .env、数据库、日志、SSL key、运行输出、虚拟环境、node_modules、Docker 迁移大包等运行态或敏感文件。
