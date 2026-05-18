import React, { createContext, useContext, useState, useCallback } from 'react'

interface SettingsState {
  baseUrl: string
  apiKey: string
  setBaseUrl: (v: string) => void
  setApiKey: (v: string) => void
  resetSettings: () => void
}

const SettingsContext = createContext<SettingsState | null>(null)

const LS_BASE_URL_KEY = 'qm_settings_base_url'
const LS_API_KEY_KEY = 'qm_settings_api_key'

/** When unset in localStorage, assume local Ollama (OpenAI-compatible API). Dockerized frontends can set VITE_DEFAULT_OPENAI_BASE_URL (e.g. http://host.docker.internal:11434). */
const DEFAULT_BASE_URL: string =
  (import.meta.env.VITE_DEFAULT_OPENAI_BASE_URL as string | undefined) ||
  'http://localhost:11434'

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

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [baseUrl, setBaseUrlState] = useState<string>(readInitialBaseUrl)
  const [apiKey, setApiKeyState] = useState<string>(readInitialApiKey)

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

  const resetSettings = useCallback(() => {
    setBaseUrl(DEFAULT_BASE_URL)
    setApiKey('')
  }, [setBaseUrl, setApiKey])

  return (
    <SettingsContext.Provider value={{ baseUrl, apiKey, setBaseUrl, setApiKey, resetSettings }}>
      {children}
    </SettingsContext.Provider>
  )
}

export const useSettings = () => {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
