export async function readResponse(response) {
  let data
  try { data = await response.json() } catch { throw new Error('服务器返回了无效响应') }
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : '请求失败 (' + response.status + ')')
  return data
}

export async function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)
  return readResponse(await fetch('/api/documents', { method: 'POST', body: form }))
}

export async function getPageLayout(id, number) {
  return readResponse(await fetch('/api/documents/' + id + '/pages/' + number))
}

export async function getCamelotTables(id, number, strategy) {
  return readResponse(await fetch('/api/documents/' + id + '/pages/' + number + '/camelot/' + strategy))
}

export async function getDocLayoutTables(id, number, threshold) {
  return readResponse(await fetch('/api/documents/' + id + '/pages/' + number + '/doclayout?threshold=' + threshold))
}

export async function deleteDocument(id) {
  if (id) await fetch('/api/documents/' + id, { method: 'DELETE' })
}
