import type { RunReport } from '@/services/api/agent'
import type { AgentRun, RunPhase } from '@/stores/agentStore'

export function mapReportToAgentRun(
  runId: string,
  sessionId: string,
  report: RunReport
): AgentRun {
  let phase: RunPhase = 'running'
  if (report.done) {
    phase = report.error ? 'error' : 'done'
  } else if (report.pending_approval) {
    phase = 'awaiting_approval'
  }
  return {
    runId,
    sessionId,
    query: report.query,
    phase,
    currentAgent: report.current_agent || '',
    agentSteps: report.agent_steps ?? [],
    thinkingMessage: '',
    approvalKind: null,
    pendingSql: report.sql_draft ?? '',
    pendingSqlExplanation: report.sql_explanation ?? '',
    pendingWebProposal: null,
    pendingPythonCode: '',
    pendingPythonRisk: '',
    streamingAnswer: '',
    thinkingSegments: report.thinking_segments ?? [],
    executions: report.executions ?? [],
    content: report.content ?? [],
    insights: report.insights ?? '',
    error: report.error ?? '',
  }
}
