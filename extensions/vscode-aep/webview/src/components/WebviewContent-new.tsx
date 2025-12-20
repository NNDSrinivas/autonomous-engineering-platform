import React from 'react';

interface WebviewContentProps {
  reviewData: any;
  loading: boolean;
}

export default function WebviewContent({ reviewData, loading }: WebviewContentProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="text-gray-500">Loading review data...</div>
      </div>
    );
  }

  if (!reviewData || !reviewData.files || reviewData.files.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        <div className="text-lg font-medium">No review data available</div>
        <div className="text-sm mt-2">Click "Re-run Review" to start a new analysis</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="text-sm text-gray-600">
        Found {reviewData.files.length} files to review
      </div>
      
      {reviewData.files.map((file: any, index: number) => (
        <div key={index} className="border rounded-lg p-4 bg-white">
          <div className="font-medium text-sm">{file.path || `File ${index + 1}`}</div>
          <div className="text-xs text-gray-500 mt-1">
            {file.issues ? `${file.issues.length} issues found` : 'No issues'}
          </div>
        </div>
      ))}
    </div>
  );
}