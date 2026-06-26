interface FilterCounts {
  all: number
  active: number
  pendingReview: number
  archived: number
}

interface FilterPillsProps {
  counts: FilterCounts
  active: string
  onSelect: (filter: string) => void
}

const pills: { key: string; label: string; countKey: keyof FilterCounts }[] = [
  { key: 'all',            label: 'All',            countKey: 'all' },
  { key: 'active',         label: 'Active',         countKey: 'active' },
  { key: 'pending review', label: 'Pending Review', countKey: 'pendingReview' },
  { key: 'archived',       label: 'Archived',       countKey: 'archived' },
]

export default function FilterPills({ counts, active, onSelect }: FilterPillsProps) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {pills.map(({ key, label, countKey }) => {
        const isActive = active === key
        return (
          <button
            key={key}
            onClick={() => onSelect(key)}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium
              border transition-all duration-150
              ${isActive
                ? 'bg-teal text-white border-teal shadow-sm'
                : 'bg-panel border-border text-text-mid hover:border-border-strong hover:text-text hover:bg-panel-2'
              }
            `}
          >
            {label}
            <span className={`text-xs px-1.5 py-0.5 rounded-md font-semibold
              ${isActive ? 'bg-white/20 text-white' : 'bg-panel-3 text-text-mute'}`}
            >
              {counts[countKey]}
            </span>
          </button>
        )
      })}
    </div>
  )
}
