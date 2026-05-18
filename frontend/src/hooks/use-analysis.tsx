import axios from 'axios'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useSettings } from '@/context/settings-context'

const API_BASE_URL = import.meta.env.VITE_SERVER_URL || "http://localhost:8000"

// Parameters for starting analysis
export interface StartAnalysisParams {
  space_id: string
  query: string
  tables?: string[]
  mode?: string
  model?: string
  index?: number
}

// Response for starting analysis
export interface StartAnalysisResponse {
  id?: string
  error?: string
}

// Response for space creation
export interface CreateSpaceResponse {
  id: string
}

// Response for space retrieval
export interface GetSpaceResponse {
  analysis_ids: string[]
}

// Response for report retrieval
export interface ReportResponse {
  done: boolean
  progress: string
  query: string
  error: string
  python_code: string
  content: ReportContent[]
  steps: ActionStep[]
  followups?: FollowupContent[]
}

export interface FollowupContent {
  progress: string
  query: string
  error: string
  python_code: string
  content: ReportContent[]
  steps: ActionStep[]
}

export interface ActionStep {
  type: string
  query?: string
  python?: string
  content?: string
}

// Type definition for model info
export interface ModelInfo {
  id: string
  name: string
  description: string
}

// Response for model list retrieval
export interface ModelListResponse {
  models: ModelInfo[]
}

// Type definition for report content
export type ReportContent =
  | { type: 'markdown'; content: string }
  | { type: 'variable'; data: string }
  | { type: 'image'; base64: string }
  | { type: 'table'; table: string }

// Model list retrieval API (pass base_url, api_key as query params)
const getModelList = async (params: { base_url?: string; api_key?: string }): Promise<ModelListResponse> => {
  const response = await axios.get<ModelListResponse>(`${API_BASE_URL}/get-model-list`, {
    params: {
      base_url: params.base_url || undefined,
      api_key: params.api_key || undefined,
    },
  })
  return response.data
}

// Space creation and retrieval API
const createSpace = async (): Promise<CreateSpaceResponse> => {
  const response = await axios.post<CreateSpaceResponse>(`${API_BASE_URL}/create-space`)
  return response.data
}

const getSpace = async (id: string): Promise<GetSpaceResponse> => {
  const response = await axios.get<GetSpaceResponse>(`${API_BASE_URL}/get-space/${id}`)
  return response.data
}

// Space deletion API
const deleteSpace = async (id: string): Promise<{ success: boolean }> => {
  const response = await axios.delete<{ success: boolean }>(`${API_BASE_URL}/delete-space/${id}`)
  return response.data
}

// Analysis start API
const startAnalysis = async (params: StartAnalysisParams): Promise<StartAnalysisResponse> => {
  const response = await axios.post<StartAnalysisResponse>(`${API_BASE_URL}/start-analysis`, {
    space_id: params.space_id,
      query: params.query,
      tables: params.tables || [],
      mode: params.mode || 'standard',
      model: params.model || '',
      index: params.index,
  })
  return response.data
}

// Title generation API
const generateTitle = async (params: { query: string; model?: string }): Promise<string> => {
  try {
    const response = await axios.post<{ title: string }>(`${API_BASE_URL}/generate-title`, {
      query: params.query,
      model: params.model || '',
    })
    return response.data.title || params.query.substring(0, 50)
  } catch {
    return params.query.length > 50 ? params.query.substring(0, 50) + '...' : params.query
  }
}

// Stop analysis API
const stopAnalysis = async (id: string): Promise<{ success: boolean; error?: string }> => {
  const response = await axios.post<{ success: boolean; error?: string }>(`${API_BASE_URL}/stop-analysis`, null, {
    params: { id }
  })
  return response.data
}

// Report retrieval API
const getReport = async (id: string): Promise<ReportResponse> => {
  const response = await axios.get<ReportResponse>(`${API_BASE_URL}/get-report`, {
    params: { id }
  })
  return response.data
}

// Model list retrieval hook
export const useModelList = () => {
  const { baseUrl, apiKey } = useSettings()
  return useQuery({
    queryKey: ['modelList', baseUrl, !!apiKey],
    queryFn: () => getModelList({ base_url: baseUrl, api_key: apiKey || "" }),
    enabled: !!baseUrl, // Only when baseUrl is set
    staleTime: 50,
  })
}

// Mode-specific model list retrieval hook (unified)
export const useModelListByMode = (isAgentic: boolean) => {
  const { baseUrl, apiKey } = useSettings()
  return useQuery({
    queryKey: ['modelList', isAgentic ? 'agentic' : 'standard', baseUrl, !!apiKey],
    queryFn: () => getModelList({ base_url: baseUrl, api_key: apiKey }),
    enabled: !!baseUrl,
    staleTime: 5 * 60 * 1000,
  })
}

// Analysis start hook
export const useStartAnalysis = () => {
  return useMutation({
    mutationFn: startAnalysis,
  })
}

// Space creation hook
export const useCreateSpace = () => {
  return useMutation({
    mutationFn: createSpace,
  })
}

// Space retrieval hook
export const useGetSpace = (id: string) => {
  return useQuery({
    queryKey: ['space', id],
    queryFn: () => getSpace(id),
    enabled: !!id, // Only run if id exists
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    // refetchInterval: 2000, // Check every 2 seconds if a new analysis has been added
    // refetchIntervalInBackground: true,
  })
}

// Space deletion hook
export const useDeleteSpace = () => {
  return useMutation({
    mutationFn: deleteSpace,
  })
}

// Stop analysis hook
export const useStopAnalysis = () => {
  return useMutation({
    mutationFn: stopAnalysis,
  })
}

// Title generation hook
export const useGenerateTitle = () => {
  return useMutation({
    mutationFn: generateTitle,
  })
}

// Report retrieval hook (polling support)
export const useReport = (id: string, enabled: boolean = true) => {
  return useQuery({
    queryKey: ['report', id],
    queryFn: () => getReport(id),
    enabled: enabled && !!id,
    refetchInterval: (query) => {
      // If done is false, refetch after 1000ms
      return query.state.data?.done === false ? 1000 : false
    },
    refetchIntervalInBackground: true,
  })
}