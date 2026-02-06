import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Play,
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  Server,
  GitBranch,
  Database,
  Shield,
  Terminal,
  FileCode,
  Wrench,
  Brain,
  ExternalLink,
  RefreshCw,
  XCircle,
  User,
} from 'lucide-react'

// Types
interface SystemStatus {
  github_cli: boolean
  github_user: string | null
  mcp_security: boolean
  mcp_change_mgmt: boolean
  vector_store: boolean
}

interface Repo {
  url: string
  name: string
  status: 'pending' | 'running' | 'complete' | 'error'
  currentStep?: string
  prUrl?: string
}

interface ChecklistItem {
  label: string
  status: 'pending' | 'running' | 'complete'
}

interface ToolCall {
  tool: string
  args: Record<string, unknown>
  repo?: string
  timestamp: string
  status: 'running' | 'complete'
  callNumber?: number
}

interface LogEntry {
  timestamp: string
  message: string
  level: 'info' | 'success' | 'warning' | 'error'
  repo?: string
}

interface WSEvent {
  type: string
  timestamp: string
  data: Record<string, unknown>
}

// Status indicator component
function StatusIndicator({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      {ok ? (
        <CheckCircle2 className="w-4 h-4 text-green-500" />
      ) : (
        <AlertCircle className="w-4 h-4 text-red-500" />
      )}
      <span className={ok ? 'text-green-400' : 'text-red-400'}>{label}</span>
    </div>
  )
}

// Checklist component for a single repo
function RepoChecklist({
  checklist,
}: {
  checklist: Record<string, ChecklistItem>
  repoName?: string
}) {
  return (
    <div className="space-y-1">
      {Object.entries(checklist).map(([key, item]) => (
        <div key={key} className="flex items-center gap-2 text-sm">
          {item.status === 'complete' ? (
            <CheckCircle2 className="w-4 h-4 text-green-500" />
          ) : item.status === 'running' ? (
            <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
          ) : (
            <Circle className="w-4 h-4 text-gray-600" />
          )}
          <span
            className={
              item.status === 'complete'
                ? 'text-green-400'
                : item.status === 'running'
                ? 'text-blue-400'
                : 'text-gray-500'
            }
          >
            {item.label}
          </span>
        </div>
      ))}
    </div>
  )
}

