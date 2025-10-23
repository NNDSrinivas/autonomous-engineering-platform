'use client';
import { useState } from 'react';
import { postJson } from '@/lib/api';

export default function SearchPage() {
  const [q, setQ] = useState('jwt expiry');
  const [hits, setHits] = useState<any[]>([]);
  const run = async () => {
    const j = await postJson('/api/search/', { q, k: 8 });
    setHits(j.hits);
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
      <ul>
        {hits.map((h, i) => (
          <li
            key={i}
            style={{
              margin: '12px 0',
              background: '#fff',
              padding: 12,
              border: '1px solid #e5e7eb',
              borderRadius: 8,
            }}
          >
            <div style={{ fontSize: 12, color: '#64748b' }}>
              {h.source} • score {h.score}
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
