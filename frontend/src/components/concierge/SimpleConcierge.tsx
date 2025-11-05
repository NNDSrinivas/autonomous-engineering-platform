import React, { useState, useEffect } from 'react';

const SimpleConcierge: React.FC = () => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const getGreeting = () => {
    const hour = currentTime.getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    if (hour < 21) return 'Good Evening';
    return 'Good Night';
  };

  const getTimeBasedIcon = () => {
    const hour = currentTime.getHours();
    if (hour < 6) return '🌙'; // Night
    if (hour < 12) return '☀️'; // Morning
    if (hour < 17) return '🌤️'; // Afternoon
    if (hour < 21) return '🌇'; // Evening
    return '🌙'; // Late night
  };

  return (
    <div className="w-96 min-h-screen bg-gradient-to-br from-blue-600 to-purple-700 p-6 text-white">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="text-6xl mb-4">{getTimeBasedIcon()}</div>
        <h1 className="text-2xl font-light mb-2">{getGreeting()}</h1>
        <div className="text-4xl font-thin mb-2">
          {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
        <div className="text-sm opacity-80">
          {currentTime.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}
        </div>
      </div>

      {/* Stats Card */}
      <div className="bg-white/20 backdrop-blur-sm rounded-xl p-6 mb-6 border border-white/30">
        <div className="flex justify-between items-center mb-4">
          <span className="font-medium">Today's Tasks</span>
          <span className="text-2xl font-bold">8</span>
        </div>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-lg font-bold text-red-300">3</div>
            <div className="text-xs opacity-70">Critical</div>
          </div>
          <div>
            <div className="text-lg font-bold text-yellow-300">2</div>
            <div className="text-xs opacity-70">Active</div>
          </div>
          <div>
            <div className="text-lg font-bold text-green-300">75%</div>
            <div className="text-xs opacity-70">Done</div>
          </div>
        </div>
      </div>

      {/* Priority Tasks */}
      <div className="mb-6">
        <h3 className="text-lg font-medium mb-4">Priority Items</h3>
        
        <div className="space-y-3">
          <div className="bg-white/15 backdrop-blur-sm rounded-xl p-4 border border-white/20">
            <div className="flex items-start gap-3">
              <span className="text-red-400 text-lg">🚨</span>
              <div className="flex-1">
                <h4 className="font-medium mb-1">Security Review</h4>
                <p className="text-sm opacity-80 mb-3">PR #42 needs authentication review</p>
                <div className="flex justify-between items-center">
                  <span className="text-xs opacity-60">Est. 15 min</span>
                  <button className="bg-blue-500 hover:bg-blue-600 px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                    Review
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white/15 backdrop-blur-sm rounded-xl p-4 border border-white/20">
            <div className="flex items-start gap-3">
              <span className="text-blue-400 text-lg">🎯</span>
              <div className="flex-1">
                <h4 className="font-medium mb-1">Focus Session</h4>
                <p className="text-sm opacity-80 mb-3">Algorithm optimization ready</p>
                <div className="flex justify-between items-center">
                  <span className="text-xs opacity-60">2hr block</span>
                  <button className="bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                    Start
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mb-6">
        <h3 className="text-lg font-medium mb-4">Quick Actions</h3>
        <div className="grid grid-cols-3 gap-3">
          <button className="bg-white/15 backdrop-blur-sm rounded-xl p-4 text-center border border-white/20 hover:bg-white/25 transition-colors">
            <div className="text-2xl mb-2">🎫</div>
            <div className="text-xs font-medium">Create Ticket</div>
          </button>
          <button className="bg-white/15 backdrop-blur-sm rounded-xl p-4 text-center border border-white/20 hover:bg-white/25 transition-colors">
            <div className="text-2xl mb-2">👥</div>
            <div className="text-xs font-medium">Join Standup</div>
          </button>
          <button className="bg-white/15 backdrop-blur-sm rounded-xl p-4 text-center border border-white/20 hover:bg-white/25 transition-colors">
            <div className="text-2xl mb-2">📚</div>
            <div className="text-xs font-medium">View Docs</div>
          </button>
        </div>
      </div>

      {/* Settings */}
      <button className="w-full bg-white/10 backdrop-blur-sm rounded-xl p-3 border border-white/20 hover:bg-white/20 transition-colors flex items-center justify-center gap-2">
        <span className="text-lg">⚙️</span>
        <span className="text-sm font-medium">Settings</span>
      </button>
    </div>
  );
};

export default SimpleConcierge;