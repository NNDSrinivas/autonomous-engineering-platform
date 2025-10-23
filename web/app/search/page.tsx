'use client';
import { useState } from 'react';
import { postJson } from '@/lib/api';

interface SearchHit {
  source: string;
  score: number;
  title?: string;
  foreign_id?: string;
  excerpt?: string;
  url?: string;
  chunk_seq?: number;
}

export default function SearchPage() {
  const [q, setQ] = useState('jwt expiry');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const run = async () => {
    try {
      setError(null);
      const j = await postJson('/api/search/', { q, k: 8 });
      setHits(j.hits);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search');
      setHits([]);
    }
  };
  return (
    <div>
      <h1>Memory Search</h1>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ flex: 1, padding: 8 }}
          placeholder="Search meetings, tasks, code..."
        />
        <button onClick={run}>Search</button>
      </div>
      {error && (
        <div style={{ color: '#dc2626', padding: 12, background: '#fee2e2', borderRadius: 8, margin: '12px 0' }}>
          {error}
        </div>
      )}
      <ul>
        {hits.map((h) => (
          <li
            key={`${h.source}:${h.foreign_id}:${h.chunk_seq}`}
            style={{
              margin: '12px 0',
              background: '#fff',
              padding: 12,
              border: '1px solid #e5e7eb',
              borderRadius: 8,
            }}
          >
            <div
              style={{ fontSize: 12, color: '#64748b' }}
              aria-label={`${h.source} result with relevance score ${h.score}`}
            >
              {h.source} <span aria-hidden="true">•</span> score {h.score}
            </div>
            <div style={{ fontWeight: 600 }}>{h.title || h.foreign_id}</div>
            <div style={{ fontSize: 12, color: '#334155' }}>{h.excerpt}</div>
            {h.url ? (
              <a href={h.url} target="_blank" rel="noopener noreferrer">
                Open
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
