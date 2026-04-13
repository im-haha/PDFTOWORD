import StatusPill from './StatusPill'

export default function HistoryTable({ history, onSelect, onDelete, onDownload }) {
  if (!history.length) {
    return <div className="history-empty">暂无历史任务</div>
  }

  return (
    <div className="history-wrap">
      <table className="history-table">
        <thead>
          <tr>
            <th>文件名</th>
            <th>上传时间</th>
            <th>模式</th>
            <th>布局保留</th>
            <th>状态</th>
            <th>进度</th>
            <th>警告</th>
            <th>退化</th>
            <th>等级</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {history.map((item) => (
            <tr key={item.taskId}>
              <td>{item.sourceFilename || item.fileName || '-'}</td>
              <td>{item.createdAt ? new Date(item.createdAt).toLocaleString() : '-'}</td>
              <td>{item.conversionMode || '-'}</td>
              <td>{item.retainLayout ? '是' : '否'}</td>
              <td><StatusPill status={item.status || 'queued'} /></td>
              <td>{item.progress ?? 0}%</td>
              <td>{item.report?.layoutWarningCount ?? item.layoutWarnings?.length ?? 0}</td>
              <td>{item.report?.fallbackBlockCount ?? item.fallbackSummary?.fallbackBlockCount ?? 0}</td>
              <td>{item.qualityGrade || item.report?.qualityGrade || '-'}</td>
              <td className="row-actions">
                <button type="button" onClick={() => onSelect(item.taskId)}>详情</button>
                {item.status === 'succeeded' ? (
                  <button type="button" onClick={() => onDownload(item.taskId)}>下载</button>
                ) : null}
                <button type="button" className="danger" onClick={() => onDelete(item.taskId)}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