// Tool call display
function ToolCallDisplay({ toolCall }: { toolCall: ToolCall }) {
  const getToolIcon = (tool: string) => {
    switch (tool) {
      case 'rag_search':
        return <Database className="w-4 h-4" />
      case 'clone_repository':
        return <GitBranch className="w-4 h-4" />
      case 'detect_compliance_drift':
      case 'apply_compliance_patches':
        return <FileCode className="w-4 h-4" />
      case 'security_scan':
        return <Shield className="w-4 h-4" />
      default:
        return <Wrench className="w-4 h-4" />
    }
  }

  return (
    <div className="flex items-start gap-2 py-2 border-b border-gray-800 last:border-0">
      <div
        className={`p-1 rounded ${
          toolCall.status === 'running' ? 'bg-blue-900' : 'bg-green-900'
        }`}
      >
        {getToolIcon(toolCall.tool)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-white">{toolCall.tool}</span>
          {toolCall.status === 'running' && (
            <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
          )}
        </div>
        <div className="text-xs text-gray-500 truncate">
          {JSON.stringify(toolCall.args).substring(0, 80)}...
        </div>
      </div>
    </div>
  )
}

// Main App component
export default function App() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [repos, setRepos] = useState<Repo[]>([])
  const [selectedRepo, setSelectedRepo] = useState<string>('')
  const [isRunning, setIsRunning] = useState(false)
  const [agentMessages, setAgentMessages] = useState<string[]>([])
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [activeRepo, setActiveRepo] = useState<string | null>(null)
  const [repoChecklists, setRepoChecklists] = useState<
    Record<string, Record<string, ChecklistItem>>
  >({})
  const [prsCreated, setPrsCreated] = useState<string[]>([])
  const [isInitializing, setIsInitializing] = useState(true)
  const [initStatus, setInitStatus] = useState('Connecting to backend...')

  const wsRef = useRef<WebSocket | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // Refs to avoid stale closures in WebSocket handler
  const activeRepoRef = useRef(activeRepo)
  const reposRef = useRef(repos)
  
  useEffect(() => {
    activeRepoRef.current = activeRepo
  }, [activeRepo])
  
  useEffect(() => {
    reposRef.current = repos
  }, [repos])

  // Initialize default checklist for a repo
  const getDefaultChecklist = (): Record<string, ChecklistItem> => ({
    rag_search: { label: 'Policy Knowledge Search', status: 'pending' },
    clone: { label: 'Clone Repository', status: 'pending' },
    detect_drift: { label: 'Detect Compliance Drift', status: 'pending' },
    security_scan: { label: 'Security Vulnerability Scan', status: 'pending' },
    apply_patches: { label: 'Apply Compliance Patches', status: 'pending' },
    run_tests: { label: 'Run Tests', status: 'pending' },
    create_pr: { label: 'Create Pull Request', status: 'pending' },
  })

  // Fetch initial data
  useEffect(() => {
    let statusLoaded = false
    let reposLoaded = false
    
    const checkInitComplete = () => {
      if (statusLoaded && reposLoaded) {
        setInitStatus('Ready!')
        setTimeout(() => setIsInitializing(false), 500)
      }
    }
    
    setInitStatus('Checking system status...')
    fetch('/api/status')
      .then((res) => res.json())
      .then((data) => {
        setStatus(data)
        statusLoaded = true
        setInitStatus('Loading repositories...')
        checkInitComplete()
      })
      .catch((err) => {
        console.error(err)
        setInitStatus('Failed to connect to backend. Is the server running?')
      })

    fetch('/api/repos')
      .then((res) => res.json())
      .then((data) => {
        setRepos(data)
        // Select first repo by default
        if (data.length > 0) {
          setSelectedRepo(data[0].name)
        }
        // Initialize checklists for each repo
        const checklists: Record<string, Record<string, ChecklistItem>> = {}
        data.forEach((repo: Repo) => {
          checklists[repo.name] = getDefaultChecklist()
        })
        setRepoChecklists(checklists)
        reposLoaded = true
        checkInitComplete()
      })
      .catch(console.error)
  }, [])

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [agentMessages])

  // WebSocket message handler
  const handleWSMessage = useCallback((event: MessageEvent) => {
    const data: WSEvent = JSON.parse(event.data)
    console.log('[UI] Received WS message type:', JSON.stringify(data.type), 'data:', data.data)
    const timestamp = new Date(data.timestamp).toLocaleTimeString()

    // Normalize type - remove any trailing whitespace
    const eventType = String(data.type).trim()
    console.log('[UI] Normalized type:', JSON.stringify(eventType))

    switch (eventType) {
      case 'system_status':
        console.log('[UI] Setting status')
        setStatus(data.data as unknown as SystemStatus)
        break

      case 'agent_start':
        console.log('[UI] Agent start!')
        setIsRunning(true)
        setLogs((prev) => [
          ...prev,
          { timestamp, message: 'Agent started', level: 'info' },
        ])
        break

      case 'agent_complete':
        console.log('[UI] Agent complete, prs_created:', data.data.prs_created)
        setIsRunning(false)
        setPrsCreated(data.data.prs_created as string[])
        setLogs((prev) => [
          ...prev,
          {
            timestamp,
            message: `Agent complete: ${data.data.tool_calls} tool calls, ${(data.data.prs_created as string[]).length} PRs`,
            level: 'success',
          },
        ])
        break

      case 'tool_call_start':
        console.log('[UI] Adding tool call:', data.data.tool, 'call #', data.data.call_number)
        setToolCalls((prev) => {
          const newCalls = [
            ...prev,
            {
              tool: data.data.tool as string,
              args: data.data.args as Record<string, unknown>,
              repo: data.data.repo as string,
              timestamp,
              status: 'running' as const,
              callNumber: data.data.call_number as number,
            },
          ]
          console.log('[UI] toolCalls now:', newCalls.length)
          return newCalls
        })
        break

      case 'tool_call_complete':
        console.log('[UI] Tool complete:', data.data.tool, 'call #', data.data.call_number)
        setToolCalls((prev) =>
          prev.map((tc) => {
            // Match by call_number if available, otherwise by tool name
            const matches = data.data.call_number
              ? tc.callNumber === data.data.call_number
              : tc.tool === data.data.tool && tc.status === 'running'
            return matches ? { ...tc, status: 'complete' as const } : tc
          })
        )
        break

      case 'checklist_update':
        console.log('[UI] Checklist update:', data.data)
        if (data.data.checklist) {
          // Use repo from event if available, otherwise fall back
          const repo = (data.data.repo as string) || activeRepoRef.current || reposRef.current[0]?.name
          if (repo) {
            console.log('[UI] Updating checklist for repo:', repo)
            setRepoChecklists((prev) => ({
              ...prev,
              [repo]: data.data.checklist as Record<string, ChecklistItem>,
            }))
          }
        }
        break

      case 'repo_start':
        console.log('[UI] Repo start:', data.data.repo)
        setActiveRepo(data.data.repo as string)
        setRepos((prev) =>
          prev.map((r) =>
            r.name === data.data.repo ? { ...r, status: 'running' } : r
          )
        )
        // Reset checklist for this repo
        setRepoChecklists((prev) => ({
          ...prev,
          [data.data.repo as string]: getDefaultChecklist(),
        }))
        break

      case 'repo_complete':
        console.log('[UI] Repo complete:', data.data.repo)
        setRepos((prev) =>
          prev.map((r) =>
            r.name === data.data.repo ? { ...r, status: 'complete' } : r
          )
        )
        break

      case 'pr_created':
        console.log('[UI] PR created:', data.data.pr_url)
        {
          const prUrl = data.data.pr_url as string
          if (prUrl) {
            setPrsCreated((prev) => prev.includes(prUrl) ? prev : [...prev, prUrl])
          }
        }
        break

      case 'agent_message':
        console.log('[UI] Agent message:', (data.data.content as string).substring(0, 50))
        setAgentMessages((prev) => {
          const newMsgs = [...prev, data.data.content as string]
          console.log('[UI] agentMessages now:', newMsgs.length)
          return newMsgs
        })
        break

      case 'console_log':
        console.log('[UI] Console log:', data.data.message)
        setLogs((prev) => {
          const newLogs = [
            ...prev,
            {
              timestamp,
              message: data.data.message as string,
              level: data.data.level as LogEntry['level'],
              repo: data.data.repo as string,
            },
          ]
          console.log('[UI] logs now:', newLogs.length)
          return newLogs
        })
        break

      case 'error':
        setLogs((prev) => [
          ...prev,
          {
            timestamp,
            message: `Error: ${data.data.message}`,
            level: 'error',
          },
        ])
        break
        
      default:
        console.log('[UI] UNHANDLED event type:', JSON.stringify(eventType))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Connect WebSocket
  const reconnectTimeoutRef = useRef<number | null>(null)
  const isClosingRef = useRef(false)
  
  const connectWS = useCallback(() => {
    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    // Close existing connection
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('[WS] Already connected')
      return
    }
    
    console.log('[WS] Connecting...')
    const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/agent`)
    
    ws.onopen = () => {
      console.log('[WS] Connected!')
      isClosingRef.current = false
      ws.send(JSON.stringify({ action: 'status' }))
    }
    
    ws.onmessage = handleWSMessage
    
    ws.onerror = (err) => {
      console.error('[WS] Error:', err)
    }
    
    ws.onclose = () => {
      console.log('[WS] Disconnected')
      if (!isClosingRef.current) {
        console.log('[WS] Will reconnect in 2s...')
        reconnectTimeoutRef.current = window.setTimeout(connectWS, 2000)
      }
    }
    
    wsRef.current = ws
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    connectWS()
    return () => {
      isClosingRef.current = true
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      wsRef.current?.close()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Start agent
  const startAgent = () => {
    console.log('[UI] startAgent called')
    console.log('[UI] WebSocket readyState:', wsRef.current?.readyState, 'OPEN is', WebSocket.OPEN)
    console.log('[UI] selectedRepo:', selectedRepo)
    console.log('[UI] isRunning:', isRunning)
    console.log('[UI] allSystemsReady:', allSystemsReady)
    
    if (!wsRef.current) {
      console.error('[UI] No WebSocket reference!')
      return
    }
    
    if (wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[UI] WebSocket NOT open, state:', wsRef.current.readyState)
      alert('WebSocket not connected. Please refresh the page.')
      return
    }
    
    if (!selectedRepo) {
      console.error('[UI] No repo selected!')
      alert('Please select a repository.')
      return
    }
    
    // Find the selected repo
    const repo = repos.find((r) => r.name === selectedRepo)
    if (!repo) {
      console.error('[UI] Selected repo not found!')
      alert('Selected repository not found.')
      return
    }
    
    console.log('[UI] All checks passed, sending start command for:', repo.name)
    
    // Reset state
    setToolCalls([])
    setAgentMessages([])
    setLogs([])
    setPrsCreated([])
    setActiveRepo(selectedRepo)
    
    // Reset checklist for selected repo only
    setRepoChecklists((prev) => ({
      ...prev,
      [selectedRepo]: getDefaultChecklist(),
    }))

    // Send start command with only the selected repo
    const payload = {
      action: 'start',
      repos: [repo.url],
    }
    console.log('[UI] Sending payload:', JSON.stringify(payload))
    
    try {
      wsRef.current.send(JSON.stringify(payload))
      console.log('[UI] Payload sent successfully!')
      setIsRunning(true)
    } catch (err) {
      console.error('[UI] Error sending:', err)
      alert('Failed to send command: ' + err)
    }
  }

  const refreshStatus = () => {
    fetch('/api/status')
      .then((res) => res.json())
      .then(setStatus)
      .catch(console.error)
  }

  const allSystemsReady =
    status?.github_cli &&
    status?.mcp_security &&
    status?.mcp_change_mgmt &&
    status?.vector_store

  return (
    <div className="h-screen bg-github-900 text-gray-200 flex flex-col overflow-hidden">
      {/* Initialization Overlay */}
      {isInitializing && (
        <div className="fixed inset-0 bg-github-900/95 z-50 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-copilot-600 border-t-transparent mx-auto mb-4"></div>
            <h2 className="text-xl font-bold text-white mb-2">Initializing Fleet Compliance Agent</h2>
            <p className="text-gray-400">{initStatus}</p>
          </div>
        </div>
      )}
      
      {/* Header */}
      <header className="bg-github-800 border-b border-gray-700 px-6 py-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-copilot-600 rounded-lg">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">
                Fleet Compliance Agent
              </h1>
              <p className="text-sm text-gray-400">
                Powered by GitHub Copilot SDK
              </p>
            </div>
          </div>

          {/* System Status */}
          <div className="flex items-center gap-6">
            {/* GitHub User */}
            {status?.github_user && (
              <div className="flex items-center gap-2 px-3 py-1 bg-github-700 rounded-lg">
                <User className="w-4 h-4 text-copilot-400" />
                <span className="text-sm text-gray-300">{status.github_user}</span>
              </div>
            )}
            <div className="flex items-center gap-4 text-sm">
              <StatusIndicator
                ok={status?.github_cli ?? false}
                label="GitHub CLI"
              />
              <StatusIndicator
                ok={status?.mcp_security ?? false}
                label="MCP Security"
              />
              <StatusIndicator
                ok={status?.mcp_change_mgmt ?? false}
                label="MCP Change Mgmt"
              />
              <StatusIndicator
                ok={status?.vector_store ?? false}
                label="Vector Store"
              />
            </div>
            <button
              onClick={refreshStatus}
              className="p-2 hover:bg-gray-700 rounded"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 overflow-hidden">
        <div className="grid grid-cols-12 gap-6 h-full">
          {/* Left Panel - Control, Checklist & Tool Calls */}
          <div className="col-span-3 flex flex-col gap-4 overflow-hidden">
            {/* Control Panel */}
            <div className="bg-github-800 rounded-lg p-4 border border-gray-700">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Server className="w-5 h-5 text-copilot-500" />
                Fleet Audit
              </h2>

              {/* Repository Dropdown */}
              <div className="mb-4">
                <label className="block text-sm text-gray-400 mb-2">Select Repository</label>
                <select
                  value={selectedRepo}
                  onChange={(e) => setSelectedRepo(e.target.value)}
                  disabled={isRunning}
                  className="w-full bg-github-900 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-copilot-500 disabled:opacity-50"
                >
                  {repos.map((repo) => (
                    <option key={repo.name} value={repo.name}>
                      {repo.name}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={startAgent}
                disabled={!allSystemsReady || isRunning || !selectedRepo}
                className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium transition-all ${
                  allSystemsReady && !isRunning && selectedRepo
                    ? 'bg-copilot-600 hover:bg-copilot-700 text-white'
                    : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                }`}
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    Run Compliance Check
                  </>
                )}
              </button>
              
              {/* Reset button when stuck */}
              {isRunning && (
                <button
                  onClick={() => {
                    setIsRunning(false)
                    console.log('[UI] Manual reset')
                  }}
                  className="w-full mt-2 flex items-center justify-center gap-2 py-2 px-4 rounded-lg font-medium bg-red-600 hover:bg-red-700 text-white transition-all"
                >
                  <XCircle className="w-4 h-4" />
                  Reset
                </button>
              )}

              {!allSystemsReady && (
                <p className="text-xs text-yellow-500 mt-2">
                  All systems must be ready to run
                </p>
              )}
            </div>

            {/* Checklist for Selected Repo */}
            {selectedRepo && (
              <div className="bg-github-800 rounded-lg p-4 border border-gray-700">
                <div className="flex items-center gap-2 mb-3">
                  <GitBranch className="w-5 h-5 text-copilot-500" />
                  <span className="font-medium text-white">{selectedRepo}</span>
                </div>
                <RepoChecklist
                  checklist={repoChecklists[selectedRepo] || getDefaultChecklist()}
                  repoName={selectedRepo}
                />
              </div>
            )}

            {/* Tool Calls - Moved here */}
            <div className="flex-1 min-h-0 bg-github-800 rounded-lg border border-gray-700 flex flex-col">
              <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between flex-shrink-0">
                <div className="flex items-center gap-2">
                  <Wrench className="w-5 h-5 text-copilot-500" />
                  <h2 className="font-semibold text-white">Tool Calls</h2>
                </div>
                <span className="text-xs text-gray-500">
                  {toolCalls.length} calls
                </span>
              </div>
              <div className="flex-1 min-h-0 overflow-auto p-3">
                {toolCalls.length === 0 ? (
                  <p className="text-gray-500 text-sm">
                    Tool calls will appear here...
                  </p>
                ) : (
                  [...toolCalls]
                    .reverse()
                    .map((tc, i) => <ToolCallDisplay key={i} toolCall={tc} />)
                )}
              </div>
            </div>

            {/* Results */}
            {prsCreated.length > 0 && (
              <div className="bg-green-900/30 border border-green-700 rounded-lg p-4 flex-shrink-0">
                <h3 className="text-sm font-medium text-green-400 mb-2">
                  Pull Requests Created
                </h3>
                {prsCreated.map((pr, i) => (
                  <a
                    key={i}
                    href={pr}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-sm text-green-300 hover:text-green-200 truncate"
                  >
                    <ExternalLink className="w-3 h-3 inline mr-1" />
                    {pr.split('/').slice(-2).join('/')}
                  </a>
                ))}
              </div>
            )}
          </div>

          {/* Middle Panel - Agent Reasoning */}
          <div className="col-span-5 flex flex-col overflow-hidden">
            {/* Agent Reasoning - Now takes full height */}
            <div className="flex-1 min-h-0 bg-github-800 rounded-lg border border-gray-700 flex flex-col">
              <div className="px-4 py-3 border-b border-gray-700 flex items-center gap-2">
                <Brain className="w-5 h-5 text-copilot-500" />
                <h2 className="font-semibold text-white">Agent Reasoning</h2>
              </div>
              <div className="flex-1 min-h-0 overflow-auto p-4 space-y-3">
                {agentMessages.length === 0 ? (
                  <p className="text-gray-500 text-sm">
                    Agent messages will appear here...
                  </p>
                ) : (
                  agentMessages.map((msg, i) => (
                    <div
                      key={i}
                      className="bg-github-900 rounded p-3 text-sm text-gray-300 prose prose-invert prose-sm max-w-none"
                    >
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          table: ({children}) => (
                            <table className="min-w-full border-collapse border border-gray-600 my-2">
                              {children}
                            </table>
                          ),
                          thead: ({children}) => (
                            <thead className="bg-github-700">{children}</thead>
                          ),
                          th: ({children}) => (
                            <th className="border border-gray-600 px-3 py-2 text-left text-xs font-semibold text-gray-200">
                              {children}
                            </th>
                          ),
                          td: ({children}) => (
                            <td className="border border-gray-600 px-3 py-2 text-xs text-gray-300">
                              {children}
                            </td>
                          ),
                          tr: ({children}) => (
                            <tr className="even:bg-github-800">{children}</tr>
                          ),
                          code: ({children, className}) => {
                            const isInline = !className;
                            return isInline ? (
                              <code className="bg-github-700 px-1 py-0.5 rounded text-copilot-400 text-xs">
                                {children}
                              </code>
                            ) : (
                              <code className={`${className} block bg-github-700 p-2 rounded overflow-x-auto`}>
                                {children}
                              </code>
                            );
                          },
                          ul: ({children}) => (
                            <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>
                          ),
                          ol: ({children}) => (
                            <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>
                          ),
                          li: ({children}) => (
                            <li className="text-gray-300">{children}</li>
                          ),
                          strong: ({children}) => (
                            <strong className="text-white font-semibold">{children}</strong>
                          ),
                        }}
                      >
                        {msg}
                      </ReactMarkdown>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>
          </div>

          {/* Right Panel - Console Logs */}
          <div className="col-span-4 bg-github-800 rounded-lg border border-gray-700 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-700 flex items-center gap-2">
              <Terminal className="w-5 h-5 text-green-500" />
              <h2 className="font-semibold text-white">Console Logs</h2>
            </div>
            <div className="flex-1 min-h-0 overflow-auto p-3 console-log bg-black/30">
              {logs.length === 0 ? (
                <p className="text-gray-500 text-sm">Logs will appear here...</p>
              ) : (
                logs.map((log, i) => (
                  <div
                    key={i}
                    className={`py-1 ${
                      log.level === 'error'
                        ? 'text-red-400'
                        : log.level === 'success'
                        ? 'text-green-400'
                        : log.level === 'warning'
                        ? 'text-yellow-400'
                        : 'text-gray-400'
                    }`}
                  >
                    <span className="text-gray-600">[{log.timestamp}]</span>{' '}
                    {log.repo && (
                      <span className="text-copilot-400">[{log.repo}]</span>
                    )}{' '}
                    {log.message}
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
