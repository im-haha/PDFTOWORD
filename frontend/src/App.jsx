import { useEffect, useMemo, useState } from 'react'
import { buildResultUrl, createTask, deleteTask, fetchTask } from './api'
import FileDropzone from './components/FileDropzone'
import HistoryTable from './components/HistoryTable'
import ProgressBar from './components/ProgressBar'
import StatusPill from './components/StatusPill'
import { loadHistory, removeHistory, upsertHistory } from './storage'

const POLL_STATUS = new Set(['queued', 'processing'])

const DEFAULT_FORM = {
  retainLayout: true,
  detectTables: false,
  outputName: '',
  conversionMode: 'resume'
}

function mapError(error) {
  if (!error) return ''
  if (error.code) {
    return `错误码 ${error.code}: ${error.message}`
  }
  return error.message || '请求失败'
}

export default function App() {
  const [file, setFile] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [form, setForm] = useState(DEFAULT_FORM)
  const [busy, setBusy] = useState(false)
  const [task, setTask] = useState(null)
  const [error, setError] = useState('')
  const [history, setHistory] = useState(() => loadHistory())

  const currentTaskId = task?.taskId

  useEffect(() => {
    if (!currentTaskId || !POLL_STATUS.has(task.status)) return

    const timer = setInterval(async () => {
      try {
        const latest = await fetchTask(currentTaskId)
        setTask(latest)
        setHistory(upsertHistory(latest))
      } catch (err) {
        setError(mapError(err))
      }
    }, 2000)

    return () => clearInterval(timer)
  }, [currentTaskId, task?.status])

  const canSubmit = useMemo(() => !!file && !busy, [file, busy])

  async function handleSubmit(event) {
    event?.preventDefault?.()
    if (!file) {
      setError('请先选择 PDF 文件')
      return
    }

    setBusy(true)
    setError('')

    try {
      const accepted = await createTask({
        file,
        retainLayout: form.retainLayout,
        detectTables: form.detectTables,
        outputName: form.outputName.trim() || undefined,
        conversionMode: form.conversionMode
      })

      const baseTask = {
        taskId: accepted.taskId,
        status: accepted.status,
        progress: 0,
        sourceFilename: file.name,
        conversionMode: form.conversionMode,
        retainLayout: form.retainLayout,
        detectTables: form.detectTables,
        createdAt: accepted.createdAt,
        startedAt: null,
        finishedAt: null,
        downloadUrl: null,
        errorCode: null,
        errorMessage: null,
        report: null,
        layoutWarnings: [],
        fontSubstitutions: {},
        fallbackSummary: { fallbackBlockCount: 0, degradedTableCount: 0 },
        qualityGrade: null
      }

      setTask(baseTask)
      setHistory(upsertHistory(baseTask))
    } catch (err) {
      setError(mapError(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRefresh(taskId = currentTaskId) {
    if (!taskId) return
    try {
      const latest = await fetchTask(taskId)
      setTask(latest)
      setHistory(upsertHistory(latest))
    } catch (err) {
      setError(mapError(err))
    }
  }

  async function handleHistorySelect(taskId) {
    await handleRefresh(taskId)
  }

  async function handleDelete(taskId) {
    try {
      await deleteTask(taskId)
      const next = removeHistory(taskId)
      setHistory(next)
      if (currentTaskId === taskId) {
        setTask(null)
      }
    } catch (err) {
      setError(mapError(err))
    }
  }

  function handleDownload(taskId = currentTaskId) {
    if (!taskId) return
    window.open(buildResultUrl(taskId), '_blank')
  }

  return (
    <main className="shell">
      <header className="hero">
        <div className="hero-brand">PDF to Word</div>
        <h1>文本型 PDF 高保真转换工作台</h1>
        <p>
          上传 PDF，异步转换，轮询状态，下载结果。`resume` 按简历模板重排；`editable` 优先可编辑性；`visual_exact` 优先外观还原。
        </p>
      </header>

      <section className="grid two-col">
        <form className="panel" onSubmit={handleSubmit}>
          <h2>上传任务</h2>
          <FileDropzone
            file={file}
            dragActive={dragActive}
            onDragState={setDragActive}
            onFileSelect={(picked, err) => {
              if (err) {
                setError(err)
                setFile(null)
              } else {
                setError('')
                setFile(picked)
              }
            }}
            disabled={busy}
          />

          <div className="form-grid">
            <label>
              输出文件名（可选）
              <input
                type="text"
                placeholder="例如 report.docx"
                value={form.outputName}
                onChange={(e) => setForm((old) => ({ ...old, outputName: e.target.value }))}
              />
            </label>

            <label>
              转换模式
              <select
                value={form.conversionMode}
                onChange={(e) => setForm((old) => ({ ...old, conversionMode: e.target.value }))}
              >
                <option value="resume">resume（按简历模板重排）</option>
                <option value="editable">editable（可编辑优先）</option>
                <option value="visual_exact">visual_exact（外观最接近原 PDF）</option>
              </select>
            </label>
            {form.conversionMode === 'resume' ? (
              <div className="mode-risk">
                当前模式会按简历结构重组内容，更统一，但不保证完全保留原始视觉排版。
              </div>
            ) : null}
            {form.conversionMode === 'visual_exact' ? (
              <div className="mode-risk">
                当前模式更像原版 PDF，但正文可能是页面图片，不适合深度编辑。
              </div>
            ) : null}
          </div>

          <div className="toggles">
            <label>
              <input
                type="checkbox"
                checked={form.retainLayout}
                onChange={(e) => setForm((old) => ({ ...old, retainLayout: e.target.checked }))}
              />
              retainLayout（尽量保留页面布局）
            </label>
            <label>
              <input
                type="checkbox"
                checked={form.detectTables}
                onChange={(e) => setForm((old) => ({ ...old, detectTables: e.target.checked }))}
              />
              detectTables（启用表格检测）
            </label>
          </div>

          <div className="actions">
            <button type="submit" disabled={!canSubmit}>开始转换</button>
          </div>
          {error ? <div className="error-box">{error}</div> : null}
        </form>

        <section className="panel">
          <h2>任务详情</h2>
          {!task ? (
            <div className="empty">尚未创建任务</div>
          ) : (
            <>
              <div className="task-head">
                <div className="mono">{task.taskId}</div>
                <StatusPill status={task.status} />
              </div>

              <dl className="task-meta">
                <div>
                  <dt>文件名</dt>
                  <dd>{task.sourceFilename || '-'}</dd>
                </div>
                <div>
                  <dt>创建时间</dt>
                  <dd>{task.createdAt ? new Date(task.createdAt).toLocaleString() : '-'}</dd>
                </div>
                <div>
                  <dt>开始时间</dt>
                  <dd>{task.startedAt ? new Date(task.startedAt).toLocaleString() : '-'}</dd>
                </div>
                <div>
                  <dt>结束时间</dt>
                  <dd>{task.finishedAt ? new Date(task.finishedAt).toLocaleString() : '-'}</dd>
                </div>
                <div>
                  <dt>模式</dt>
                  <dd>{task.conversionMode || '-'}</dd>
                </div>
                <div>
                  <dt>retainLayout</dt>
                  <dd>{task.retainLayout ? '开启' : '关闭'}</dd>
                </div>
              </dl>

              <ProgressBar value={task.progress || 0} />

              {task.report ? (
                <div className="report-box">
                  <div className="report-title">质量报告</div>
                  <div className="report-grid">
                    <div>质量等级: <b>{task.qualityGrade || task.report.qualityGrade || '-'}</b></div>
                    <div>段落数: {task.report.paragraphCount ?? '-'}</div>
                    <div>表格数: {task.report.tableCount ?? '-'}</div>
                    <div>图片数: {task.report.imageCount ?? '-'}</div>
                    <div>字体替代: {task.report.fontSubstitutionCount ?? '-'}</div>
                    <div>退化块: {task.report.fallbackBlockCount ?? '-'}</div>
                    <div>页面警告: {task.report.layoutWarningCount ?? '-'}</div>
                  </div>
                  {task.layoutWarnings?.length ? (
                    <ul className="warnings-list">
                      {task.layoutWarnings.slice(0, 8).map((w, idx) => (
                        <li key={`${idx}-${w}`}>{w}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}

              {task.errorMessage ? (
                <div className="error-box">{task.errorCode || 'FAILED'}: {task.errorMessage}</div>
              ) : null}

              <div className="actions">
                <button type="button" onClick={() => handleRefresh()}>刷新状态</button>
                {task.status === 'succeeded' ? (
                  <button type="button" onClick={() => handleDownload()}>下载 DOCX</button>
                ) : null}
                {task.status === 'failed' && file ? (
                  <button type="button" onClick={handleSubmit}>重试当前文件</button>
                ) : null}
              </div>
            </>
          )}
        </section>
      </section>

      <section className="panel panel-history">
        <div className="history-header">
          <h2>历史记录</h2>
          <p>本地保存最近 100 条任务（浏览器 localStorage）</p>
        </div>

        <HistoryTable
          history={history}
          onSelect={handleHistorySelect}
          onDelete={handleDelete}
          onDownload={handleDownload}
        />
      </section>

      <footer className="footnote">
        当前状态机: idle, uploading, queued, processing, succeeded or failed
      </footer>
    </main>
  )
}
