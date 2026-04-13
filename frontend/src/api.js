const API_PREFIX = '/api/v1'

async function parseJson(res) {
  const payload = await res.json().catch(() => ({ code: -1, message: 'invalid response', data: null }))
  if (!res.ok || payload.code !== 0) {
    const error = new Error(payload.message || 'request failed')
    error.code = payload.code || res.status
    error.payload = payload
    throw error
  }
  return payload.data
}

export async function createTask({ file, retainLayout, detectTables, outputName, conversionMode }) {
  const form = new FormData()
  form.append('file', file)
  form.append('retainLayout', String(retainLayout))
  form.append('detectTables', String(detectTables))
  if (outputName) form.append('outputName', outputName)
  if (conversionMode) form.append('conversionMode', conversionMode)

  const res = await fetch(`${API_PREFIX}/tasks`, {
    method: 'POST',
    body: form
  })
  return parseJson(res)
}

export async function fetchTask(taskId) {
  const res = await fetch(`${API_PREFIX}/tasks/${taskId}`)
  return parseJson(res)
}

export async function deleteTask(taskId) {
  const res = await fetch(`${API_PREFIX}/tasks/${taskId}`, { method: 'DELETE' })
  return parseJson(res)
}

export function buildResultUrl(taskId) {
  return `${API_PREFIX}/tasks/${taskId}/result`
}
