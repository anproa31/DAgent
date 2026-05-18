import { Download, X, Copy } from 'lucide-react'
import { toast } from 'sonner'
import * as XLSX from 'xlsx'
import { type ActionStep } from '@/hooks/use-analysis'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AIResponse } from '@/components/ui/kibo-ui/response'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface SidePanelProps {
  type: 'code' | 'table' | 'step'
  content: string
  stepData?: ActionStep
  onClose: () => void
  inSplitView?: boolean
}

export function SidePanel({
  type,
  content,
  stepData,
  onClose,
}: SidePanelProps) {
  // Split view mode: render directly without using Sheet
  if (type === 'code') {
    return <CodePanelContent content={content} onClose={onClose} />
  }

  if (type === 'table') {
    return <TablePanelContent content={content} onClose={onClose} />
  }

  if (type === 'step' && stepData) {
    return <StepPanelContent stepData={stepData} onClose={onClose} />
  }

  return null
}

// Code panel for split view
function CodePanelContent({
  content,
  onClose,
}: {
  content: string
  onClose: () => void
}) {
  const downloadCode = () => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `analysis_code_${Date.now()}.py`
    link.click()
    URL.revokeObjectURL(url)
  }

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(content)
    } catch (error) {
    }
  }

  return (
    <Card className='h-full rounded-none border-0 border-l'>
      <CardHeader className='pb-3'>
        <CardTitle className='flex items-center justify-between text-base'>
          <span>Python Code</span>
          <div className='flex items-center gap-2'>
            <Button onClick={copyCode} variant='outline' size='sm'>
              <Copy className='mr-2 h-4 w-4' />
              Copy
            </Button>
            <Button onClick={downloadCode} variant='outline' size='sm'>
              <Download className='mr-2 h-4 w-4' />
              Download
            </Button>
            <Button onClick={onClose} variant='ghost' size='sm'>
              <X className='h-4 w-4' />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className='h-[calc(100%-80px)] pt-0'>
        <ScrollArea className='h-full'>
          <pre className='bg-muted overflow-x-auto rounded-lg p-4 font-mono text-sm whitespace-pre-wrap'>
            <code>{content}</code>
          </pre>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

// Table panel for split view
function TablePanelContent({
  content,
  onClose,
}: {
  content: string
  onClose: () => void
}) {
  // Parse table data in CSV or JSON format
  let headers: string[] = []
  let dataRows: string[][] = []

  try {
    // JSON format (per API spec)
    const jsonData = JSON.parse(content) as any[]
    if (jsonData.length > 0) {
      headers = Object.keys(jsonData[0])
      dataRows = jsonData.map((row) =>
        headers.map((header) => String(row[header] || ''))
      )
    }
  } catch {
    // CSV format (fallback)
    const rows = content
      .trim()
      .split('\n')
      .map((row) => row.split(','))
    headers = rows[0] || []
    dataRows = rows.slice(1)
  }

  const downloadCSV = () => {
    let csvContent: string
    if (headers.length > 0) {
      csvContent = [
        headers.join(','),
        ...dataRows.map((row) => row.join(',')),
      ].join('\n')
    } else {
      csvContent = content
    }

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `analysis_table_${Date.now()}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const dowmloadTSV = () => {
    let tsvContent: string
    if (headers.length > 0) {
      tsvContent = [
        headers.join('\t'),
        ...dataRows.map((row) => row.join('\t')),
      ].join('\n')
    } else {
      tsvContent = content
    }

    const blob = new Blob([tsvContent], { type: 'text/tab-separated-values' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `analysis_table_${Date.now()}.tsv`
    link.click()
    URL.revokeObjectURL(url)
  }
  const convertToXLSX = (jsonData: any[]) => {
    if (jsonData.length === 0) return

    const workbook = XLSX.utils.book_new()
    const worksheet = XLSX.utils.json_to_sheet(jsonData)
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Sheet1')

    return workbook
  }

  const downloadXLSX = () => {
    const workbook = convertToXLSX(
      dataRows.map((row) => {
        const rowData: Record<string, string> = {}
        headers.forEach((header, i) => {
          rowData[header] = row[i] || ''
        })
        return rowData
      })
    )
    if (workbook) {
      XLSX.writeFile(workbook, `table_${Date.now()}.xlsx`)
    }
  }

  const copyCSV = async () => {
    try {
      let csvContent: string
      if (headers.length > 0) {
        csvContent = [
          headers.join(','),
          ...dataRows.map((row) => row.join(',')),
        ].join('\n')
      } else {
        csvContent = content
      }
      await navigator.clipboard.writeText(csvContent)
    } catch (error) {
      toast.error('Failed to copy to clipboard')
    }
  }

  return (
    <div className='flex h-full min-h-0 w-full min-w-0 flex-col bg-background'>
      {/* Header row: title + close */}
      <div className='flex shrink-0 items-center justify-between gap-3 border-b bg-muted/50 px-4 py-3'>
        <span className='min-w-0 truncate text-sm font-semibold text-foreground'>
          Table ({dataRows.length} rows &times; {headers.length} columns)
        </span>
        <Button
          onClick={onClose}
          variant='outline'
          size='sm'
          className='h-8 shrink-0 gap-1.5'
        >
          <X className='h-4 w-4' />
          Close
        </Button>
      </div>

      {/* Export actions row */}
      <div className='flex shrink-0 flex-wrap items-center gap-x-1 gap-y-1 border-b px-4 py-2'>
        <Button onClick={downloadCSV} variant='link' size='sm' className='h-8'>
          <Download className='mr-1.5 h-4 w-4' />
          CSV
        </Button>
        <Button onClick={downloadXLSX} variant='link' size='sm' className='h-8'>
          <Download className='mr-1.5 h-4 w-4' />
          XLSX
        </Button>
        <Button onClick={dowmloadTSV} variant='link' size='sm' className='h-8'>
          <Download className='mr-1.5 h-4 w-4' />
          TSV
        </Button>
        <Button onClick={copyCSV} variant='link' size='sm' className='h-8'>
          <Copy className='mr-1.5 h-4 w-4' />
          Copy
        </Button>
      </div>

      {/* Scrollable table area */}
      <div className='min-h-0 flex-1 overflow-auto'>
        <Table className='w-max min-w-full'>
          <TableHeader>
            <TableRow>
              {headers.map((header, index) => (
                <TableHead
                  key={index}
                  className='sticky top-0 z-10 whitespace-nowrap bg-muted/80 backdrop-blur-sm'
                >
                  {header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {dataRows.map((row, rowIndex) => (
              <TableRow key={rowIndex}>
                {row.map((cell, cellIndex) => (
                  <TableCell key={cellIndex} className='whitespace-nowrap'>
                    {cell}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

// Step panel for split view
function StepPanelContent({
  stepData,
  onClose,
}: {
  stepData: ActionStep
  onClose: () => void
}) {
  const downloadCode = () => {
    if (stepData.python) {
      const blob = new Blob([stepData.python], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `step_code_${Date.now()}.py`
      link.click()
      URL.revokeObjectURL(url)
    }
  }

  const copyCode = async () => {
    if (stepData.python) {
      try {
        await navigator.clipboard.writeText(stepData.python)
        toast.success('Code copied to clipboard')
      } catch (error) {
        toast.error('Failed to copy to clipboard')
      }
    }
  }

  return (
    <Card className='h-full rounded-none border-0 border-l'>
      <CardHeader className='pb-3'>
        <CardTitle className='flex items-center justify-between text-base'>
          <div className='flex flex-col gap-2'>
            <span>Analysis Steps</span>
          </div>
          <div className='flex items-center gap-2'>
            {stepData.python && (
              <>
                <Button onClick={copyCode} variant='outline' size='sm'>
                  <Copy className='mr-2 h-4 w-4' />
                  Copy
                </Button>
                <Button onClick={downloadCode} variant='outline' size='sm'>
                  <Download className='mr-2 h-4 w-4' />
                  Download
                </Button>
              </>
            )}
            <Button onClick={onClose} variant='ghost' size='sm'>
              <X className='h-4 w-4' />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className='h-[calc(100%-80px)] pt-0'>
        <ScrollArea className='h-full w-full'>
          <p className='py-3 text-lg text-wrap'>{stepData.query}</p>
          <div className='space-y-4'>
            {/* Python Code Section */}
            {stepData.python && (
              <div>
                <h3 className='text-muted-foreground mb-2 text-sm font-medium'>
                  Executed Python Code
                </h3>
                <pre className='bg-muted overflow-x-auto rounded-lg p-4 font-mono text-sm whitespace-pre-wrap'>
                  <code>{stepData.python}</code>
                </pre>
              </div>
            )}

            {/* Content Section */}
            {stepData.content && (
              <div>
                <h3 className='text-muted-foreground mb-2 text-sm font-medium'>
                  Step Results
                </h3>
                <div className='prose prose-sm max-w-none'>
                  <AIResponse>{stepData.content}</AIResponse>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
