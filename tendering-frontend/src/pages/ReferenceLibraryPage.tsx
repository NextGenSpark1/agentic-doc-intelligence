import { useEffect, useState } from 'react';
import { Search, Download, BookOpen } from 'lucide-react';
import { getReferenceDocuments } from '../api/tenders';
import { CategoryBadge } from '../components/Badge';
import type { ReferenceDocument, ReferenceCategory } from '../types';

const ALL_CATEGORIES: ReferenceCategory[] = ['legal', 'financial', 'technical', 'template', 'other'];

export function ReferenceLibraryPage() {
  const [documents, setDocuments] = useState<ReferenceDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<ReferenceCategory | 'all'>('all');

  useEffect(() => {
    getReferenceDocuments().then(setDocuments).finally(() => setLoading(false));
  }, []);

  const filtered = documents.filter((doc) => {
    const matchesSearch =
      doc.title.toLowerCase().includes(search.toLowerCase()) ||
      doc.description.toLowerCase().includes(search.toLowerCase()) ||
      doc.tags.some((tag) => tag.toLowerCase().includes(search.toLowerCase()));
    const matchesCategory = categoryFilter === 'all' || doc.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="pt-[6.5rem] px-6 pb-10 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text">Reference Library</h1>
        <p className="text-sm text-text-mute mt-0.5">Legal documents, templates, and guides for tender preparation</p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1 max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-mute" />
          <input
            type="text"
            placeholder="Search documents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm bg-panel border border-border rounded-lg outline-none focus:border-teal transition-colors"
          />
        </div>

        <div className="flex gap-1 flex-wrap">
          <button
            onClick={() => setCategoryFilter('all')}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              categoryFilter === 'all' ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
            }`}
          >
            All
          </button>
          {ALL_CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setCategoryFilter(c)}
              className={`px-3 py-1.5 rounded text-xs font-medium capitalize transition-colors ${
                categoryFilter === c ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-center text-sm text-text-mute py-16">Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center text-sm text-text-mute py-16">No documents found.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((doc) => (
            <div key={doc.id} className="bg-panel border border-border rounded-lg p-5 flex flex-col">
              <div className="flex items-start gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-teal/10 flex items-center justify-center flex-shrink-0">
                  <BookOpen size={16} className="text-teal" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-text line-clamp-2">{doc.title}</h3>
                  <CategoryBadge category={doc.category} />
                </div>
              </div>

              <p className="text-xs text-text-mute flex-1 line-clamp-3 mb-4">{doc.description}</p>

              {/* Tags */}
              <div className="flex flex-wrap gap-1 mb-4">
                {doc.tags.map((tag) => (
                  <span key={tag} className="px-2 py-0.5 bg-panel-3 text-text-mute text-xs rounded">
                    {tag}
                  </span>
                ))}
              </div>

              <a
                href={doc.url}
                className="flex items-center justify-center gap-2 w-full py-2 text-xs font-medium text-teal border border-teal rounded hover:bg-teal hover:text-white transition-colors"
              >
                <Download size={13} />
                Download
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
