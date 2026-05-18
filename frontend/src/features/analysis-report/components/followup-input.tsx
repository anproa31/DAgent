import {
    AIInput,
    AIInputModelSelect,
    AIInputModelSelectContent,
    AIInputModelSelectItem,
    AIInputModelSelectTrigger,
    AIInputModelSelectValue,
    AIInputSubmit,
    AIInputTextarea,
    AIInputToolbar,
    AIInputTools,
    AIInputMultiSelectTable
} from '@/components/ui/kibo-ui/ai-input'
import { Button } from '@/components/ui/button'
import { SquareIcon } from 'lucide-react'
import { type FormEventHandler } from 'react'
import type { ModelInfo } from '@/hooks/use-analysis'

// Presentation-only component
export interface FollowupInputProps {
    text: string
    onTextChange: (text: string) => void
    model: string
    onModelChange: (model: string) => void
    models: ModelInfo[]
    selectedTables: string[]
    onSelectedTablesChange: (tables: string[]) => void
    tables: { name: string }[] | undefined
    tablesError?: unknown
    status: 'submitted' | 'streaming' | 'ready' | 'error'
    isprocessing?: boolean
    onSubmit: (data: { text: string }) => void
    onStop?: () => void
}

export default function FollowupInput({
    text,
    onTextChange,
    model,
    onModelChange,
    models,
    selectedTables,
    onSelectedTablesChange,
    tables,
    tablesError,
    status,
    isprocessing,
    onSubmit,
    onStop,
}: FollowupInputProps) {
    const handleSubmit: FormEventHandler<HTMLFormElement> = (e) => {
        e.preventDefault()
        if (isprocessing) return
        if (!text.trim()) return
        onSubmit({ text: text.trim() })
    }

    const disabled = !text || !model || !tables || tables.length === 0 || !!tablesError || isprocessing

    return (
        <div className='sticky bottom-5 w-full flex justify-center px-4'>
            <div className='w-full max-w-3xl'>
                <AIInput onSubmit={handleSubmit} className='shadow-lg dark:shadow-accent-foreground/10 inset-ring-gray-50 border border-border'>
                    <AIInputTextarea
                        placeholder='Ask more ...'
                        onChange={(e) => onTextChange(e.target.value)}
                        value={text}
                    />
                    <AIInputToolbar>
                        <AIInputTools>
                            <AIInputModelSelect onValueChange={onModelChange} value={model}>
                                <AIInputModelSelectTrigger>
                                    <AIInputModelSelectValue placeholder='Select Model'>
                                        {model && models?.find((m) => m.id === model)?.name}
                                    </AIInputModelSelectValue>
                                </AIInputModelSelectTrigger>
                                <AIInputModelSelectContent className='z-50'>
                                    {models?.map((m) => (
                                        <AIInputModelSelectItem key={m.id} value={m.id}>
                                            <div className='flex flex-col'>
                                                <span className='font-medium'>{m.name}</span>
                                                <span className='text-xs text-muted-foreground'>{m.description}</span>
                                            </div>
                                        </AIInputModelSelectItem>
                                    ))}
                                </AIInputModelSelectContent>
                            </AIInputModelSelect>
                            <AIInputMultiSelectTable
                                options={(tables ?? []).map((t) => ({ value: t.name, label: t.name }))}
                                selected={selectedTables}
                                onSelectedChange={onSelectedTablesChange}
                                placeholder='Select Tables'
                            />
                        </AIInputTools>
                        {isprocessing ? (
                            <Button
                                type='button'
                                size='icon'
                                variant='default'
                                onClick={onStop}
                                className='gap-1.5 rounded-lg rounded-br-xl'
                                aria-label='Stop generation'
                            >
                                <SquareIcon className='h-4 w-4 fill-current' />
                            </Button>
                        ) : (
                            <AIInputSubmit disabled={disabled} status={status} />
                        )}
                    </AIInputToolbar>
                </AIInput>
            </div>
        </div>
    )
}
