const LABELS = {
  idle: '待开始',
  uploading: '上传中',
  queued: '排队中',
  processing: '转换中',
  succeeded: '已完成',
  failed: '失败'
}

export default function StatusPill({ status }) {
  return <span className={`status-pill status-${status}`}>{LABELS[status] || status}</span>
}
