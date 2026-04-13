const HISTORY_KEY = 'pdf_word_task_history_v1'

export function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return []
    const data = JSON.parse(raw)
    return Array.isArray(data) ? data : []
  } catch {
    return []
  }
}

export function saveHistory(entries) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, 100)))
}

export function upsertHistory(entry) {
  const list = loadHistory()
  const idx = list.findIndex((it) => it.taskId === entry.taskId)
  if (idx >= 0) {
    list[idx] = { ...list[idx], ...entry }
  } else {
    list.unshift(entry)
  }
  saveHistory(list)
  return list
}

export function removeHistory(taskId) {
  const list = loadHistory().filter((it) => it.taskId !== taskId)
  saveHistory(list)
  return list
}
