import { useState, useEffect } from 'react';

interface FeedbackStats {
  total_generations: number;
  total_feedback: number;
  feedback_rate: number;
  rating_distribution: Record<number, number>;
  reason_distribution: Record<string, number>;
  period_days: number;
}

interface LearningStats {
  org_key: string;
  contexts: Record<string, {
    precise: ArmPerformance;
    balanced: ArmPerformance;
    creative: ArmPerformance;
  }>;
  last_updated: string;
}

interface ArmPerformance {
  successes: number;
  failures: number;
  total_trials: number;
  success_rate: number | null;
  confidence: number;
}

interface FeedbackEntry {
  id: number;
  rating: number;
  reason?: string;
  comment?: string;
  created_at: string;
  task_type: string;
  model: string;
  temperature: number;
}

export function AdminFeedbackStats() {
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [learningStats, setLearningStats] = useState<LearningStats | null>(null);
  const [recentFeedback, setRecentFeedback] = useState<FeedbackEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState(30);

  useEffect(() => {
    loadData();
  }, [selectedPeriod]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Load all data in parallel
      const [feedbackResponse, learningResponse, recentResponse] = await Promise.all([
        fetch(`/api/feedback/stats?days=${selectedPeriod}`),
        fetch('/api/feedback/learning'),
        fetch('/api/feedback/recent?limit=10'),
      ]);

      const errors = [];

      if (feedbackResponse.ok) {
        const feedbackData = await feedbackResponse.json();
        setFeedbackStats(feedbackData);
      } else {
        errors.push('Unable to load feedback statistics');
      }

      if (learningResponse.ok) {
        const learningData = await learningResponse.json();
        setLearningStats(learningData);
      } else {
        errors.push('Unable to load learning performance data');
      }

      if (recentResponse.ok) {
        const recentData = await recentResponse.json();
        setRecentFeedback(recentData.feedback);
      } else {
        errors.push('Unable to load recent feedback entries');
      }

      if (errors.length > 0) {
        const errorMessage = errors.join('. ') + ' Some data may be incomplete.';
        setError(errorMessage);
      }
    } catch (error) {
      console.error('Error loading feedback data:', error);
      setError('Failed to load feedback data. Please try refreshing the page.');
    } finally {
      setLoading(false);
    }
  };

  const getRatingLabel = (rating: number) => {
    switch (rating) {
      case 1: return 'Positive';
      case 0: return 'Neutral';
      case -1: return 'Negative';
      default: return 'Unknown';
    }
  };

  const getRatingColor = (rating: number) => {
    switch (rating) {
      case 1: return 'text-green-600 bg-green-100';
      case 0: return 'text-gray-600 bg-gray-100';
      case -1: return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/3"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">AI Feedback Analytics</h2>
        <select
          value={selectedPeriod}
          onChange={(e) => setSelectedPeriod(Number(e.target.value))}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-center">
            <span className="text-red-600 text-lg mr-2">⚠️</span>
            <p className="text-sm text-red-600">{error}</p>
          </div>
        </div>
      )}

      {feedbackStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="text-sm font-medium text-gray-600">Total Generations</h3>
            <p className="text-2xl font-bold text-gray-900">{feedbackStats.total_generations}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="text-sm font-medium text-gray-600">Feedback Received</h3>
            <p className="text-2xl font-bold text-gray-900">{feedbackStats.total_feedback}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="text-sm font-medium text-gray-600">Feedback Rate</h3>
            <p className="text-2xl font-bold text-gray-900">{feedbackStats.feedback_rate}%</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="text-sm font-medium text-gray-600">Positive Rate</h3>
            <p className="text-2xl font-bold text-green-600">
              {feedbackStats.total_feedback > 0
                ? Math.round(((feedbackStats.rating_distribution[1] || 0) / feedbackStats.total_feedback) * 100)
                : 0}%
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Rating Distribution */}
        {feedbackStats && (
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Rating Distribution</h3>
            <div className="space-y-3">
              {Object.entries(feedbackStats.rating_distribution).map(([rating, count]) => (
                <div key={rating} className="flex items-center justify-between">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getRatingColor(Number(rating))}`}>
                    {getRatingLabel(Number(rating))}
                  </span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{
                          width: `${feedbackStats.total_feedback > 0 ? (count / feedbackStats.total_feedback) * 100 : 0}%`,
                        }}
                      ></div>
                    </div>
                    <span className="text-sm text-gray-600 w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reason Distribution */}
        {feedbackStats && Object.keys(feedbackStats.reason_distribution).length > 0 && (
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Feedback Reasons</h3>
            <div className="space-y-3">
              {Object.entries(feedbackStats.reason_distribution).map(([reason, count]) => (
                <div key={reason} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700 capitalize">{reason}</span>
                  <span className="text-sm font-medium text-gray-900">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Learning Performance */}
      {learningStats && (
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Contextual Bandit Performance</h3>
          <div className="space-y-4">
            {Object.entries(learningStats.contexts).map(([context, arms]) => (
              <div key={context} className="border border-gray-100 rounded-lg p-4">
                <h4 className="text-md font-medium text-gray-800 mb-3 capitalize">
                  {context.replace('_', ' ')}
                </h4>
                <div className="grid grid-cols-3 gap-4">
                  {Object.entries(arms).map(([arm, performance]: [string, ArmPerformance]) => (
                    <div key={arm} className="text-center">
                      <div className="text-sm font-medium text-gray-700 capitalize mb-1">{arm}</div>
                      <div className="text-lg font-bold text-gray-900">
                        {performance.success_rate !== null ? Math.round(performance.success_rate * 100) : 'N/A'}%
                      </div>
                      <div className="text-xs text-gray-500">
                        {performance.total_trials} trials
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1 mt-2">
                        <div
                          className="bg-blue-600 h-1 rounded-full"
                          style={{ width: `${performance.confidence * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Feedback */}
      {recentFeedback.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="p-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Recent Feedback</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Date</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Rating</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Reason</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Model</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Comment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {recentFeedback.map((entry) => (
                  <tr key={entry.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-600">
                      {formatDate(entry.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs ${getRatingColor(entry.rating)}`}>
                        {getRatingLabel(entry.rating)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600 capitalize">
                      {entry.reason || '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {entry.model} ({entry.temperature})
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-xs truncate">
                      {entry.comment || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}