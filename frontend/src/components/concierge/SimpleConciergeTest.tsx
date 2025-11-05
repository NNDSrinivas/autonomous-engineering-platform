import React, { useState, useEffect } from 'react';

const SimpleConciergeTest: React.FC = () => {
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(true);
  }, []);

  if (!loaded) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
      }}>
        <div style={{ color: 'white', fontSize: '24px' }}>
          🌟 Loading Concierge System...
        </div>
      </div>
    );
  }

  return (
    <div style={{ 
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #FFE4B5 0%, #FFA500 100%)',
      padding: '20px',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* Settings Button */}
      <button 
        style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          width: '50px',
          height: '50px',
          borderRadius: '50%',
          border: 'none',
          background: 'rgba(255, 255, 255, 0.2)',
          backdropFilter: 'blur(10px)',
          fontSize: '24px',
          cursor: 'pointer',
          zIndex: 1000
        }}
      >
        ⚙️
      </button>

      {/* Animated Particles */}
      <div style={{ 
        position: 'fixed', 
        top: 0, 
        left: 0, 
        width: '100%', 
        height: '100%',
        pointerEvents: 'none',
        zIndex: 1
      }}>
        {/* Simulated butterflies */}
        <div style={{
          position: 'absolute',
          top: '20%',
          left: '10%',
          fontSize: '30px',
          animation: 'float 6s ease-in-out infinite'
        }}>🦋</div>
        <div style={{
          position: 'absolute',
          top: '40%',
          right: '20%',
          fontSize: '30px',
          animation: 'float 8s ease-in-out infinite 2s'
        }}>🦋</div>
        <div style={{
          position: 'absolute',
          bottom: '30%',
          left: '30%',
          fontSize: '30px',
          animation: 'float 7s ease-in-out infinite 4s'
        }}>🦋</div>
      </div>

      {/* Main Content */}
      <div style={{ position: 'relative', zIndex: 10, color: '#2C3E50' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div style={{ fontSize: '60px', marginBottom: '20px' }}>☀️</div>
          <h1 style={{ fontSize: '48px', fontWeight: 'bold', margin: '0 0 10px 0' }}>
            Good Morning! Ready to tackle the day?
          </h1>
          <p style={{ fontSize: '18px', opacity: 0.8, margin: '0 0 10px 0' }}>
            It's 11:42 AM on Tuesday, November 5th
          </p>
          <p style={{ fontSize: '14px', opacity: 0.6, margin: 0 }}>
            You have 3 meetings scheduled and 5 tasks pending
          </p>
        </div>

        {/* Dashboard Grid */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '30px',
          maxWidth: '1400px',
          margin: '0 auto'
        }}>
          
          {/* Tasks Summary */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.9)',
            backdropFilter: 'blur(20px)',
            borderRadius: '20px',
            padding: '30px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ margin: '0 0 20px 0', fontSize: '20px' }}>📊 Today's Overview</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Total Tasks</span>
                <span style={{ fontSize: '24px', fontWeight: 'bold', color: '#3B82F6' }}>8</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>High Priority</span>
                <span style={{ fontSize: '24px', fontWeight: 'bold', color: '#EF4444' }}>3</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>In Progress</span>
                <span style={{ fontSize: '24px', fontWeight: 'bold', color: '#F97316' }}>2</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '10px', borderTop: '1px solid #E5E7EB' }}>
                <span>Completion Rate</span>
                <span style={{ fontSize: '20px', fontWeight: 'bold', color: '#10B981' }}>75%</span>
              </div>
            </div>
          </div>

          {/* AI Recommendations */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.9)',
            backdropFilter: 'blur(20px)',
            borderRadius: '20px',
            padding: '30px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ margin: '0 0 20px 0', fontSize: '20px' }}>🤖 AI Recommendations</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
              <div style={{ 
                padding: '15px',
                background: 'rgba(239, 68, 68, 0.1)',
                borderRadius: '10px',
                borderLeft: '4px solid #EF4444'
              }}>
                <div style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '5px' }}>
                  🔥 Review PR #42
                </div>
                <div style={{ fontSize: '14px', color: '#666', marginBottom: '5px' }}>
                  Critical security update needs your review
                </div>
                <div style={{ fontSize: '12px', color: '#999' }}>
                  Estimated: 15 minutes
                </div>
              </div>
              
              <div style={{ 
                padding: '15px',
                background: 'rgba(59, 130, 246, 0.1)',
                borderRadius: '10px',
                borderLeft: '4px solid #3B82F6'
              }}>
                <div style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '5px' }}>
                  🎯 Deep Focus Session
                </div>
                <div style={{ fontSize: '14px', color: '#666', marginBottom: '5px' }}>
                  Complete algorithm optimization
                </div>
                <div style={{ fontSize: '12px', color: '#999' }}>
                  Estimated: 2 hours
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.9)',
            backdropFilter: 'blur(20px)',
            borderRadius: '20px',
            padding: '30px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ margin: '0 0 20px 0', fontSize: '20px' }}>⚡ Quick Actions</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[
                { icon: '🎫', title: 'Create JIRA Ticket', desc: 'Quick issue creation' },
                { icon: '👥', title: 'Start Standup', desc: 'Join team meeting' },
                { icon: '📚', title: 'View Documentation', desc: 'Browse project docs' }
              ].map((action, index) => (
                <button
                  key={index}
                  style={{
                    padding: '15px',
                    background: 'rgba(255, 255, 255, 0.8)',
                    border: 'none',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '15px'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 1)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.8)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  <div style={{ fontSize: '24px' }}>{action.icon}</div>
                  <div>
                    <div style={{ fontWeight: 'bold', fontSize: '14px' }}>{action.title}</div>
                    <div style={{ fontSize: '12px', color: '#666' }}>{action.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* CSS Animation */}
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px) rotate(0deg); }
          25% { transform: translateY(-20px) rotate(5deg); }
          50% { transform: translateY(-10px) rotate(-5deg); }
          75% { transform: translateY(-15px) rotate(3deg); }
        }
      `}</style>
    </div>
  );
};

export default SimpleConciergeTest;