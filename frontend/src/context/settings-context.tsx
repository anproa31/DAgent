import React, { createContext, useContext, useState, useCallback } from 'react'

interface SettingsState {
  baseUrl: string
  apiKey: string
  embeddingBaseUrl: string
  embeddingModel: string
  setBaseUrl: (v: string) => void
  setApiKey: (v: string) => void
  setEmbeddingBaseUrl: (v: string) => void
  setEmbeddingModel: (v: string) => void
  resetSettings: () => void
}

const SettingsContext = createContext<SettingsState | null>(null)

const LS_BASE_URL_KEY = 'qm_settings_base_url'
const LS_API_KEY_KEY = 'qm_settings_api_key'
const LS_EMBED_URL_KEY = 'qm_settings_embed_url'
const LS_EMBED_MODEL_KEY = 'qm_settings_embed_model'

/** When unset in localStorage, assume local Ollama (OpenAI-compatible API). Dockerized frontends can set VITE_DEFAULT_OPENAI_BASE_URL (e.g. http://host.docker.internal:11434). */
const DEFAULT_BASE_URL: string =
  (import.meta.env.VITE_DEFAULT_OPENAI_BASE_URL as string | undefined) ||
  'http://localhost:11434'

/** Embedding endpoint for the memory system (KB ingestion + retrieval). Must point at an
 *  OpenAI-compatible /v1 endpoint serving the embedding model (Ollama: .../v1). */
const DEFAULT_EMBED_URL: string =
  (import.meta.env.VITE_DEFAULT_EMBEDDING_BASE_URL as string | undefined) ||
  'http://localhost:11434/v1'
const DEFAULT_EMBED_MODEL = 'nomic-embed-text'

function readInitialBaseUrl(): string {
  try {
    const stored = localStorage.getItem(LS_BASE_URL_KEY)
    if (stored != null && stored.trim() !== '') return stored
  } catch {
    // ignore
  }
  return DEFAULT_BASE_URL
}

function readInitialApiKey(): string {
  try {
    return localStorage.getItem(LS_API_KEY_KEY) || ''
  } catch {
    return ''
  }
}

function readInitial(key: string, fallback: string): string {
  try {
    const stored = localStorage.getItem(key)
    if (stored != null && stored.trim() !== '') return stored
  } catch {
    // ignore
  }
  return fallback
}

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [baseUrl, setBaseUrlState] = useState<string>(readInitialBaseUrl)
  const [apiKey, setApiKeyState] = useState<string>(readInitialApiKey)
  const [embeddingBaseUrl, setEmbeddingBaseUrlState] = useState<string>(() =>
    readInitial(LS_EMBED_URL_KEY, DEFAULT_EMBED_URL)
  )
  const [embeddingModel, setEmbeddingModelState] = useState<string>(() =>
    readInitial(LS_EMBED_MODEL_KEY, DEFAULT_EMBED_MODEL)
  )

  const setBaseUrl = useCallback((v: string) => {
    setBaseUrlState(v)
    try {
      localStorage.setItem(LS_BASE_URL_KEY, v)
    } catch (_) {}
  }, [])

  const setApiKey = useCallback((v: string) => {
    setApiKeyState(v)
    try {
      localStorage.setItem(LS_API_KEY_KEY, v)
    } catch (_) {}
  }, [])

  const setEmbeddingBaseUrl = useCallback((v: string) => {
    setEmbeddingBaseUrlState(v)
    try {
      localStorage.setItem(LS_EMBED_URL_KEY, v)
    } catch (_) {}
  }, [])

  const setEmbeddingModel = useCallback((v: string) => {
    setEmbeddingModelState(v)
    try {
      localStorage.setItem(LS_EMBED_MODEL_KEY, v)
    } catch (_) {}
  }, [])

  const resetSettings = useCallback(() => {
    setBaseUrl(DEFAULT_BASE_URL)
    setApiKey('')
    setEmbeddingBaseUrl(DEFAULT_EMBED_URL)
    setEmbeddingModel(DEFAULT_EMBED_MODEL)
  }, [setBaseUrl, setApiKey, setEmbeddingBaseUrl, setEmbeddingModel])

  return (
    <SettingsContext.Provider
      value={{
        baseUrl,
        apiKey,
        embeddingBaseUrl,
        embeddingModel,
        setBaseUrl,
        setApiKey,
        setEmbeddingBaseUrl,
        setEmbeddingModel,
        resetSettings,
      }}
    >
      {children}
    </SettingsContext.Provider>
  )
}

export const useSettings = () => {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
