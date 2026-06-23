const NAV_ITEMS = ['Case Details', 'Case Configuration', 'Audit Log']

export default function SettingsPage() {
  return (
    <div className="max-w-screen-xl mx-auto px-6 py-6">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-text">Case Settings</h1>
        <p className="text-sm text-text-mute mt-0.5">Manage case configuration and preferences</p>
      </div>

      <div className="flex gap-5">
        {/* Left nav rail */}
        <aside className="w-48 shrink-0">
          <nav className="bg-panel border border-border rounded-lg overflow-hidden">
            {NAV_ITEMS.map((item, idx) => (
              <button
                key={item}
                className={`
                  w-full text-left px-4 py-3 text-sm transition-colors duration-150
                  hover:bg-panel-2 hover:text-text
                  ${idx === 0
                    ? 'text-navy font-semibold bg-panel-2 border-l-2 border-navy'
                    : 'text-text-mid font-medium border-l-2 border-transparent'}
                  ${idx < NAV_ITEMS.length - 1 ? 'border-b border-border' : ''}
                `}
              >
                {item}
              </button>
            ))}
          </nav>
        </aside>

        {/* Right content area */}
        <div className="flex-1 flex flex-col gap-4">
          {/* Case Details card */}
          <div className="bg-panel border border-border rounded-lg p-5">
            <h2 className="text-sm font-semibold text-text mb-3">Case Details</h2>
            <div className="flex items-center justify-center py-10">
              <div className="text-center">
                <div className="w-10 h-10 bg-panel-3 rounded-full flex items-center justify-center mx-auto mb-2">
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#878E99"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                </div>
                <p className="text-sm text-text-mute">
                  Select a case to edit its details.
                </p>
              </div>
            </div>
          </div>

          {/* Case Configuration card */}
          <div className="bg-panel border border-border rounded-lg p-5">
            <h2 className="text-sm font-semibold text-text mb-3">Case Configuration</h2>
            <div className="flex items-center justify-center py-10">
              <div className="text-center">
                <div className="w-10 h-10 bg-panel-3 rounded-full flex items-center justify-center mx-auto mb-2">
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#878E99"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
                  </svg>
                </div>
                <p className="text-sm text-text-mute">
                  Configuration options will appear here.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
