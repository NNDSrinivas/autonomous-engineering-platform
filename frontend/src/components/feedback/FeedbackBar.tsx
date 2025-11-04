import { useState } from 'react';

interface FeedbackBarProps {
  generationLogId: number | null;
  onFeedbackSubmitted?: () => void;
}

interface FeedbackData {
  rating: number;
  reason?: string;
  comment?: string;
}

const FEEDBACK_REASONS = [
  { value: 'correctness', label: 'Code Correctness' },
  { value: 'style', label: 'Code Style' },
  { value: 'performance', label: 'Performance' },
  { value: 'security', label: 'Security' },
  { value: 'other', label: 'Other' },
];

export function FeedbackBar({ generationLogId, onFeedbackSubmitted }: FeedbackBarProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [selectedRating, setSelectedRating] = useState<number | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackData>({ rating: 0 });
  const [error, setError] = useState<string | null>(null);

  const handleRatingClick = (rating: number) => {
    if (hasSubmitted) return;
    
    setSelectedRating(rating);
    setFeedback({ ...feedback, rating });
    
    if (rating !== 0) {
      setShowDetails(true);
    } else {
      // Neutral rating - show brief confirmation before submitting
      setError(null);
      submitFeedback({ rating });
    }
  };

  const submitFeedback = async (feedbackData: FeedbackData) => {
    if (!generationLogId || isSubmitting) return;

    setIsSubmitting(true);
    
    try {
      const response = await fetch('/api/feedback/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          gen_id: generationLogId,
          rating: feedbackData.rating,
          reason: feedbackData.reason,
          comment: feedbackData.comment,
        }),
      });

      if (response.ok) {
        setHasSubmitted(true);
        setShowDetails(false);
        setError(null);
        onFeedbackSubmitted?.();
      } else {
        const errorText = await response.text();
        console.error('Failed to submit feedback:', response.status, errorText);
        setError('Failed to submit feedback. Please try again.');
      }
    } catch (error) {
      console.error('Error submitting feedback:', error);
      setError('Network error. Please check your connection and try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitDetails = () => {
    submitFeedback(feedback);
  };

  if (!generationLogId) {
    return null;
  }

  if (hasSubmitted) {
    return (
      <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
        <span className="text-lg">👍</span>
        <span className="text-sm text-green-700">Thank you for your feedback!</span>
      </div>
    );
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-700">
          How helpful was this code generation?
        </span>
        {isSubmitting && (
          <div className="w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin"></div>
        )}
      </div>

      <div className="flex items-center gap-2 mb-3">
        <button
          onClick={() => handleRatingClick(-1)}
          disabled={isSubmitting || hasSubmitted}
          className={`p-2 rounded-lg transition-colors ${
            selectedRating === -1
              ? 'bg-red-100 text-red-600 border-red-300'
              : 'bg-white hover:bg-red-50 text-gray-600 hover:text-red-600'
          } border disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <span className="text-lg">👎</span>
        </button>

        <button
          onClick={() => handleRatingClick(0)}
          disabled={isSubmitting || hasSubmitted}
          className={`px-3 py-2 rounded-lg transition-colors text-sm ${
            selectedRating === 0
              ? 'bg-gray-200 text-gray-800 border-gray-400'
              : 'bg-white hover:bg-gray-100 text-gray-600'
          } border disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          Neutral
        </button>

        <button
          onClick={() => handleRatingClick(1)}
          disabled={isSubmitting || hasSubmitted}
          className={`p-2 rounded-lg transition-colors ${
            selectedRating === 1
              ? 'bg-green-100 text-green-600 border-green-300'
              : 'bg-white hover:bg-green-50 text-gray-600 hover:text-green-600'
          } border disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <span className="text-lg">👍</span>
        </button>
      </div>

      {showDetails && selectedRating !== null && (
        <div className="space-y-3 pt-3 border-t border-gray-300">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              What aspect needs improvement? (optional)
            </label>
            <select
              value={feedback.reason || ''}
              onChange={(e) => setFeedback({ ...feedback, reason: e.target.value || undefined })}
              className="w-full p-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select a reason...</option>
              {FEEDBACK_REASONS.map((reason) => (
                <option key={reason.value} value={reason.value}>
                  {reason.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Additional comments (optional)
            </label>
            <textarea
              value={feedback.comment || ''}
              onChange={(e) => setFeedback({ ...feedback, comment: e.target.value || undefined })}
              placeholder="Any specific feedback to help improve future generations..."
              className="w-full p-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
              rows={3}
              maxLength={1000}
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowDetails(false)}
              className="px-3 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmitDetails}
              disabled={isSubmitting}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <span>📤</span>
              Submit
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
    </div>
  );
}