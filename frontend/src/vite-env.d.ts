/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_SERVER_URL: string
  readonly VITE_AGENT_SERVICE_URL: string
  readonly USER_DATABASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
