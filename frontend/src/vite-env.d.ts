/// <reference types="vite/client" />

declare module '*.md?raw' {
  const content: string
  export default content
}
interface ImportMetaEnv {
  readonly VITE_SERVER_URL: string
  readonly VITE_AGENT_SERVICE_URL: string
  readonly USER_DATABASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
