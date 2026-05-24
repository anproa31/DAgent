import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSettings } from '@/context/settings-context'
import {
  createSkill,
  deleteKbDocument,
  deleteSkill,
  listKbDocuments,
  listSkills,
  updateSkill,
  uploadKbDocument,
  type SkillCreate,
  type SkillUpdate,
} from '@/services/api/memory'

const KB_KEY = ['kb-documents']
const SKILLS_KEY = ['skills']

/** Embedding overrides from Settings, threaded into every KB call. */
const useEmbeddingOpts = () => {
  const { embeddingBaseUrl, embeddingModel } = useSettings()
  return { embedding_base_url: embeddingBaseUrl, embedding_model: embeddingModel }
}

// ── Knowledge base ─────────────────────────────────────────────────────────────

export const useKbDocuments = () => {
  const opts = useEmbeddingOpts()
  return useQuery({
    queryKey: KB_KEY,
    queryFn: () => listKbDocuments(opts),
  })
}

export const useUploadKbDocument = () => {
  const qc = useQueryClient()
  const opts = useEmbeddingOpts()
  return useMutation({
    mutationFn: (file: File) => uploadKbDocument(file, opts),
    onSuccess: () => qc.invalidateQueries({ queryKey: KB_KEY }),
  })
}

export const useDeleteKbDocument = () => {
  const qc = useQueryClient()
  const opts = useEmbeddingOpts()
  return useMutation({
    mutationFn: (filename: string) => deleteKbDocument(filename, opts),
    onSuccess: () => qc.invalidateQueries({ queryKey: KB_KEY }),
  })
}

// ── Skills ───────────────────────────────────────────────────────────────────

export const useSkills = () =>
  useQuery({ queryKey: SKILLS_KEY, queryFn: listSkills })

export const useCreateSkill = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SkillCreate) => createSkill(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: SKILLS_KEY }),
  })
}

export const useUpdateSkill = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ skillId, body }: { skillId: string; body: SkillUpdate }) =>
      updateSkill(skillId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: SKILLS_KEY }),
  })
}

export const useDeleteSkill = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (skillId: string) => deleteSkill(skillId),
    onSuccess: () => qc.invalidateQueries({ queryKey: SKILLS_KEY }),
  })
}
