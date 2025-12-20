import React from 'react';

// Risk level type definition
export type RiskLevel = 'minimal' | 'low' | 'medium' | 'high' | 'critical';

// Risk factor interface
export interface RiskFactor {
  factor: string;
  score: number;
  reasoning: string;
  category: string;
  examples: string[];
}

// Risk assessment interface
export interface RiskAssessment {
  overall_risk: RiskLevel;
  risk_score: number;
  confidence_score: number;
  requires_review: boolean;
  safe_to_auto_apply: boolean;
  factors: RiskFactor[];
  impact_analysis: {
    files_affected: number;
    lines_added: number;
    risk_categories: Record<string, string[]>;
    highest_risk_factor: string | null;
    critical_areas: string[];
    affected_systems: string[];
  };
  recommendations: string[];
}

// Props interfaces
interface RiskBadgeProps {
  risk: RiskLevel;
  score: number;
  className?: string;
}

interface ConfidenceMeterProps {
  score: number;
  className?: string;
}

interface RiskAssessmentPanelProps {
  assessment: RiskAssessment;
  className?: string;
}

interface RiskFactorListProps {
  factors: RiskFactor[];
  className?: string;
}

interface RecommendationsListProps {
  recommendations: string[];
  className?: string;
}

/**
 * Enterprise Risk Badge Component
 * Displays color-coded risk level with score
 */
export const RiskBadge: React.FC<RiskBadgeProps> = ({ risk, score, className = '' }) => {
  const getRiskConfig = (riskLevel: RiskLevel) => {
    switch (riskLevel) {
      case 'minimal':
        return {
          bg: 'bg-green-100',
          text: 'text-green-800',
          border: 'border-green-300',
          icon: '✅',
          label: 'Minimal Risk'
        };
      case 'low':
        return {
          bg: 'bg-blue-100',
          text: 'text-blue-800',
          border: 'border-blue-300',
          icon: 'ℹ️',
          label: 'Low Risk'
        };
      case 'medium':
        return {
          bg: 'bg-yellow-100',
          text: 'text-yellow-800',
          border: 'border-yellow-300',
          icon: '⚠️',
          label: 'Medium Risk'
        };
      case 'high':
        return {
          bg: 'bg-orange-100',
          text: 'text-orange-800',
          border: 'border-orange-300',
          icon: '🔶',
          label: 'High Risk'
        };
      case 'critical':
        return {
          bg: 'bg-red-100',
          text: 'text-red-800',
          border: 'border-red-300',
          icon: '🚨',
          label: 'Critical Risk'
        };
      default:
        return {
          bg: 'bg-gray-100',
          text: 'text-gray-800',
          border: 'border-gray-300',
          icon: '❓',
          label: 'Unknown Risk'
        };
    }
  };

  const config = getRiskConfig(risk);
  const percentage = Math.round(score * 100);

  return (
    <div className={`inline-flex items-center px-3 py-1 rounded-full border ${config.bg} ${config.text} ${config.border} ${className}`}>
      <span className="mr-1 text-sm">{config.icon}</span>
      <span className="font-medium text-sm">{config.label}</span>
      <span className="ml-2 text-xs opacity-75">({percentage}%)</span>
    </div>
  );
};

/**
 * Confidence Meter Component
 * Visual gauge showing AI confidence in the risk assessment
 */
