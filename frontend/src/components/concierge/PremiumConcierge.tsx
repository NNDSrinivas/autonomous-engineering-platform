import React, { useState, useEffect, useRef } from 'react';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  opacity: number;
  color: string;
  life: number;
  maxLife: number;
}

const PremiumConcierge: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [particles, setParticles] = useState<Particle[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());
  const animationFrameRef = useRef<number>();

  // Get time-based theme
  const getTimeTheme = () => {
    const hour = currentTime.getHours();
    if (hour >= 6 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 17) return 'afternoon';  
    if (hour >= 17 && hour < 21) return 'evening';
    return 'night';
  };

  const theme = getTimeTheme();

  // Premium theme configurations
  const themes = {
    morning: {
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      overlay: 'linear-gradient(135deg, rgba(255,223,186,0.3) 0%, rgba(255,180,71,0.2) 100%)',
      particles: { colors: ['#FFD700', '#FFA500', '#FF6347'], count: 25 },
      greeting: 'Good Morning',
      icon: '🌅',
      accent: '#FF6B47',
      shadow: 'rgba(255, 107, 71, 0.3)'
    },
    afternoon: {
      background: 'linear-gradient(135deg, #74b9ff 0%, #0984e3 100%)',
      overlay: 'linear-gradient(135deg, rgba(116,185,255,0.2) 0%, rgba(9,132,227,0.3) 100%)',
      particles: { colors: ['#87CEEB', '#4169E1', '#1E90FF'], count: 20 },
      greeting: 'Good Afternoon',
      icon: '☀️',
      accent: '#4A90E2',
      shadow: 'rgba(74, 144, 226, 0.3)'
    },
    evening: {
      background: 'linear-gradient(135deg, #fd79a8 0%, #e84393 100%)',
      overlay: 'linear-gradient(135deg, rgba(253,121,168,0.2) 0%, rgba(232,67,147,0.3) 100%)',
      particles: { colors: ['#FF69B4', '#FF1493', '#DC143C'], count: 22 },
      greeting: 'Good Evening',
      icon: '🌆',
      accent: '#E84393',
      shadow: 'rgba(232, 67, 147, 0.3)'
    },
    night: {
      background: 'linear-gradient(135deg, #2d3436 0%, #636e72 100%)',
      overlay: 'linear-gradient(135deg, rgba(45,52,54,0.4) 0%, rgba(99,110,114,0.2) 100%)',
      particles: { colors: ['#F39C12', '#E67E22', '#D35400'], count: 30 },
      greeting: 'Good Evening',
      icon: '🌙',
      accent: '#F39C12',
      shadow: 'rgba(243, 156, 18, 0.3)'
    }
  };

  const currentTheme = themes[theme];

  // Initialize premium particle system
  useEffect(() => {
    const initParticles = () => {
      const newParticles: Particle[] = [];
      for (let i = 0; i < currentTheme.particles.count; i++) {
        const color = currentTheme.particles.colors[Math.floor(Math.random() * currentTheme.particles.colors.length)];
        newParticles.push({
          x: Math.random() * 400,
          y: Math.random() * 800,
          vx: (Math.random() - 0.5) * 0.8,
          vy: (Math.random() - 0.5) * 0.5,
          size: Math.random() * 3 + 1,
          opacity: Math.random() * 0.6 + 0.2,
          color,
          life: Math.random() * 100,
          maxLife: 100 + Math.random() * 50
        });
      }
      setParticles(newParticles);
    };

    initParticles();
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [theme]);

  // Animate particles with sophisticated physics
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      setParticles(prevParticles => {
        return prevParticles.map(particle => {
          // Update position with gentle drift
          particle.x += particle.vx;
          particle.y += particle.vy;
          particle.life += 0.5;

          // Gentle boundary wrapping
          if (particle.x < -10) particle.x = canvas.width + 10;
          if (particle.x > canvas.width + 10) particle.x = -10;
          if (particle.y < -10) particle.y = canvas.height + 10;
          if (particle.y > canvas.height + 10) particle.y = -10;

          // Breathing opacity effect
          const lifeCycle = particle.life / particle.maxLife;
          particle.opacity = 0.3 + 0.4 * Math.sin(lifeCycle * Math.PI * 2) * Math.sin(Date.now() * 0.001 + particle.x * 0.01);

          // Reset particle when life ends
          if (particle.life > particle.maxLife) {
            particle.life = 0;
            particle.x = Math.random() * canvas.width;
            particle.y = Math.random() * canvas.height;
          }

          return particle;
        });
      });

      // Draw particles with glow effect
      particles.forEach(particle => {
        ctx.save();
        ctx.globalAlpha = Math.max(0, particle.opacity);
        
        // Outer glow
        ctx.shadowColor = particle.color;
        ctx.shadowBlur = 10;
        ctx.fillStyle = particle.color;
        ctx.beginPath();
        ctx.arc(particle.x, particle.y, particle.size * 1.5, 0, Math.PI * 2);
        ctx.fill();

        // Inner bright core
        ctx.shadowBlur = 0;
        ctx.globalAlpha = Math.max(0, particle.opacity * 1.5);
        ctx.fillStyle = '#FFFFFF';
        ctx.beginPath();
        ctx.arc(particle.x, particle.y, particle.size * 0.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      });

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [particles]);

  // Update time
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="w-96 h-screen relative overflow-hidden" style={{ background: currentTheme.background }}>
      {/* Animated Background Canvas */}
      <canvas
        ref={canvasRef}
        width={384}
        height={800}
        className="absolute inset-0 pointer-events-none"
        style={{ zIndex: 1 }}
      />

      {/* Premium Overlay */}
      <div 
        className="absolute inset-0 pointer-events-none" 
        style={{ 
          background: currentTheme.overlay,
          zIndex: 2
        }} 
      />

      {/* Main Content Container */}
      <div className="relative z-10 h-full flex flex-col">
        {/* Header Section */}
        <div className="px-6 pt-8 pb-6">
          <div className="text-center">
            {/* Weather Icon */}
            <div className="text-6xl mb-4 filter drop-shadow-lg">
              {currentTheme.icon}
            </div>
            
            {/* Greeting */}
            <h1 className="text-2xl font-light text-white mb-2 tracking-wide">
              {currentTheme.greeting}
            </h1>
            
            {/* Time */}
            <div className="text-4xl font-thin text-white/90 mb-1 tracking-wider">
              {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
            
            {/* Date */}
            <div className="text-sm text-white/70 font-medium tracking-wide">
              {currentTime.toLocaleDateString([], { 
                weekday: 'long', 
                month: 'long', 
                day: 'numeric' 
              })}
            </div>
          </div>
        </div>

        {/* Stats Overview */}
        <div className="px-6 mb-6">
          <div 
            className="bg-white/10 backdrop-blur-xl rounded-2xl p-6 border border-white/20"
            style={{ 
              backdropFilter: 'blur(25px)',
              boxShadow: `0 8px 32px ${currentTheme.shadow}`
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-white/90 font-medium">Today's Overview</span>
              <span className="text-2xl font-bold text-white">8</span>
            </div>
            
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-lg font-bold text-red-400 mb-1">3</div>
                <div className="text-xs text-white/70 font-medium">Critical</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-yellow-400 mb-1">2</div>
                <div className="text-xs text-white/70 font-medium">Active</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-green-400 mb-1">75%</div>
                <div className="text-xs text-white/70 font-medium">Complete</div>
              </div>
            </div>
          </div>
        </div>

        {/* Priority Tasks */}
        <div className="px-6 mb-6 flex-1">
          <h3 className="text-lg font-medium text-white/90 mb-4">Priority Items</h3>
          
          <div className="space-y-3">
            {/* High Priority Alert */}
            <div 
              className="bg-white/15 backdrop-blur-xl rounded-xl p-4 border border-white/25 hover:bg-white/20 transition-all duration-300"
              style={{ 
                backdropFilter: 'blur(20px)',
                boxShadow: `0 4px 16px ${currentTheme.shadow}`
              }}
            >
              <div className="flex items-start gap-3">
                <span className="text-red-400 text-lg">🚨</span>
                <div className="flex-1">
                  <h4 className="text-white font-medium mb-1">Security Review Required</h4>
                  <p className="text-white/70 text-sm mb-2">PR #42 contains authentication changes</p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-white/60">Est. 15 minutes</span>
                    <button 
                      className="px-4 py-2 rounded-lg text-white text-sm font-medium hover:scale-105 transition-transform"
                      style={{ backgroundColor: currentTheme.accent }}
                    >
                      Review Now
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Focus Session */}
            <div 
              className="bg-white/15 backdrop-blur-xl rounded-xl p-4 border border-white/25 hover:bg-white/20 transition-all duration-300"
              style={{ 
                backdropFilter: 'blur(20px)',
                boxShadow: `0 4px 16px ${currentTheme.shadow}`
              }}
            >
              <div className="flex items-start gap-3">
                <span className="text-blue-400 text-lg">🎯</span>
                <div className="flex-1">
                  <h4 className="text-white font-medium mb-1">Deep Focus Available</h4>
                  <p className="text-white/70 text-sm mb-2">Algorithm optimization in peak window</p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-white/60">2hr block</span>
                    <button 
                      className="px-4 py-2 rounded-lg text-white text-sm font-medium hover:scale-105 transition-transform"
                      style={{ backgroundColor: currentTheme.accent }}
                    >
                      Start Session
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="px-6 pb-6">
          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: '🎫', label: 'Ticket', color: 'bg-blue-500/20' },
              { icon: '👥', label: 'Standup', color: 'bg-green-500/20' },
              { icon: '📚', label: 'Docs', color: 'bg-purple-500/20' }
            ].map((action, index) => (
              <button
                key={index}
                className={`${action.color} backdrop-blur-xl rounded-xl p-4 border border-white/20 
                           hover:scale-105 transition-all duration-200 text-center`}
                style={{ backdropFilter: 'blur(15px)' }}
              >
                <div className="text-xl mb-1">{action.icon}</div>
                <div className="text-xs text-white/80 font-medium">{action.label}</div>
              </button>
            ))}
          </div>

          {/* Settings */}
          <button 
            className="w-full mt-4 p-3 bg-white/10 backdrop-blur-xl rounded-xl border border-white/20 
                       hover:bg-white/15 transition-all duration-200 flex items-center justify-center gap-2"
            style={{ backdropFilter: 'blur(15px)' }}
          >
            <span className="text-lg">⚙️</span>
            <span className="text-sm text-white/80 font-medium">Customize Experience</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default PremiumConcierge;