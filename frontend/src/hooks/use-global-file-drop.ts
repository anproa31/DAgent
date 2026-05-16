import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Hook for detecting global (full-screen) file drag & drop.
 * - Counts dragenter/leave events to correctly control overlay display
 * - Reliably removes event listeners on page leave or unmount
 */
export function useGlobalFileDrop(onFiles: (files: File[]) => void) {
  const dragCounter = useRef(0)
  const [isDragging, setIsDragging] = useState(false)

  const handleDragEnter = useCallback((e: DragEvent) => {
    if (!e.dataTransfer) return
    // Ignore drags that do not contain files (e.g. text selection)
    if (!Array.from(e.dataTransfer.types).includes('Files')) return
    e.preventDefault()
    dragCounter.current += 1
    setIsDragging(true)
  }, [])

  const handleDragOver = useCallback((e: DragEvent) => {
    if (!e.dataTransfer) return
    if (!Array.from(e.dataTransfer.types).includes('Files')) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    if (!e.dataTransfer) return
    if (!Array.from(e.dataTransfer.types).includes('Files')) return
    e.preventDefault()
    dragCounter.current -= 1
    if (dragCounter.current <= 0) {
      setIsDragging(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: DragEvent) => {
      if (!e.dataTransfer) return
      if (!Array.from(e.dataTransfer.types).includes('Files')) return
      e.preventDefault()
      e.stopPropagation()
      dragCounter.current = 0
      setIsDragging(false)
      const fileList = e.dataTransfer.files
      if (fileList && fileList.length > 0) {
        onFiles(Array.from(fileList))
      }
    },
    [onFiles]
  )

  useEffect(() => {
    window.addEventListener('dragenter', handleDragEnter)
    window.addEventListener('dragover', handleDragOver)
    window.addEventListener('dragleave', handleDragLeave)
    window.addEventListener('drop', handleDrop)
    return () => {
      window.removeEventListener('dragenter', handleDragEnter)
      window.removeEventListener('dragover', handleDragOver)
      window.removeEventListener('dragleave', handleDragLeave)
      window.removeEventListener('drop', handleDrop)
    }
  }, [handleDragEnter, handleDragLeave, handleDragOver, handleDrop])

  return { isDragging }
}
