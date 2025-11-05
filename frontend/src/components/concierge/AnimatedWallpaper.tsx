import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

interface WallpaperConfig {
  theme: string;
  animations: string[];
  colors: {
    primary: string;
    secondary: string;
    accent: string;
    text: string;
  };
  particle_effects: {
    enabled: boolean;
    type: string;
    intensity: string;
  };
  transition_duration: string;
  hour: number;
}

interface AnimatedWallpaperProps {
  config: WallpaperConfig;
  className?: string;
}

interface Particle {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  opacity: number;
  type: string;
}

const AnimatedWallpaper: React.FC<AnimatedWallpaperProps> = ({ config, className = '' }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [particles, setParticles] = useState<Particle[]>([]);
  const animationRef = useRef<number>();

  // Initialize particles based on theme
  useEffect(() => {
    if (!config.particle_effects.enabled) return;

    const particleCount = getParticleCount(config.particle_effects.intensity);
    const newParticles: Particle[] = [];

    for (let i = 0; i < particleCount; i++) {
      newParticles.push(createParticle(i, config.theme));
    }

    setParticles(newParticles);
  }, [config]);

  // Animation loop
  useEffect(() => {
    if (!canvasRef.current || particles.length === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const updateCanvasSize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    updateCanvasSize();
    window.addEventListener('resize', updateCanvasSize);

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // Update and draw particles
      setParticles(currentParticles => 
        currentParticles.map(particle => {
          const updated = updateParticle(particle, canvas.width, canvas.height, config.theme);
          drawParticle(ctx, updated, config.colors);
          return updated;
        })
      );

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', updateCanvasSize);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [particles, config]);

  const getParticleCount = (intensity: string): number => {
    switch (intensity) {
      case 'subtle': return 15;
      case 'normal': return 30;
      case 'vibrant': return 50;
      default: return 30;
    }
  };

  const createParticle = (id: number, theme: string): Particle => {
    const canvas = canvasRef.current;
    const width = canvas?.width || window.innerWidth;
    const height = canvas?.height || window.innerHeight;

    const baseParticle = {
      id,
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 3 + 1,
      opacity: Math.random() * 0.6 + 0.2,
    };

    switch (theme) {
      case 'morning':
        return {
          ...baseParticle,
          vx: Math.random() * 0.5 - 0.25,
          vy: Math.random() * 0.3 - 0.15,
          type: Math.random() > 0.7 ? 'butterfly' : 'pollen',
          size: Math.random() * 2 + 0.5,
        };
      case 'afternoon':
        return {
          ...baseParticle,
          vx: Math.random() * 1 - 0.5,
          vy: Math.random() * 0.5 - 0.25,
          type: Math.random() > 0.8 ? 'bird' : 'cloud_particle',
          size: Math.random() * 4 + 1,
        };
      case 'evening':
        return {
          ...baseParticle,
          vx: Math.random() * 0.3 - 0.15,
          vy: Math.random() * 0.2 - 0.1,
          type: Math.random() > 0.9 ? 'seagull' : 'sea_particle',
          size: Math.random() * 2.5 + 0.8,
        };
      case 'night':
        return {
          ...baseParticle,
          vx: Math.random() * 2 - 1,
          vy: Math.random() * 3 + 0.5,
          type: Math.random() > 0.95 ? 'meteor' : 'star',
          size: Math.random() * 1.5 + 0.3,
          opacity: Math.random() * 0.8 + 0.2,
        };
      default:
        return {
          ...baseParticle,
          vx: Math.random() * 1 - 0.5,
          vy: Math.random() * 1 - 0.5,
          type: 'generic',
        };
    }
  };

  const updateParticle = (particle: Particle, width: number, height: number, theme: string): Particle => {
    let { x, y, vx, vy } = particle;

    // Update position
    x += vx;
    y += vy;

    // Handle specific theme behaviors
    switch (theme) {
      case 'morning':
        // Gentle floating motion
        x += Math.sin(Date.now() * 0.001 + particle.id) * 0.1;
        break;
      case 'afternoon':
        // Cloud-like drift
        if (particle.type === 'cloud_particle') {
          x += 0.2;
        }
        break;
      case 'evening':
        // Ocean wave motion
        y += Math.sin(Date.now() * 0.002 + particle.id * 0.1) * 0.15;
        break;
      case 'night':
        // Falling stars and twinkling
        if (particle.type === 'meteor') {
          x -= 2;
          y += 3;
        } else {
          // Twinkling effect for stars
          particle.opacity = 0.3 + Math.sin(Date.now() * 0.003 + particle.id) * 0.3;
        }
        break;
    }

    // Wrap around screen edges
    if (x > width + 10) x = -10;
    if (x < -10) x = width + 10;
    if (y > height + 10) y = -10;
    if (y < -10) y = height + 10;

    return { ...particle, x, y };
  };

  const drawParticle = (ctx: CanvasRenderingContext2D, particle: Particle, colors: any) => {
    ctx.save();
    ctx.globalAlpha = particle.opacity;

    switch (particle.type) {
      case 'butterfly':
        drawButterfly(ctx, particle, colors.accent);
        break;
      case 'pollen':
        drawCircle(ctx, particle, colors.accent);
        break;
      case 'bird':
        drawBird(ctx, particle, colors.text);
        break;
      case 'cloud_particle':
        drawCloudParticle(ctx, particle, colors.secondary);
        break;
      case 'seagull':
        drawSeagull(ctx, particle, colors.text);
        break;
      case 'sea_particle':
        drawCircle(ctx, particle, colors.accent);
        break;
      case 'meteor':
        drawMeteor(ctx, particle, colors.accent);
        break;
      case 'star':
        drawStar(ctx, particle, colors.accent);
        break;
      default:
        drawCircle(ctx, particle, colors.accent);
    }

    ctx.restore();
  };

  const drawCircle = (ctx: CanvasRenderingContext2D, particle: Particle, color: string) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
    ctx.fill();
  };

  const drawStar = (ctx: CanvasRenderingContext2D, particle: Particle, color: string) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    
    const spikes = 5;
    const outerRadius = particle.size;
    const innerRadius = particle.size * 0.5;
    
    for (let i = 0; i < spikes * 2; i++) {
      const radius = i % 2 === 0 ? outerRadius : innerRadius;
      const angle = (i * Math.PI) / spikes;
      const x = particle.x + Math.cos(angle) * radius;
      const y = particle.y + Math.sin(angle) * radius;
      
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    
    ctx.closePath();
    ctx.fill();
  };

  const drawMeteor = (ctx: CanvasRenderingContext2D, particle: Particle, color: string) => {
    const gradient = ctx.createLinearGradient(
      particle.x, particle.y,
      particle.x + 15, particle.y - 15
    );
    gradient.addColorStop(0, color);
    gradient.addColorStop(1, 'transparent');
    
    ctx.strokeStyle = gradient;
    ctx.lineWidth = particle.size;
    ctx.beginPath();
    ctx.moveTo(particle.x, particle.y);
    ctx.lineTo(particle.x + 15, particle.y - 15);
    ctx.stroke();
    
    // Bright head
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.size * 1.5, 0, Math.PI * 2);
    ctx.fill();
  };

  const drawButterfly = (ctx: CanvasRenderingContext2D, particle: Particle, color: string) => {
    ctx.fillStyle = color;
    const size = particle.size;
    
    // Simple butterfly shape with two wing pairs
    ctx.beginPath();
    ctx.ellipse(particle.x - size/2, particle.y - size/2, size/2, size/3, Math.PI/4, 0, Math.PI * 2);
    ctx.ellipse(particle.x + size/2, particle.y - size/2, size/2, size/3, -Math.PI/4, 0, Math.PI * 2);
    ctx.ellipse(particle.x - size/3, particle.y + size/3, size/3, size/4, Math.PI/6, 0, Math.PI * 2);
    ctx.ellipse(particle.x + size/3, particle.y + size/3, size/3, size/4, -Math.PI/6, 0, Math.PI * 2);
    ctx.fill();
  };

  const drawBird = (ctx: CanvasRenderingContext2D, particle: Particle, color: string) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    
    // Simple bird V shape
    const size = particle.size;
    ctx.moveTo(particle.x - size, particle.y);
    ctx.lineTo(particle.x, particle.y - size/2);
    ctx.lineTo(particle.x + size, particle.y);
    
    ctx.stroke();
  };

  const drawSeagull = (ctx: CanvasRenderingContext2D, particle: Particle, color: string) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    
    // Seagull M shape
    const size = particle.size * 1.5;
    ctx.moveTo(particle.x - size, particle.y + size/3);
    ctx.lineTo(particle.x - size/2, particle.y - size/3);
    ctx.lineTo(particle.x, particle.y);
    ctx.lineTo(particle.x + size/2, particle.y - size/3);
    ctx.lineTo(particle.x + size, particle.y + size/3);
    
    ctx.stroke();
  };

  const drawCloudParticle = (ctx: CanvasRenderingContext2D, particle: Particle, color: string) => {
    ctx.fillStyle = color;
    const size = particle.size;
    
    // Fluffy cloud particle
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, size, 0, Math.PI * 2);
    ctx.arc(particle.x + size/2, particle.y, size * 0.7, 0, Math.PI * 2);
    ctx.arc(particle.x - size/2, particle.y, size * 0.7, 0, Math.PI * 2);
    ctx.fill();
  };

  const getBackgroundGradient = (colors: any, theme: string) => {
    switch (theme) {
      case 'morning':
        return `linear-gradient(to bottom, ${colors.primary} 0%, ${colors.secondary} 100%)`;
      case 'afternoon':
        return `linear-gradient(to bottom, ${colors.primary} 0%, ${colors.secondary} 70%, ${colors.accent}20 100%)`;
      case 'evening':
        return `linear-gradient(to bottom, ${colors.accent}40 0%, ${colors.primary} 50%, ${colors.secondary} 100%)`;
      case 'night':
        return `radial-gradient(ellipse at center top, ${colors.secondary} 0%, ${colors.primary} 100%)`;
      default:
        return `linear-gradient(to bottom, ${colors.primary}, ${colors.secondary})`;
    }
  };

  return (
    <div className={`fixed inset-0 -z-10 overflow-hidden ${className}`}>
      {/* Background gradient */}
      <motion.div
        className="absolute inset-0"
        style={{
          background: getBackgroundGradient(config.colors, config.theme),
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 2 }}
      />
      
      {/* CSS-based animations for larger elements */}
      <AnimatedElements theme={config.theme} colors={config.colors} />
      
      {/* Particle canvas */}
      {config.particle_effects.enabled && (
        <canvas
          ref={canvasRef}
          className="absolute inset-0"
          style={{ pointerEvents: 'none' }}
        />
      )}
      
      {/* Overlay for better text readability */}
      <div className="absolute inset-0 bg-black/5" />
    </div>
  );
};

