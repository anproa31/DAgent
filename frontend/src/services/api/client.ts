import axios from 'axios'

/** Legacy analysis server (spaces, tables, model list). */
export const SERVER_BASE_URL =
  import.meta.env.VITE_SERVER_URL || 'http://localhost:8000'

/** Agent orchestration service (sessions, runs, SSE). */
export const AGENT_BASE_URL =
  import.meta.env.VITE_AGENT_SERVICE_URL || 'http://localhost:8074'

export const serverClient = axios.create({ baseURL: SERVER_BASE_URL })
export const agentClient = axios.create({ baseURL: AGENT_BASE_URL })
