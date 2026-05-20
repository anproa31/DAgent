import type React from 'react'
import { useState, useCallback } from 'react'
import { toast } from 'sonner'
import { parseDatasourceError } from '@/features/datasources/lib/parse-datasource-error'
import type { DatasourceRecord } from '@/services/api/datasources'
import { useUploadDatasourceFiles } from '@/hooks/use-datasources'

interface UseFileUploadFlowOptions {
  startProgress: () => () => void
  onSuccess: (records: DatasourceRecord[]) => void
  onError: (message: string, details: string) => void
}

export function useFileUploadFlow({
  startProgress,
  onSuccess,
  onError,
}: UseFileUploadFlowOptions) {
  const uploadMutation = useUploadDatasourceFiles()
  const [files, setFiles] = useState<File[]>([])
  const [dragActive, setDragActive] = useState(false)

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files?.[0]) {
      setFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)])
    }
  }, [])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)])
    }
  }

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const resetFiles = () => setFiles([])

  const handleUpload = async () => {
    if (files.length === 0) return
    const stop = startProgress()
    try {
      const result = await uploadMutation.mutateAsync(files)
      stop()
      onSuccess(result.datasources)
      toast.success(result.message || 'Files uploaded')
    } catch (error) {
      stop()
      const { message, details } = parseDatasourceError(error, 'Upload failed')
      onError(message, details)
    }
  }

  return {
    files,
    dragActive,
    handleDrag,
    handleDrop,
    handleFileInput,
    removeFile,
    resetFiles,
    handleUpload,
    isUploading: uploadMutation.isPending,
  }
}
