export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: 'Inter,system-ui' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '220px 1fr',
            minHeight: '100vh',
          }}
        >
          <aside style={{ background: '#0f172a', color: '#e2e8f0', padding: '16px' }}>
            <h2>AEP</h2>
            <nav style={{ display: 'grid', gap: 8 }}>
              <a href="/">Overview</a>
              <a href="/search">Memory Search</a>
            </nav>
          </aside>
          <main style={{ padding: '16px' }}>{children}</main>
        </div>
      </body>
    </html>
  );
}
