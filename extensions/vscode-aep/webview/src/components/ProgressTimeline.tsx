import React from 'react';

interface RefactorProgress {
  stage: string;
  message: string;
  timestamp?: string;
  progress?: number;
  file?: string;
  status?: 'running' | 'completed' | 'error' | 'waiting';
}

interface ProgressTimelineProps {
  steps: RefactorProgress[];
  currentFile?: string;
  className?: string;
}

const getStageIcon = (stage: string, status?: string): string => {
  if (status === 'error') return '❌';
  if (status === 'completed') return '✅';
  if (status === 'running') return '⏳';
  
  switch (stage.toLowerCase()) {
    case 'analysis':
    case 'analyzing':
      return '🔍';
    case 'planning':
    case 'plan':
      return '📋';
    case 'ast_edit':
    case 'editing':
      return '🔧';
    case 'diffing':
    case 'diff':
      return '📝';
    case 'validation':
    case 'validating':
      return '✔️';
    case 'completion':
    case 'done':
      return '🎉';
    case 'file_start':
    case 'file':
      return '📄';
    default:
      return '📍';
  }
};

const getStatusStyle = (status?: string): string => {
  switch (status) {
    case 'completed':
      return 'text-green-600 bg-green-100 border-green-300';
    case 'error':
      return 'text-red-600 bg-red-100 border-red-300';
    case 'running':
      return 'text-blue-600 bg-blue-100 border-blue-300 animate-pulse';
    case 'waiting':
      return 'text-gray-500 bg-gray-100 border-gray-300';
    default:
      return 'text-gray-600 bg-gray-50 border-gray-200';
  }
};

const formatTimestamp = (timestamp?: string): string => {
  if (!timestamp) return '';
  
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch {
    return timestamp;
  }
};

export const ProgressTimeline: React.FC<ProgressTimelineProps> = ({
  steps,
  currentFile,
  className = ''
}) => {
  if (!steps.length) {
    return (
      <div className={`bg-gray-50 border rounded-lg p-4 ${className}`}>
        <div className="text-gray-500 text-sm text-center">
          No progress steps yet...
        </div>
      </div>
    );
  }

  const currentFileSteps = currentFile 
    ? steps.filter(step => !step.file || step.file === currentFile)
    : steps;

  return (
    <div className={`bg-white border rounded-lg overflow-hidden ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 bg-gray-50 border-b">
        <div className="flex items-center justify-between">
          <h4 className="font-semibold text-gray-800 flex items-center">
            ⚡ Progress Timeline
          </h4>
          {currentFile && (
            <span className="text-xs font-mono text-gray-600 bg-gray-200 px-2 py-1 rounded">
              {currentFile}
            </span>
          )}
        </div>
      </div>

      {/* Timeline */}
      <div className="p-4">
        <div className="space-y-3">
          {currentFileSteps.map((step, index) => {
            const isLast = index === currentFileSteps.length - 1;
            const isActive = step.status === 'running';
            
            return (
              <div key={index} className="flex items-start space-x-3">
                {/* Timeline connector */}
                <div className="flex flex-col items-center">
                  <div className={`
                    w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm
                    ${getStatusStyle(step.status)}
                  `}>
                    {getStageIcon(step.stage, step.status)}
                  </div>
                  {!isLast && (
                    <div className={`
                      w-0.5 h-6 mt-1
                      ${isActive ? 'bg-blue-300' : 'bg-gray-200'}
                    `} />
                  )}
                </div>

                {/* Step content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-gray-800 capitalize">
                        {step.stage}
                      </span>
                      {step.status && (
                        <span className={`
                          text-xs px-2 py-0.5 rounded-full font-medium
                          ${
                            step.status === 'completed' ? 'bg-green-100 text-green-700' :
                            step.status === 'error' ? 'bg-red-100 text-red-700' :
                            step.status === 'running' ? 'bg-blue-100 text-blue-700' :
                            'bg-gray-100 text-gray-600'
                          }
                        `}>
                          {step.status}
                        </span>
                      )}
                    </div>
                    
                    {step.timestamp && (
                      <span className="text-xs text-gray-500 font-mono">
                        {formatTimestamp(step.timestamp)}
                      </span>
                    )}
                  </div>
                  
                  <p className="text-sm text-gray-600 mt-1">
                    {step.message}
                  </p>
                  
                  {step.file && step.file !== currentFile && (
                    <div className="mt-1">
                      <span className="text-xs font-mono text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                        📄 {step.file}
                      </span>
                    </div>
                  )}

                  {step.progress !== undefined && (
                    <div className="mt-2">
                      <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                        <span>Progress</span>
                        <span>{step.progress}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1.5">
                        <div 
                          className={`
                            h-1.5 rounded-full transition-all duration-300
                            ${step.status === 'error' ? 'bg-red-500' : 'bg-blue-500'}
                          `}
                          style={{ width: `${step.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Active indicator for running refactor */}
        {steps.some(step => step.status === 'running') && (
          <div className="mt-4 flex items-center space-x-2 text-sm text-blue-600">
            <div className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full" />
            <span>Refactor in progress...</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProgressTimeline;