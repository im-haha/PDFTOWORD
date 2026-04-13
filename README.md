# PDF -> Word 高保真转换服务（文本型 PDF）

基于你给的两份设计文档实现的可运行 MVP：
- `POST /api/v1/tasks` 上传 PDF，创建异步转换任务
- `GET /api/v1/tasks/{taskId}` 查询状态与进度
- `GET /api/v1/tasks/{taskId}/result` 下载 DOCX
- `DELETE /api/v1/tasks/{taskId}` 删除任务与文件
- `GET /api/v1/health` 健康检查

## 架构实现
- 前端轻：仅上传、轮询、下载
- 后端 API：校验/预检/任务创建
- Worker：异步执行转换（进程内队列版本）
- 存储：本地磁盘 `storage/source` + `storage/result`
- 任务元数据：SQLite `storage/tasks.db`

## 高保真策略（当前版本）
- 默认：`visual_exact`（视觉无损）模式，按页渲染写入 Word，外观最接近原 PDF
- 可选：`editable`（可编辑）模式，走段落/run/表格重建
- 解析：PyMuPDF `dict/raw` 级别块、行、span
- 生成：python-docx paragraph/run/section/table/image
- 字体：subset 字体名清洗 + 映射 + 粗斜体识别
- 布局：段落归并、基础对齐、缩进、页尺寸映射
- 表格：规则化文本栅格的基础识别（复杂表格降级）
- 预检：前 1~3 页文本密度 + 图片覆盖率 + span 密度联合判断

## 本地运行
1. 创建虚拟环境
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 启动服务
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. 打开文档
- Swagger: `http://127.0.0.1:8000/docs`

## 上传示例
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/tasks" \
  -F "file=@/absolute/path/to/sample.pdf" \
  -F "retainLayout=true" \
  -F "detectTables=true" \
  -F "conversionMode=visual_exact"
```

## 目录结构
```text
app/
  api/
  converter/
  models/
  schemas/
  services/
  utils/
  workers/
storage/
requirements.txt
README.md
```

## 说明
- 当前是“正式架构可演进 + 本地可跑通”的实现版本。
- 若要上生产，建议把进度缓存/队列替换为 Redis + Celery/RQ/Dramatiq，并补齐鉴权、限流、审计和对象存储。
