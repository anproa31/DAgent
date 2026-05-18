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
} from '@/components/ui/kibo-ui/ai-input';
import { type FormEventHandler, useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ThemeSwitch } from '@/components/theme-switch'
import { Setting } from '@/components/setting'
import { useStartAnalysis, useModelListByMode, ModelInfo, useCreateSpace, useGenerateTitle } from '@/hooks/use-analysis'
import { useGlobalFileDrop } from '@/hooks/use-global-file-drop'
import { useSharedAnalysisHistory } from '@/context/analysis-history-context' // TODO: Replace with useContext.
import { AnimatedBeam } from "@/components/magicui/animated-beam";
import { Database, X, Loader2 } from 'lucide-react';
import { useTableList } from '@/hooks/use-table-list'
import { useUploadDatasourceFiles } from '@/hooks/use-datasources'
import { Badge } from '@/components/ui/badge'
// import { Alert, AlertDescription } from '@/components/ui/alert'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'


export default function NewAnalysis() {
  const { data: tables, isLoading, error } = useTableList()
  const navigate = useNavigate()
  const startAnalysisMutation = useStartAnalysis()
  const createSpaceMutation = useCreateSpace()
  const generateTitleMutation = useGenerateTitle()
  const uploadDatasourcesMutation = useUploadDatasourceFiles()
  const { addToHistory } = useSharedAnalysisHistory()

  const [text, setText] = useState<string>('');
  const [model, setModel] = useState<string>('');
  const [agenticMode] = useState<boolean>(false);
  const [status, setStatus] = useState<
    'submitted' | 'streaming' | 'ready' | 'error'
  >('ready');
  const [selectedTables, setSelectedTables] = useState<string[]>([]);

  const isUploading = uploadDatasourcesMutation.isPending

  const SUPPORTED_FILE_REGEX = /(\.csv|\.xlsx|\.xls|\.parquet|\.db|\.sqlite|\.sqlite3|\.duckdb)$/i

  const handleGlobalFiles = useCallback(async (droppedFiles: File[]) => {
    const valid = droppedFiles.filter(f => SUPPORTED_FILE_REGEX.test(f.name))
    const rejected = droppedFiles.filter(f => !SUPPORTED_FILE_REGEX.test(f.name))
    if (rejected.length > 0) {
      toast.error(`Unsupported files excluded: ${rejected.map(f => f.name).join(', ')}`)
    }
    if (valid.length === 0) return

    try {
      toast.message('Registering datasources', { description: `Introspecting ${valid.length} file(s)...` })
      const result = await uploadDatasourcesMutation.mutateAsync(valid)
      const newViews = result.datasources.flatMap(d => d.view_names)
      if (newViews.length > 0) {
        setSelectedTables(prev => Array.from(new Set([...prev, ...newViews])))
      }
      toast.success(result.message || `Registered ${result.datasources.length} datasource(s)`)
    } catch (e) {
      const message =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        || (e instanceof Error ? e.message : 'Error during file upload')
      toast.error(message)
    }
  }, [uploadDatasourcesMutation])

  const { isDragging } = useGlobalFileDrop(handleGlobalFiles)

  // Fetch model list depending on agentic mode
  const { data: modelData } = useModelListByMode(agenticMode)

  // Set default model when model list is loaded
  useEffect(() => {
    if (modelData?.models && modelData.models.length > 0) {
      // Check if current model exists in the new list
      const currentModelExists = modelData.models.find((m: ModelInfo) => m.id === model);
      if (!currentModelExists) {
        // If current model doesn't exist, choose the first model
        setModel(modelData.models[0].id);
      } else if (model === '') {
        // If model not chosen yet, choose the first one
        setModel(modelData.models[0].id);
      }
    }
  }, [modelData, model]);

  // Initially select all tables
  useEffect(() => {
    if (tables && tables.length > 0 && selectedTables.length === 0) {
      setSelectedTables(tables.map(t => t.name));
    }
  }, [tables]);

  const beam_containerRef = useRef<HTMLDivElement>(null);
  const beam_div1Ref = useRef<HTMLDivElement>(null);
  const beam_div2Ref = useRef<HTMLDivElement>(null);

  const handleSubmit: FormEventHandler<HTMLFormElement> = async (event) => {
    event.preventDefault();
    if (!text.trim()) {
      return;
    }

    // Validation when no tables exist
    if (!tables || tables.length === 0 || error) {
      toast.error('To start analysis, at least one table must be connected.');
      return;
    }

    if (selectedTables.length === 0) {
      toast.error('Select at least one table.');
      return;
    }

    setStatus('submitted');

    try {
      // First create a space
      const spaceResult = await createSpaceMutation.mutateAsync();
      
      if (!spaceResult.id) {
        toast.error('Failed to create space');
        setStatus('error');
        return;
      }

      // Start analysis within the created space
      const result = await startAnalysisMutation.mutateAsync({
        space_id: spaceResult.id,
        query: text.trim(),
        tables: selectedTables,
        mode: agenticMode ? 'agentic' : 'standard',
        model: model,
      });

      if (result.id) {
        // Generate an AI title; fall back to truncated query if it fails
        const aiTitle = await generateTitleMutation.mutateAsync({
          query: text.trim(),
          model,
        });

        // Add to history using the AI-generated title
        addToHistory(spaceResult.id, aiTitle);

        // Navigate to report page (using space ID) on success
        navigate({ to: `/report/${spaceResult.id}` });
      } else if (result.error) {
        // If an error message is returned
        toast.error(result.error);
        setStatus('error');
      } else {
        // Unexpected response
        toast.error('An unexpected error occurred');
        setStatus('error');
      }
    } catch (error) {
      // API error
      toast.error('Failed to start analysis');
      setStatus('error');
      // Development debug: do not log in production
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.debug('Analysis start error:', error);
      }

      // Reset status to ready after 3 seconds
      setTimeout(() => setStatus('ready'), 3000);
    }
  };

  return (
    <>
      {/* ===== Top Heading ===== */}
      <Header fixed>
        <div className='ml-auto flex items-center space-x-4'>
          <ThemeSwitch />
          <Setting />
        </div>
      </Header>

      {/* ===== Main ===== */}
      <Main className='h-full'>
        {/* Global drag overlay */}
        {isDragging && (
          <div className='fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm border-4 border-dashed border-primary pointer-events-none'>
            <p className='text-2xl font-semibold mb-2'>Drop files here</p>
            <p className='text-muted-foreground'>CSV · Excel · Parquet · SQLite · DuckDB</p>
          </div>
        )}
        {isUploading && (
          <div className='fixed bottom-4 right-4 z-50 rounded-md bg-primary/90 px-4 py-2 text-sm text-primary-foreground shadow'>Registering datasource...</div>
        )}
        <TooltipProvider>
          <div className='w-full h-[80%] flex flex-col items-center pt-[calc(50vh-270px)]'>
            <div ref={beam_containerRef} className='relative flex items-center justify-between w-3xl'>
              <div ref={beam_div1Ref} className='p-1'>
                <h1 className='text-4xl font-bold tracking-tight md:text-5xl'>
                  Data Analysis Agent
                </h1>
                <p className='text-muted-foreground text-xl'>
                  Start a new analysis with AI assistance.
                </p>
              </div>
              <div ref={beam_div2Ref} className='relative'>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className='cursor-help'>
                      <Database className='w-13 h-13' />
                      {/* Table count badge */}
                      <div className='absolute -bottom-1 -right-1'>
                        {error || tables?.length === 0 ? (
                          <Badge
                            variant="destructive"
                            className="h-6 w-6 p-0 flex items-center justify-center text-xs rounded-full bg-red-500 dark:bg-red-700 text-white"
                          >
                            <X className="w-3 h-3" />
                          </Badge>
                        ) : isLoading ? (
                          <Badge
                            variant="secondary"
                            className="h-6 w-6 p-0 flex items-center justify-center text-xs rounded-full bg-blue-500 dark:bg-blue-700 text-white"
                          >
                            <Loader2 className="w-3 h-3 animate-spin" />
                          </Badge>
                        ) : (
                          <Badge
                            variant="default"
                            className="h-6 w-6 p-0 flex items-center justify-center text-xs rounded-full bg-green-500 dark:bg-green-700 text-white"
                          >
                            {tables?.length || 0}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side='bottom'>
                    <p>
                      {error
                        ? 'Error loading database.'
                        : tables?.length === 0
                          ? 'No tables connected. Please add tables.'
                          : isLoading
                            ? 'Loading table info...'
                            : `Connected to ${tables?.length || 0} tables.`
                      }
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <AnimatedBeam
                duration={6}
                containerRef={beam_containerRef}
                fromRef={beam_div1Ref}
                toRef={beam_div2Ref}
                startXOffset={210}
                endXOffset={-30}
                gradientStartColor="#888888"
                gradientStopColor="#444444"
              />
            </div>
            <div className='w-3xl my-7'>
              <AIInput onSubmit={handleSubmit}>
                <AIInputTextarea onChange={(e) => setText(e.target.value)} value={text} />
                <AIInputToolbar>
                  <AIInputTools>
                    <AIInputModelSelect onValueChange={setModel} value={model}>
                      <AIInputModelSelectTrigger>
                        <AIInputModelSelectValue placeholder="Select a model">
                          {model && modelData?.models?.find((m: ModelInfo) => m.id === model)?.name}
                        </AIInputModelSelectValue>
                      </AIInputModelSelectTrigger>
                      <AIInputModelSelectContent className="z-50">
                        {modelData?.models?.map((modelItem: ModelInfo) => (
                          <AIInputModelSelectItem key={modelItem.id} value={modelItem.id}>
                            <div className="flex flex-col">
                              <span className="font-medium">{modelItem.name}</span>
                              <span className="text-xs text-muted-foreground">{modelItem.description}</span>
                            </div>
                          </AIInputModelSelectItem>
                        ))}
                      </AIInputModelSelectContent>
                    </AIInputModelSelect>
                  <AIInputMultiSelectTable
                      options={(tables ?? []).map((t) => ({ value: t.name, label: t.name }))}
                      selected={selectedTables}
                      onSelectedChange={setSelectedTables}
                      placeholder="Select tables"
                    />

                  </AIInputTools>
                  <AIInputSubmit disabled={!text || !model || !tables || tables.length === 0 || !!error} status={status} />
                </AIInputToolbar>


              </AIInput>
            </div>
          </div>
        </TooltipProvider>
      </Main >
    </>
  )
}