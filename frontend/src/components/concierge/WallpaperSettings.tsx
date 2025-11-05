import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface WallpaperTheme {
  id: string;
  name: string;
  description: string;
  preview_image?: string;
}

interface TimeBasedTheme {
  name: string;
  description: string;
  primary_color: string;
  accent_color: string;
  animations: string[];
}

interface WallpaperPreferences {
  theme: string;
  custom_background?: string;
  animation_speed: string;
  particles_enabled: boolean;
  time_based_themes: boolean;
}

interface WallpaperSettingsProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (preferences: WallpaperPreferences) => void;
  currentPreferences?: WallpaperPreferences;
}

const WallpaperSettings: React.FC<WallpaperSettingsProps> = ({
  isOpen,
  onClose,
  onSave,
  currentPreferences
}) => {
  const [preferences, setPreferences] = useState<WallpaperPreferences>({
    theme: 'dynamic',
    animation_speed: 'normal',
    particles_enabled: true,
    time_based_themes: true,
    ...currentPreferences
  });

  const [availableThemes, setAvailableThemes] = useState<{
    time_based_themes: Record<string, TimeBasedTheme>;
    custom_themes: WallpaperTheme[];
    animation_options: {
      speed: string[];
      intensity: string[];
      particles: string[];
    };
  } | null>(null);

  const [activeTab, setActiveTab] = useState<'themes' | 'animations' | 'advanced'>('themes');

  useEffect(() => {
    if (isOpen) {
      fetchAvailableThemes();
    }
  }, [isOpen]);

  const fetchAvailableThemes = async () => {
    try {
      const response = await fetch('/api/autonomous/concierge/wallpaper/themes');
      const data = await response.json();
      setAvailableThemes(data);
    } catch (error) {
      console.error('Failed to fetch wallpaper themes:', error);
    }
  };

  const handleSave = async () => {
    try {
      const response = await fetch('/api/autonomous/concierge/wallpaper/preferences', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': 'current-user',
        },
        body: JSON.stringify(preferences),
      });

      if (response.ok) {
        onSave(preferences);
        onClose();
      } else {
        console.error('Failed to save preferences');
      }
    } catch (error) {
      console.error('Error saving preferences:', error);
    }
  };

  const getThemePreview = (theme: TimeBasedTheme) => {
    return (
      <div
        className="w-full h-20 rounded-lg relative overflow-hidden"
        style={{
          background: `linear-gradient(135deg, ${theme.primary_color}, ${theme.accent_color})`
        }}
      >
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-white font-medium text-sm">{theme.name}</span>
        </div>
        {theme.animations.includes('star_twinkle') && (
          <div className="absolute top-2 right-2 w-2 h-2 bg-white rounded-full animate-pulse" />
        )}
        {theme.animations.includes('sun_rays') && (
          <div className="absolute top-1 right-4 w-3 h-3 bg-yellow-300 rounded-full" />
        )}
        {theme.animations.includes('wave_motion') && (
          <div className="absolute bottom-0 left-0 right-0 h-2 bg-blue-300 opacity-60" />
        )}
      </div>
    );
  };

  const getCurrentTimeTheme = () => {
    const hour = new Date().getHours();
    if (hour >= 6 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 18) return 'afternoon';
    if (hour >= 18 && hour < 22) return 'evening';
    return 'night';
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Modal */}
        <motion.div
          className="relative bg-white rounded-2xl shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden"
          initial={{ scale: 0.9, y: 50 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.9, y: 50 }}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-semibold text-gray-800">
                🎨 Wallpaper Settings
              </h2>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600 text-2xl"
              >
                ×
              </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-4 mt-4">
              {[
                { key: 'themes', label: 'Themes', icon: '🌈' },
                { key: 'animations', label: 'Animations', icon: '✨' },
                { key: 'advanced', label: 'Advanced', icon: '⚙️' }
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as any)}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-colors ${
                    activeTab === tab.key
                      ? 'bg-blue-100 text-blue-600'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span>{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Content */}
          <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
            {activeTab === 'themes' && (
              <div className="space-y-6">
                {/* Time-based Themes Toggle */}
                <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                  <div>
                    <h3 className="font-semibold text-gray-800">Dynamic Time-based Themes</h3>
                    <p className="text-sm text-gray-600">
                      Automatically change wallpaper based on time of day
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={preferences.time_based_themes}
                      onChange={(e) => setPreferences(prev => ({
                        ...prev,
                        time_based_themes: e.target.checked
                      }))}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {/* Current Time Theme Preview */}
                {preferences.time_based_themes && availableThemes && (
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h3 className="font-semibold text-gray-800 mb-3">
                      Current Time Theme: {getCurrentTimeTheme().charAt(0).toUpperCase() + getCurrentTimeTheme().slice(1)}
                    </h3>
                    {getThemePreview(availableThemes.time_based_themes[getCurrentTimeTheme()])}
                  </div>
                )}

                {/* Time-based Themes Grid */}
                {availableThemes && (
                  <div>
                    <h3 className="font-semibold text-gray-800 mb-4">Available Time Themes</h3>
                    <div className="grid grid-cols-2 gap-4">
                      {Object.entries(availableThemes.time_based_themes).map(([key, theme]) => (
                        <div key={key} className="p-4 border rounded-lg hover:border-blue-300 transition-colors">
                          <h4 className="font-medium text-gray-800 mb-2">{theme.name}</h4>
                          {getThemePreview(theme)}
                          <p className="text-xs text-gray-600 mt-2">{theme.description}</p>
                          <div className="flex gap-1 mt-2">
                            {theme.animations.slice(0, 3).map((animation, index) => (
                              <span key={index} className="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded">
                                {animation.replace('_', ' ')}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Custom Themes */}
                {availableThemes && (
                  <div>
                    <h3 className="font-semibold text-gray-800 mb-4">Custom Themes</h3>
                    <div className="grid grid-cols-3 gap-4">
                      {availableThemes.custom_themes.map((theme) => (
                        <button
                          key={theme.id}
                          onClick={() => setPreferences(prev => ({ ...prev, theme: theme.id }))}
                          className={`p-4 border rounded-lg text-left hover:border-blue-300 transition-colors ${
                            preferences.theme === theme.id ? 'border-blue-500 bg-blue-50' : ''
                          }`}
                        >
                          <h4 className="font-medium text-gray-800">{theme.name}</h4>
                          <p className="text-sm text-gray-600 mt-1">{theme.description}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'animations' && (
              <div className="space-y-6">
                {/* Animation Speed */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Animation Speed
                  </label>
                  <div className="grid grid-cols-3 gap-4">
                    {['slow', 'normal', 'fast'].map((speed) => (
                      <button
                        key={speed}
                        onClick={() => setPreferences(prev => ({ ...prev, animation_speed: speed }))}
                        className={`p-3 border rounded-lg text-center transition-colors ${
                          preferences.animation_speed === speed
                            ? 'border-blue-500 bg-blue-50 text-blue-600'
                            : 'border-gray-300 hover:border-blue-300'
                        }`}
                      >
                        <div className="text-2xl mb-1">
                          {speed === 'slow' ? '🐌' : speed === 'normal' ? '🚶' : '🏃'}
                        </div>
                        {speed.charAt(0).toUpperCase() + speed.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Particle Effects */}
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h3 className="font-semibold text-gray-800">Particle Effects</h3>
                    <p className="text-sm text-gray-600">
                      Enable floating particles and dynamic elements
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={preferences.particles_enabled}
                      onChange={(e) => setPreferences(prev => ({
                        ...prev,
                        particles_enabled: e.target.checked
                      }))}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {/* Animation Preview */}
                <div className="p-4 bg-gradient-to-br from-blue-100 to-purple-100 rounded-lg">
                  <h3 className="font-semibold text-gray-800 mb-3">Preview</h3>
                  <div className="relative h-32 bg-gradient-to-br from-blue-200 to-purple-200 rounded-lg overflow-hidden">
                    <div className="absolute top-2 left-2 w-2 h-2 bg-white rounded-full animate-pulse"></div>
                    <div className="absolute top-4 right-6 w-3 h-3 bg-yellow-300 rounded-full"></div>
                    <div className="absolute bottom-0 left-0 right-0 h-3 bg-blue-300 opacity-60"></div>
                    <div className="absolute inset-0 flex items-center justify-center text-gray-700">
                      Animation Speed: {preferences.animation_speed}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'advanced' && (
              <div className="space-y-6">
                {/* Custom Background Upload */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Custom Background Image
                  </label>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                    <div className="text-4xl mb-2">📁</div>
                    <p className="text-gray-600 mb-4">Upload your own background image</p>
                    <button className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors">
                      Choose File
                    </button>
                  </div>
                </div>

                {/* Performance Settings */}
                <div className="p-4 bg-yellow-50 rounded-lg">
                  <h3 className="font-semibold text-gray-800 mb-3">⚡ Performance Tips</h3>
                  <ul className="text-sm text-gray-600 space-y-2">
                    <li>• Disable particles on slower devices</li>
                    <li>• Use 'slow' animation speed to reduce CPU usage</li>
                    <li>• Custom backgrounds may impact loading time</li>
                  </ul>
                </div>

                {/* Reset to Defaults */}
                <div className="flex justify-center">
                  <button
                    onClick={() => setPreferences({
                      theme: 'dynamic',
                      animation_speed: 'normal',
                      particles_enabled: true,
                      time_based_themes: true,
                    })}
                    className="px-6 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Reset to Defaults
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              Save Changes
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default WallpaperSettings;