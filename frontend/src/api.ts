import type { DashboardData, Thread } from './types'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`Falha ao carregar (${response.status})`)
  return response.json() as Promise<T>
}

export const api = {
  dashboard: () => getJson<DashboardData>('/api/dashboard'),
  thread: (id: string) => getJson<Thread>(`/api/threads/${encodeURIComponent(id)}`),
}
