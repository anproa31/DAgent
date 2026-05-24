import { agentClient } from '@/services/api/client'

// ── Types ────────────────────────────────────────────────────────────────────

export interface KbUploadResponse {
  status: string
  filename: string
  chunks_stored: number
  total_chars: number
}

export interface Skill {
  skill_id: string
  name: string
  description: string
  template: string
  type: string
  is_default: boolean
  created_at?: string
}

export interface SkillCreate {
  name: string
  description: string
  template: string
  skill_type: string
}

export interface SkillUpdate {
  name: string
  description: string
  template: string
}

/** Embedding endpoint override sent with KB calls (from Settings). */
export interface EmbeddingOpts {
  embedding_base_url?: string
  embedding_model?: string
}

// ── Knowledge base ─────────────────────────────────────────────────────────────

export const listKbDocuments = async (opts: EmbeddingOpts = {}): Promise<string[]> => {
  const res = await agentClient.get<{ documents: string[] }>('/agent/kb/documents', {
    params: {
      embedding_base_url: opts.embedding_base_url || undefined,
      embedding_model: opts.embedding_model || undefined,
    },
  })
  return res.data.documents
}

export const uploadKbDocument = async (
  file: File,
  opts: EmbeddingOpts = {}
): Promise<KbUploadResponse> => {
  const form = new FormData()
  form.append('file', file)
  const res = await agentClient.post<KbUploadResponse>('/agent/kb/upload', form, {
    params: {
      embedding_base_url: opts.embedding_base_url || undefined,
      embedding_model: opts.embedding_model || undefined,
    },
  })
  return res.data
}

export const deleteKbDocument = async (
  filename: string,
  opts: EmbeddingOpts = {}
): Promise<void> => {
  await agentClient.delete(`/agent/kb/documents/${encodeURIComponent(filename)}`, {
    params: {
      embedding_base_url: opts.embedding_base_url || undefined,
      embedding_model: opts.embedding_model || undefined,
    },
  })
}

// ── Skills (procedural memory) ──────────────────────────────────────────────────

export const listSkills = async (): Promise<Skill[]> => {
  const res = await agentClient.get<{ skills: Skill[] }>('/agent/skills/')
  return res.data.skills
}

export const createSkill = async (body: SkillCreate): Promise<{ skill_id: string }> => {
  const res = await agentClient.post<{ skill_id: string }>('/agent/skills/', body)
  return res.data
}

export const updateSkill = async (skillId: string, body: SkillUpdate): Promise<void> => {
  await agentClient.put(`/agent/skills/${skillId}`, body)
}

export const deleteSkill = async (skillId: string): Promise<void> => {
  await agentClient.delete(`/agent/skills/${skillId}`)
}
