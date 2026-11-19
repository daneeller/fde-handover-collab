#!/usr/bin/env python3
"""部署入口：读取 PORT 环境变量，绑定 0.0.0.0 启动 FastAPI MVP。"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