const AnimatedElements: React.FC<{ theme: string; colors: any }> = ({ theme, colors }) => {
  switch (theme) {
    case 'morning':
      return (
        <>
          {/* Sun */}
          <motion.div
            className="absolute top-16 right-16 w-20 h-20 rounded-full"
            style={{ backgroundColor: colors.accent }}
            animate={{
              scale: [1, 1.1, 1],
              opacity: [0.8, 1, 0.8],
            }}
            transition={{
              duration: 4,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
          {/* Grass elements */}
          {Array.from({ length: 20 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute bottom-0 w-1 bg-green-400 origin-bottom"
              style={{
                left: `${i * 5}%`,
                height: `${Math.random() * 30 + 10}px`,
              }}
              animate={{
                rotate: [0, 3, -3, 0],
              }}
              transition={{
                duration: 3 + Math.random() * 2,
                repeat: Infinity,
                delay: Math.random() * 2,
              }}
            />
          ))}
        </>
      );
    
    case 'evening':
      return (
        <>
          {/* Sun/Moon */}
          <motion.div
            className="absolute top-20 left-1/4 w-24 h-24 rounded-full"
            style={{ 
              background: `radial-gradient(circle, ${colors.accent} 0%, ${colors.primary} 100%)` 
            }}
            animate={{
              y: [0, -10, 0],
            }}
            transition={{
              duration: 6,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
          {/* Ocean waves */}
          {Array.from({ length: 5 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute bottom-0 h-8 opacity-60"
              style={{
                left: 0,
                right: 0,
                background: `linear-gradient(to right, transparent, ${colors.secondary}, transparent)`,
                transform: `translateY(${i * 8}px)`,
              }}
              animate={{
                x: [-100, 100],
              }}
              transition={{
                duration: 8 + i * 2,
                repeat: Infinity,
                ease: "linear",
              }}
            />
          ))}
        </>
      );
    
    case 'night':
      return (
        <>
          {/* Moon */}
          <motion.div
            className="absolute top-12 right-20 w-16 h-16 rounded-full"
            style={{ backgroundColor: colors.accent }}
            animate={{
              opacity: [0.7, 1, 0.7],
            }}
            transition={{
              duration: 5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
          {/* Static stars */}
          {Array.from({ length: 50 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1 h-1 rounded-full"
              style={{
                backgroundColor: colors.accent,
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 80}%`,
              }}
              animate={{
                opacity: [0.3, 1, 0.3],
              }}
              transition={{
                duration: 2 + Math.random() * 3,
                repeat: Infinity,
                delay: Math.random() * 2,
              }}
            />
          ))}
        </>
      );
    
    default:
      return null;
  }
};

export default AnimatedWallpaper;