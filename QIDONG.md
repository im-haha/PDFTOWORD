# 启动说明（前后端）

## 1. 启动后端

```bash
cd /Users/chen/Desktop/code/PDF
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端地址：
- `http://127.0.0.1:8000`
- 文档：`http://127.0.0.1:8000/docs`

## 2. 启动前端

首次安装依赖：
```bash
cd /Users/chen/Desktop/code/PDF/frontend
npm install
```

开发模式启动：
```bash
cd /Users/chen/Desktop/code/PDF/frontend
npm run dev
```

前端地址：
- `http://127.0.0.1:5173`

说明：
- 前端已配置 Vite 代理，`/api` 会自动转发到 `http://127.0.0.1:8000`。

## 3. 联调流程

1. 先启动后端。
2. 再启动前端。
3. 打开 `http://127.0.0.1:5173`，上传 PDF，查看状态，下载结果。

补充：
- 前端默认 `resume` 模式（按标准简历模板重排）。
- 如需“视觉尽量一模一样”，可在界面里切换 `visual_exact`（该模式会按页转图片嵌入 Word）。
