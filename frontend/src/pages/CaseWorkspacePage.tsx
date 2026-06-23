import { useParams, useNavigate } from 'react-router-dom'

const SUBTABS = ['Workspace', 'Entity Graph', 'Timeline', 'Findings', 'Report']

const PLACEHOLDER_DOCS = [
  { name: 'Contract_2024_Q3.pdf', type: 'PDF' },
  { name: 'Payments_Ledger.xlsx', type: 'XLS' },
  { name: 'Invoice_Batch_Aug.pdf', type: 'PDF' },
]

export default function CaseWorkspacePage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 96px)' }}>
      {/* Sub-header */}
      <div className="bg-panel border-b border-border px-6 py-3 flex flex-col gap-2 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/cases')}
            className="text-teal text-sm font-medium hover:text-teal-soft transition-colors duration-150"
          >
            ← Cases
          </button>
          <span className="text-text-mute text-sm">/</span>
          <span className="text-sm font-mono text-text-mid">{caseId}</span>
          <span className="text-sm font-semibold text-text">Case Workspace</span>
        </div>

        {/* Sub-tabs */}
        <div className="flex items-center gap-1">
          {SUBTABS.map((tab) => (
            <span
              key={tab}
              className={`
                px-3 py-1 rounded text-sm font-medium cursor-pointer transition-colors duration-150
                ${tab === 'Workspace'
                  ? 'bg-navy text-white'
                  : 'text-text-mute hover:text-text hover:bg-panel-2'}
              `}
            >
              {tab}
            </span>
          ))}
        </div>
      </div>

      {/* Three-panel layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel — Documents */}
        <aside
          className="bg-panel border-r border-border flex flex-col shrink-0 overflow-y-auto"
          style={{ width: 240 }}
        >
          <div className="px-4 py-3 border-b border-border">
            <span className="text-xs font-semibold text-text-mute uppercase tracking-wide">Documents</span>
          </div>
          <div className="flex flex-col gap-0.5 p-2">
            {PLACEHOLDER_DOCS.map((doc) => (
              <div
                key={doc.name}
                className="flex items-center gap-2 px-2 py-2 rounded hover:bg-panel-2 cursor-pointer transition-colors duration-150"
              >
                <span
                  className={`
                    text-xs font-mono font-semibold px-1.5 py-0.5 rounded shrink-0
                    ${doc.type === 'PDF' ? 'bg-red-bg text-red' : 'bg-green-bg text-green'}
                  `}
                >
                  {doc.type}
                </span>
                <span className="text-xs text-text truncate">{doc.name}</span>
              </div>
            ))}
          </div>
          <div className="mt-auto px-4 py-3 border-t border-border">
            <button className="text-teal text-xs font-medium hover:text-teal-soft transition-colors duration-150">
              + Upload document
            </button>
          </div>
        </aside>

        {/* Center panel — Document Viewer */}
        <main className="flex-1 bg-canvas-deep flex items-center justify-center overflow-auto">
          <div className="flex flex-col items-center gap-3 text-center px-6">
            {/* Document icon */}
            <div className="w-14 h-14 bg-panel border border-border rounded-xl flex items-center justify-center shadow-sm">
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#878E99"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="9" y1="13" x2="15" y2="13" />
                <line x1="9" y1="17" x2="15" y2="17" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-text">Document Viewer</h3>
            <p className="text-xs text-text-mute max-w-[220px]">
              Select a document from the left panel to view its contents here.
            </p>
          </div>
        </main>

        {/* Right panel — Case Assistant */}
        <aside
          className="bg-panel border-l border-border flex flex-col shrink-0 overflow-hidden"
          style={{ width: 300 }}
        >
          <div className="px-4 py-3 border-b border-border">
            <span className="text-xs font-semibold text-text-mute uppercase tracking-wide">Case Assistant</span>
          </div>

          {/* Chat area */}
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
            {/* Greeting bubble */}
            <div className="bg-teal/10 border border-teal/20 rounded-lg px-3 py-2.5">
              <p className="text-xs text-text">
                Hi! I'm your Case Assistant for{' '}
                <span className="font-mono font-semibold text-teal">{caseId}</span>. Ask me anything
                about the documents in this case.
              </p>
            </div>
            <p className="text-xs text-text-mute text-center">No messages yet</p>
          </div>

          {/* Input area */}
          <div className="border-t border-border p-3">
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Ask the assistant..."
                className="
                  flex-1 border border-border-strong rounded-md px-3 py-2 text-xs text-text bg-panel
                  placeholder:text-text-mute
                  focus:outline-none focus:ring-2 focus:ring-teal/30 focus:border-teal
                  transition-colors duration-150
                "
              />
              <button className="bg-teal text-white text-xs font-medium px-3 py-2 rounded-md hover:bg-teal-soft transition-colors duration-150 shrink-0">
                Send
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
