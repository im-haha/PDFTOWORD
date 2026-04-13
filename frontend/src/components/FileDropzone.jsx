import { useRef } from 'react'

export default function FileDropzone({
  file,
  dragActive,
  onDragState,
  onFileSelect,
  disabled = false
}) {
  const inputRef = useRef(null)

  const handleFiles = (files) => {
    const picked = files?.[0]
    if (!picked) return
    if (!picked.name.toLowerCase().endsWith('.pdf')) {
      onFileSelect(null, '请上传 .pdf 文件')
      return
    }
    if (picked.size > 50 * 1024 * 1024) {
      onFileSelect(null, '文件大小不能超过 50MB')
      return
    }
    onFileSelect(picked)
  }

  const onDrop = (event) => {
    event.preventDefault()
    event.stopPropagation()
    onDragState(false)
    if (disabled) return
    handleFiles(event.dataTransfer?.files)
  }

  return (
    <section
      className={`dropzone ${dragActive ? 'is-active' : ''} ${disabled ? 'is-disabled' : ''}`}
      onDragEnter={(e) => {
        e.preventDefault()
        if (!disabled) onDragState(true)
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={(e) => {
        e.preventDefault()
        onDragState(false)
      }}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
          e.preventDefault()
          inputRef.current?.click()
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        hidden
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />

      <div className="dropzone-title">拖拽 PDF 到此处，或点击选择文件</div>
      <div className="dropzone-subtitle">
        仅支持文本型 PDF，最大 50MB，最多 300 页
      </div>
      {file ? <div className="dropzone-file">当前文件: {file.name}</div> : null}
    </section>
  )
}