export const ConfidenceMeter: React.FC<ConfidenceMeterProps> = ({ score, className = '' }) => {
  const percentage = Math.round(score * 100);
  
  const getConfidenceColor = (score: number) => {
    if (score >= 0.9) return 'bg-green-500';
    if (score >= 0.7) return 'bg-blue-500';
    if (score >= 0.5) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getConfidenceLabel = (score: number) => {
    if (score >= 0.9) return 'Very High';
    if (score >= 0.7) return 'High';
    if (score >= 0.5) return 'Medium';
    return 'Low';
  };

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      <div className="flex flex-col">
        <div className="text-xs text-gray-600 mb-1">Confidence</div>
        <div className="flex items-center space-x-2">
          {/* Progress bar */}
          <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-300 ${getConfidenceColor(score)}`}
              style={{ width: `${percentage}%` }}
            />
          </div>
          <span className="text-xs font-medium text-gray-700">
            {getConfidenceLabel(score)} ({percentage}%)
          </span>
        </div>
      </div>
    </div>
  );
};

/**
 * Risk Factor List Component
 * Displays detailed breakdown of risk factors
 */
export const RiskFactorList: React.FC<RiskFactorListProps> = ({ factors, className = '' }) => {
  return (
    <div className={`space-y-3 ${className}`}>
      <h4 className="font-semibold text-gray-800 text-sm">Risk Factors</h4>
      {factors.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No specific risk factors identified</p>
      ) : (
        <div className="space-y-2">
          {factors.map((factor, index) => {
            const severityColor = factor.score >= 0.8 ? 'text-red-600' :
                                 factor.score >= 0.6 ? 'text-orange-600' :
                                 factor.score >= 0.4 ? 'text-yellow-600' : 'text-blue-600';
            
            return (
              <div key={index} className="border-l-3 border-gray-300 pl-3 py-1">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium text-gray-800">
                        {factor.factor.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </span>
                      <span className={`text-xs font-semibold ${severityColor}`}>
                        {Math.round(factor.score * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mt-1">{factor.reasoning}</p>
                    {factor.examples.length > 0 && (
                      <div className="mt-1">
                        <details className="group">
                          <summary className="text-xs text-blue-600 cursor-pointer hover:text-blue-800">
                            View examples ({factor.examples.length})
                          </summary>
                          <div className="mt-1 ml-2 space-y-1">
                            {factor.examples.slice(0, 3).map((example, exIndex) => (
                              <code key={exIndex} className="block text-xs bg-gray-100 p-1 rounded">
                                {example}
                              </code>
                            ))}
                          </div>
                        </details>
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                    {factor.category}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

/**
 * Recommendations List Component
 * Shows actionable recommendations based on risk assessment
 */
export const RecommendationsList: React.FC<RecommendationsListProps> = ({ recommendations, className = '' }) => {
  return (
    <div className={`space-y-2 ${className}`}>
      <h4 className="font-semibold text-gray-800 text-sm">Recommendations</h4>
      {recommendations.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No specific recommendations</p>
      ) : (
        <ul className="space-y-2">
          {recommendations.map((recommendation, index) => (
            <li key={index} className="flex items-start space-x-2">
              <span className="text-blue-500 text-xs mt-1">→</span>
              <span className="text-sm text-gray-700 flex-1">{recommendation}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

/**
 * Complete Risk Assessment Panel
 * Enterprise-grade risk visualization with all components
 */
export const RiskAssessmentPanel: React.FC<RiskAssessmentPanelProps> = ({ assessment, className = '' }) => {
  const {
    overall_risk,
    risk_score,
    confidence_score,
    requires_review,
    safe_to_auto_apply,
    factors,
    impact_analysis,
    recommendations
  } = assessment;

  return (
    <div className={`bg-white border border-gray-200 rounded-lg p-4 space-y-4 ${className}`}>
      {/* Header with risk badge and confidence */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <RiskBadge risk={overall_risk} score={risk_score} />
          <ConfidenceMeter score={confidence_score} />
        </div>
        <div className="flex items-center space-x-2">
          {safe_to_auto_apply && (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-green-100 text-green-800">
              ✅ Safe Auto-Apply
            </span>
          )}
          {requires_review && (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-orange-100 text-orange-800">
              👀 Review Required
            </span>
          )}
        </div>
      </div>

      {/* Impact summary */}
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="font-semibold text-gray-800 text-sm mb-2">Impact Analysis</h4>
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-gray-600">Files Affected:</span>
            <span className="ml-2 font-medium">{impact_analysis.files_affected}</span>
          </div>
          <div>
            <span className="text-gray-600">Lines Added:</span>
            <span className="ml-2 font-medium">{impact_analysis.lines_added}</span>
          </div>
          <div>
            <span className="text-gray-600">Systems:</span>
            <span className="ml-2 font-medium">{impact_analysis.affected_systems.join(', ') || 'None'}</span>
          </div>
          <div>
            <span className="text-gray-600">Critical Areas:</span>
            <span className="ml-2 font-medium">{impact_analysis.critical_areas.length}</span>
          </div>
        </div>
      </div>

      {/* Expandable sections */}
      <div className="space-y-3">
        {factors.length > 0 && (
          <details className="group">
            <summary className="cursor-pointer font-medium text-sm text-gray-700 hover:text-gray-900">
              Risk Factors ({factors.length}) {factors.some(f => f.score > 0.7) && '🔥'}
            </summary>
            <div className="mt-2">
              <RiskFactorList factors={factors} />
            </div>
          </details>
        )}

        {recommendations.length > 0 && (
          <details className="group">
            <summary className="cursor-pointer font-medium text-sm text-gray-700 hover:text-gray-900">
              Recommendations ({recommendations.length})
            </summary>
            <div className="mt-2">
              <RecommendationsList recommendations={recommendations} />
            </div>
          </details>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex justify-end space-x-2 pt-2 border-t border-gray-200">
        <button className="px-3 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50">
          View Details
        </button>
        {safe_to_auto_apply ? (
          <button className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700">
            Apply Safely
          </button>
        ) : (
          <button className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">
            Review & Apply
          </button>
        )}
      </div>
    </div>
  );
};

/**
 * Compact Risk Indicator for List Items
 * Minimal risk display for file listings
 */
export const CompactRiskIndicator: React.FC<{ risk: RiskLevel; score: number; className?: string }> = ({ 
  risk, 
  score, 
  className = '' 
}) => {
  const getRiskIcon = (riskLevel: RiskLevel) => {
    switch (riskLevel) {
      case 'minimal': return '🟢';
      case 'low': return '🔵';
      case 'medium': return '🟡';
      case 'high': return '🟠';
      case 'critical': return '🔴';
      default: return '⚪';
    }
  };

  return (
    <span 
      className={`inline-flex items-center space-x-1 ${className}`}
      title={`${risk} risk (${Math.round(score * 100)}%)`}
    >
      <span className="text-sm">{getRiskIcon(risk)}</span>
    </span>
  );
};