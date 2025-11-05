import React, { useState, useEffect, useRef } from 'react';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  opacity: number;
  type: 'butterfly' | 'pollen' | 'leaf' | 'sparkle';
  rotation: number;
  rotationSpeed: number;
}

const WeatherStyleConcierge: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [particles, setParticles] = useState<Particle[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Get time-based theme
  const getTimeTheme = () => {
    const hour = currentTime.getHours();
    if (hour >= 6 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 17) return 'afternoon';  
    if (hour >= 17 && hour < 21) return 'evening';
    return 'night';
  };

  const theme = getTimeTheme();

  // Theme configurations
  const themes = {
    morning: {
      background: 'linear-gradient(180deg, #FFE5B4 0%, #FFDAB9 50%, #FFB347 100%)',
      particles: { type: 'butterfly' as const, color: '#FF6B35', count: 12 },
      icon: '🌅',
      greeting: 'Good Morning!',
      accent: '#FF8C42'
    },
    afternoon: {
      background: 'linear-gradient(180deg, #87CEEB 0%, #98D8E8 50%, #B0E0E6 100%)',
      particles: { type: 'sparkle' as const, color: '#4A90E2', count: 8 },
      icon: '☀️',
      greeting: 'Good Afternoon!',
      accent: '#4A90E2'
    },
    evening: {
      background: 'linear-gradient(180deg, #FF6B35 0%, #F7931E 50%, #FFB347 100%)',
      particles: { type: 'leaf' as const, color: '#D2691E', count: 10 },
      icon: '🌅',
      greeting: 'Good Evening!',
      accent: '#FF6B35'
    },
    night: {
      background: 'linear-gradient(180deg, #2C3E50 0%, #34495E 50%, #4A6741 100%)',
      particles: { type: 'sparkle' as const, color: '#F39C12', count: 15 },
      icon: '🌙',
      greeting: 'Good Night!',
      accent: '#F39C12'
    }
  };

  const currentTheme = themes[theme];

  // Initialize particles
  useEffect(() => {
    const initParticles = () => {
      const newParticles: Particle[] = [];
      for (let i = 0; i < currentTheme.particles.count; i++) {
        newParticles.push({
          x: Math.random() * 350,
          y: Math.random() * 600,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.3,
          size: Math.random() * 4 + 2,
          opacity: Math.random() * 0.7 + 0.3,
          type: currentTheme.particles.type,
          rotation: Math.random() * Math.PI * 2,
          rotationSpeed: (Math.random() - 0.5) * 0.02
        });
      }
      setParticles(newParticles);
    };

    initParticles();
  }, [theme]);

  // Animate particles
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      particles.forEach(particle => {
        // Update position
        particle.x += particle.vx;
        particle.y += particle.vy;
        particle.rotation += particle.rotationSpeed;

        // Bounce off edges
        if (particle.x < 0 || particle.x > canvas.width) particle.vx *= -1;
        if (particle.y < 0 || particle.y > canvas.height) particle.vy *= -1;

        // Draw particle based on type
        ctx.save();
        ctx.translate(particle.x, particle.y);
        ctx.rotate(particle.rotation);
        ctx.globalAlpha = particle.opacity;

        switch (particle.type) {
          case 'butterfly':
            ctx.fillStyle = currentTheme.particles.color;
            ctx.fillRect(-particle.size/2, -particle.size/4, particle.size, particle.size/2);
            ctx.fillRect(-particle.size/4, -particle.size/2, particle.size/2, particle.size);
            break;
          case 'sparkle':
            ctx.fillStyle = currentTheme.particles.color;
            ctx.beginPath();
            for (let i = 0; i < 4; i++) {
              ctx.lineTo(Math.cos(i * Math.PI / 2) * particle.size, Math.sin(i * Math.PI / 2) * particle.size);
              ctx.lineTo(Math.cos((i + 0.5) * Math.PI / 2) * particle.size/3, Math.sin((i + 0.5) * Math.PI / 2) * particle.size/3);
            }
            ctx.closePath();
            ctx.fill();
            break;
          case 'leaf':
            ctx.fillStyle = currentTheme.particles.color;
            ctx.beginPath();
            ctx.ellipse(0, 0, particle.size/2, particle.size, 0, 0, Math.PI * 2);
            ctx.fill();
            break;
          case 'pollen':
            ctx.fillStyle = currentTheme.particles.color;
            ctx.beginPath();
            ctx.arc(0, 0, particle.size/3, 0, Math.PI * 2);
            ctx.fill();
            break;
        }

        ctx.restore();
      });

      requestAnimationFrame(animate);
    };

    animate();
  }, [particles, currentTheme]);

  // Update time
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div 
      className="w-96 h-full min-h-screen relative overflow-hidden"
      style={{ background: currentTheme.background }}
    >
      {/* Animated Background Canvas */}
      <canvas
        ref={canvasRef}
        width={384}
        height={600}
        className="absolute inset-0 pointer-events-none"
        style={{ zIndex: 1 }}
      />

      {/* Content */}
      <div className="relative z-10 p-4 h-full flex flex-col">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="text-4xl mb-2">{currentTheme.icon}</div>
          <h1 className="text-lg font-semibold text-gray-800 mb-1">
            {currentTheme.greeting}
          </h1>
          <p className="text-sm text-gray-600">
            {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </p>
          <p className="text-xs text-gray-500">
            {currentTime.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })}
          </p>
        </div>

        {/* Stats Cards */}
        <div className="space-y-3 mb-6">
          <div 
            className="bg-white/20 backdrop-blur-md rounded-xl p-4 border border-white/30"
            style={{ backdropFilter: 'blur(20px)' }}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-700">📊 Today's Tasks</span>
              <span 
                className="text-xl font-bold"
                style={{ color: currentTheme.accent }}
              >
                8
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="text-center">
                <div className="font-bold text-red-600">3</div>
                <div className="text-gray-600">High</div>
              </div>
              <div className="text-center">
                <div className="font-bold text-orange-600">2</div>
                <div className="text-gray-600">Active</div>
              </div>
              <div className="text-center">
                <div className="font-bold text-green-600">75%</div>
                <div className="text-gray-600">Done</div>
              </div>
            </div>
          </div>

          <div 
            className="bg-white/20 backdrop-blur-md rounded-xl p-4 border border-white/30"
            style={{ backdropFilter: 'blur(20px)' }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-red-500">🔥</span>
              <span className="text-sm font-medium text-gray-700">Priority Alert</span>
            </div>
            <p className="text-xs text-gray-600 mb-2">Security PR #42 needs review</p>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Est. 15min</span>
              <button 
                className="px-3 py-1 text-xs rounded-lg text-white font-medium"
                style={{ backgroundColor: currentTheme.accent }}
              >
                Review
              </button>
            </div>
          </div>

          <div 
            className="bg-white/20 backdrop-blur-md rounded-xl p-4 border border-white/30"
            style={{ backdropFilter: 'blur(20px)' }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-blue-500">🎯</span>
              <span className="text-sm font-medium text-gray-700">Focus Session</span>
            </div>
            <p className="text-xs text-gray-600 mb-2">Algorithm optimization ready</p>
            <div className="flex justify-between items-center">
              <span className="text-xs text-gray-500">Peak window</span>
              <button 
                className="px-3 py-1 text-xs rounded-lg text-white font-medium"
                style={{ backgroundColor: currentTheme.accent }}
              >
                Start
              </button>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-700 mb-3">⚡ Quick Actions</h3>
          
          {[
            { icon: '🎫', label: 'Create Ticket', color: '#3B82F6' },
            { icon: '👥', label: 'Join Standup', color: '#10B981' },
            { icon: '📚', label: 'View Docs', color: '#8B5CF6' }
          ].map((action, index) => (
            <button
              key={index}
              className="w-full p-3 bg-white/15 backdrop-blur-md rounded-lg border border-white/20 
                         hover:bg-white/25 transition-all duration-200 flex items-center gap-3
                         hover:scale-105 hover:shadow-lg"
              style={{ backdropFilter: 'blur(15px)' }}
            >
              <span className="text-lg">{action.icon}</span>
              <span className="text-sm font-medium text-gray-700">{action.label}</span>
            </button>
          ))}
        </div>

        {/* Settings */}
        <div className="mt-auto pt-4">
          <button 
            className="w-full p-2 bg-white/10 backdrop-blur-md rounded-lg border border-white/20 
                       hover:bg-white/20 transition-all duration-200 flex items-center justify-center gap-2"
            style={{ backdropFilter: 'blur(15px)' }}
          >
            <span>⚙️</span>
            <span className="text-sm text-gray-700">Customize Wallpaper</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default WeatherStyleConcierge;