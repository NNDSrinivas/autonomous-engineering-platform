import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import AnimatedWallpaper from './AnimatedWallpaper';
import WallpaperSettings from './WallpaperSettings';

interface GreetingData {
  primary_message: string;
  time_context: string;
  day_info: string;
  energy_level: string;
  motivational_quote: string;
  timestamp: string;
}

interface TaskSummary {
  total: number;
  high_priority: number;
  in_progress: number;
  completion_rate: string;
}

interface Recommendation {
  type: string;
  title: string;
  description: string;
  reason: string;
  estimated_time: string;
  action: string;
  task_key?: string;
}

interface QuickAction {
  id: string;
  title: string;
  icon: string;
  description: string;
  action: string;
}

interface ConciergeGreetingData {
  greeting: GreetingData;
  wallpaper: any;
  tasks_summary: TaskSummary;
  recommendations: Recommendation[];
  quick_actions: QuickAction[];
}

interface ConciergeGreetingProps {
  onActionClick?: (action: string, data?: any) => void;
  className?: string;
}

const ConciergeGreeting: React.FC<ConciergeGreetingProps> = ({ 
  onActionClick, 
  className = '' 
}) => {
  const [greetingData, setGreetingData] = useState<ConciergeGreetingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showWallpaperSettings, setShowWallpaperSettings] = useState(false);

  const handleWallpaperPreferences = (preferences: any) => {
    console.log('Wallpaper preferences saved:', preferences);
    // Trigger wallpaper refresh or update
  };

  useEffect(() => {
    fetchGreetingData();
  }, []);

  const fetchGreetingData = async () => {
    try {
      setLoading(true);
      
      // For now, use mock data since API might not be ready
      const mockData: ConciergeGreetingData = {
        greeting: {
          primary_message: "Good Morning! Ready to tackle the day?",
          time_context: "It's 11:42 AM on Tuesday, November 5th",
          day_info: "You have 3 meetings scheduled and 5 tasks pending",
          energy_level: "high",
          motivational_quote: "Success is not final, failure is not fatal: it is the courage to continue that counts.",
          timestamp: new Date().toISOString()
        },
        wallpaper: {
          theme: "morning",
          colors: {
            primary: "#FFE4B5",
            secondary: "#FFA500",
            text: "#2C3E50"
          },
          animations: ["butterfly_flight", "sun_rays", "grass_sway"],
          particles: {
            count: 25,
            types: ["butterfly", "pollen", "grass"]
          }
        },
        tasks_summary: {
          total: 8,
          high_priority: 3,
          in_progress: 2,
          completion_rate: "75%"
        },
        recommendations: [
          {
            type: "urgent_task",
            title: "Review PR #42",
            description: "Critical security update needs your review",
            reason: "High priority, blocking deployment",
            estimated_time: "15 minutes",
            action: "review_pr",
            task_key: "PROJ-123"
          },
          {
            type: "focus_session",
            title: "Deep Focus: Algorithm Implementation",
            description: "Complete the sorting algorithm optimization",
            reason: "Peak productivity window",
            estimated_time: "2 hours",
            action: "start_focus",
            task_key: "PROJ-124"
          }
        ],
        quick_actions: [
          {
            id: "1",
            title: "Create JIRA Ticket",
            icon: "ticket",
            description: "Quick issue creation",
            action: "create_jira_ticket"
          },
          {
            id: "2",
            title: "Start Standup",
            icon: "users", 
            description: "Join team meeting",
            action: "join_standup"
          },
          {
            id: "3",
            title: "View Documentation",
            icon: "book",
            description: "Browse project docs",
            action: "view_docs"
          }
        ]
      };

      setGreetingData(mockData);
      setError(null);
      
      // Uncomment this when backend is ready:
      // const response = await fetch('/api/autonomous/concierge/greeting', {
      //   headers: {
      //     'X-User-Id': 'current-user',
      //   },
      // });
      // if (!response.ok) {
      //   throw new Error('Failed to fetch greeting data');
      // }
      // const data = await response.json();
      // setGreetingData(data);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Failed to fetch greeting data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleActionClick = (action: string, data?: any) => {
    if (onActionClick) {
      onActionClick(action, data);
    } else {
      // Default action handling
      console.log('Action clicked:', action, data);
    }
  };

  const getGreetingIcon = (energyLevel: string) => {
    switch (energyLevel) {
      case 'high': return '☀️';
      case 'steady': return '⚡';
      case 'winding_down': return '🌅';
      case 'focused': return '🌙';
      default: return '✨';
    }
  };

  const getPriorityIcon = (type: string) => {
    switch (type) {
      case 'urgent_task': return '🔥';
      case 'focus_session': return '🎯';
      case 'review': return '👀';
      default: return '📋';
    }
  };

  const getQuickActionIcon = (iconName: string) => {
    switch (iconName) {
      case 'ticket': return '🎫';
      case 'git-pull-request': return '🔀';
      case 'users': return '👥';
      case 'book': return '📚';
      default: return '⚡';
    }
  };

  if (loading) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${className}`}>
        <motion.div
          className="text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Preparing your workspace...</p>
        </motion.div>
      </div>
    );
  }

  if (error || !greetingData) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${className}`}>
        <motion.div
          className="text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">
            Unable to load workspace
          </h2>
          <p className="text-gray-600 mb-4">{error || 'Unknown error occurred'}</p>
          <button
            onClick={fetchGreetingData}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            Try Again
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen relative ${className}`}>
      {/* Animated Wallpaper Background */}
      <AnimatedWallpaper config={greetingData.wallpaper} />

      {/* Settings Button */}
      <motion.button
        onClick={() => setShowWallpaperSettings(true)}
        className="fixed top-6 right-6 z-20 w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-white/30 transition-colors shadow-lg"
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 1.5 }}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
      >
        ⚙️
      </motion.button>

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex flex-col">
        {/* Header Greeting */}
        <motion.div
          className="pt-16 pb-8 text-center"
          initial={{ opacity: 0, y: -50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.5 }}
        >
          <div className="text-6xl mb-4">
            {getGreetingIcon(greetingData.greeting.energy_level)}
          </div>
          <h1 
            className="text-4xl font-bold mb-2"
            style={{ color: greetingData.wallpaper.colors.text }}
          >
            {greetingData.greeting.primary_message}
          </h1>
          <p 
            className="text-lg opacity-80 mb-2"
            style={{ color: greetingData.wallpaper.colors.text }}
          >
            {greetingData.greeting.time_context}
          </p>
          <p 
            className="text-sm opacity-60"
            style={{ color: greetingData.wallpaper.colors.text }}
          >
            {greetingData.greeting.day_info}
          </p>
        </motion.div>

        {/* Main Dashboard Content */}
        <div className="flex-1 px-8 pb-8">
          <div className="max-w-7xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              
              {/* Left Column: Tasks Summary */}
              <motion.div
                className="lg:col-span-1"
                initial={{ opacity: 0, x: -50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.8, delay: 0.8 }}
              >
                <div className="bg-white/90 backdrop-blur-sm rounded-2xl p-6 shadow-xl">
                  <h2 className="text-xl font-semibold mb-4 text-gray-800">
                    📊 Today's Overview
                  </h2>
                  
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Total Tasks</span>
                      <span className="text-2xl font-bold text-blue-600">
                        {greetingData.tasks_summary.total}
                      </span>
                    </div>
                    
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">High Priority</span>
                      <span className="text-2xl font-bold text-red-500">
                        {greetingData.tasks_summary.high_priority}
                      </span>
                    </div>
                    
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">In Progress</span>
                      <span className="text-2xl font-bold text-orange-500">
                        {greetingData.tasks_summary.in_progress}
                      </span>
                    </div>
                    
                    <div className="pt-2 border-t">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-600">Completion Rate</span>
                        <span className="text-xl font-bold text-green-500">
                          {greetingData.tasks_summary.completion_rate}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Motivational Quote */}
                <motion.div
                  className="mt-6 bg-white/80 backdrop-blur-sm rounded-2xl p-6 shadow-xl"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.8, delay: 1.2 }}
                >
                  <div className="text-center">
                    <div className="text-3xl mb-3">💡</div>
                    <p className="text-gray-700 italic text-center">
                      "{greetingData.greeting.motivational_quote}"
                    </p>
                  </div>
                </motion.div>
              </motion.div>

              {/* Center Column: Recommendations */}
              <motion.div
                className="lg:col-span-1"
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8, delay: 1.0 }}
              >
                <div className="bg-white/90 backdrop-blur-sm rounded-2xl p-6 shadow-xl">
                  <h2 className="text-xl font-semibold mb-4 text-gray-800">
                    🎯 Smart Recommendations
                  </h2>
                  
                  <div className="space-y-4">
                    {greetingData.recommendations.map((rec, index) => (
                      <motion.div
                        key={index}
                        className="p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors cursor-pointer"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => handleActionClick(rec.action, { 
                          task_key: rec.task_key,
                          type: rec.type 
                        })}
                      >
                        <div className="flex items-start gap-3">
                          <div className="text-2xl">
                            {getPriorityIcon(rec.type)}
                          </div>
                          <div className="flex-1">
                            <h3 className="font-semibold text-gray-800 mb-1">
                              {rec.title}
                            </h3>
                            <p className="text-sm text-gray-600 mb-2">
                              {rec.description}
                            </p>
                            <div className="flex justify-between items-center text-xs">
                              <span className="text-blue-600">
                                {rec.estimated_time}
                              </span>
                              <span className="text-gray-500">
                                {rec.reason}
                              </span>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </motion.div>

              {/* Right Column: Quick Actions */}
              <motion.div
                className="lg:col-span-1"
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.8, delay: 1.4 }}
              >
                <div className="bg-white/90 backdrop-blur-sm rounded-2xl p-6 shadow-xl">
                  <h2 className="text-xl font-semibold mb-4 text-gray-800">
                    ⚡ Quick Actions
                  </h2>
                  
                  <div className="grid grid-cols-2 gap-4">
                    {greetingData.quick_actions.map((action) => (
                      <motion.button
                        key={action.id}
                        className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 hover:from-blue-100 hover:to-blue-200 rounded-xl border border-blue-200 transition-all duration-200"
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => handleActionClick(action.action)}
                      >
                        <div className="text-center">
                          <div className="text-3xl mb-2">
                            {getQuickActionIcon(action.icon)}
                          </div>
                          <h3 className="font-semibold text-gray-800 text-sm mb-1">
                            {action.title}
                          </h3>
                          <p className="text-xs text-gray-600">
                            {action.description}
                          </p>
                        </div>
                      </motion.button>
                    ))}
                  </div>
                </div>

                {/* Settings Button */}
                <motion.div
                  className="mt-6"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.8, delay: 1.6 }}
                >
                  <button
                    className="w-full p-4 bg-white/80 backdrop-blur-sm rounded-2xl shadow-xl hover:bg-white/90 transition-all duration-200 text-center"
                    onClick={() => handleActionClick('open_wallpaper_settings')}
                  >
                    <div className="text-2xl mb-2">🎨</div>
                    <span className="text-gray-700 font-medium">
                      Customize Wallpaper
                    </span>
                  </button>
                </motion.div>
              </motion.div>
            </div>
          </div>
        </div>
      </div>

      {/* Wallpaper Settings Modal */}
      <WallpaperSettings
        isOpen={showWallpaperSettings}
        onClose={() => setShowWallpaperSettings(false)}
        onSave={handleWallpaperPreferences}
      />
    </div>
  );
};

export default ConciergeGreeting;