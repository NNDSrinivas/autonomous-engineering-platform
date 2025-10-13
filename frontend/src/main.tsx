import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

function App() {
  return (
    <div style={{ 
      padding: '40px', 
      fontFamily: 'Arial, sans-serif',
      backgroundColor: '#f8fafc',
      minHeight: '100vh'
    }}>
      <div style={{
        backgroundColor: 'white',
        padding: '20px',
        borderRadius: '8px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
      }}>
        <h1 style={{ 
          color: '#2563eb', 
          margin: '0 0 20px 0',
          fontSize: '32px'
        }}>
          🤖 Autonomous Engineering Platform
        </h1>
        <p style={{ fontSize: '18px', color: '#4b5563' }}>
          Welcome to your AI-powered engineering assistant!
        </p>
        
        <div style={{ 
          backgroundColor: '#ecfdf5', 
          border: '1px solid #a7f3d0',
          padding: '16px', 
          borderRadius: '8px',
          marginTop: '20px'
        }}>
          <h2 style={{ color: '#065f46', margin: '0 0 10px 0' }}>✅ System Status</h2>
          <p style={{ color: '#047857', margin: '5px 0' }}>• React frontend is running</p>
          <p style={{ color: '#047857', margin: '5px 0' }}>• Development server active on port 3000</p>
          <p style={{ color: '#047857', margin: '5px 0' }}>• Ready for full dashboard deployment</p>
        </div>

        <button 
          onClick={() => alert('Platform is working!')}
          style={{
            backgroundColor: '#2563eb',
            color: 'white',
            border: 'none',
            padding: '12px 24px',
            borderRadius: '6px',
            fontSize: '16px',
            cursor: 'pointer',
            marginTop: '20px'
          }}
        >
          🚀 Test Interaction
        </button>
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
