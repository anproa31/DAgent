import { Upload } from 'lucide-react'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FILE_ACCEPT } from '@/features/datasources/lib/constants'
import { WizardStepShell } from '@/features/datasources/components/wizard/wizard-step-shell'
import type { useFileUploadFlow } from '@/features/datasources/hooks/use-file-upload-flow'

type FileUploadFlow = ReturnType<typeof useFileUploadFlow>

interface FileUploadStepProps {
  flow: FileUploadFlow
  isProcessing: boolean
  onBack: () => void
}

export function FileUploadStep({ flow, isProcessing, onBack }: FileUploadStepProps) {
  const {
    files,
    dragActive,
    handleDrag,
    handleDrop,
    handleFileInput,
    removeFile,
    handleUpload,
  } = flow

  return (
    <WizardStepShell stepKey='files-input' className='py-4'>
      <div
        className={`rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          dragActive
            ? 'border-primary bg-primary/5'
            : 'border-muted-foreground/25'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <Upload className='text-muted-foreground mx-auto mb-3 h-12 w-12' />
        <p className='mb-1 text-lg font-medium'>Drop files here</p>
        <p className='text-muted-foreground mb-3 text-sm'>
          CSV · Excel (.xlsx/.xls) · Parquet · SQLite (.db/.sqlite) · DuckDB
        </p>
        <Input
          type='file'
          multiple
          accept={FILE_ACCEPT}
          onChange={handleFileInput}
          className='hidden'
          id='datasource-file-upload'
        />
        <Label
          htmlFor='datasource-file-upload'
          className={buttonVariants({
            variant: 'outline',
            className: 'cursor-pointer bg-transparent',
          })}
        >
          Choose files
        </Label>
      </div>

      {files.length > 0 && (
        <div className='mt-4'>
          <h4 className='mb-2 font-medium'>Selected files</h4>
          <div className='space-y-2'>
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className='bg-muted flex items-center justify-between rounded p-2'
              >
                <span className='truncate text-sm'>{file.name}</span>
                <Button
                  variant='ghost'
                  size='sm'
                  onClick={() => removeFile(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className='mt-6 flex justify-between'>
        <Button variant='outline' onClick={onBack}>
          Back
        </Button>
        <Button
          onClick={handleUpload}
          disabled={files.length === 0 || isProcessing}
        >
          {isProcessing
            ? 'Registering...'
            : `Register ${files.length || ''} file${files.length === 1 ? '' : 's'}`.trim()}
        </Button>
      </div>
    </WizardStepShell>
  )
}
