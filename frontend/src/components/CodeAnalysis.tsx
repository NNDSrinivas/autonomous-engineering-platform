import React, { useState } from 'react'

const CodeAnalysis: React.FC = () => {
  const [code, setCode] = useState('')
  const [analysis, setAnalysis] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const analyzeCode = async () => {
    if (!code.trim()) return
    
    setLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/analyze-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          language: 'python',
          analysis_type: 'quality'
        })
      })
      const result = await response.json()
      setAnalysis(result)
    } catch (error) {
      console.error('Analysis failed:', error)
      setAnalysis({ error: 'Failed to analyze code' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            AI Code Analysis
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Code to Analyze
              </label>
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                rows={10}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                placeholder="Paste your code here..."
              />
            </div>
            
            <button
              onClick={analyzeCode}
              disabled={loading || !code.trim()}
              className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
            >
              {loading ? '🔍 Analyzing...' : '🔍 Analyze Code'}
            </button>
          </div>
        </div>
      </div>

      {analysis && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Analysis Results
            </h3>
            
            {analysis.error ? (
              <div className="text-red-600 p-4 bg-red-50 rounded-lg">
                {analysis.error}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-blue-800 font-medium">Quality Score</div>
                    <div className="text-2xl font-bold text-blue-900">8.5/10</div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-green-800 font-medium">Complexity</div>
                    <div className="text-2xl font-bold text-green-900">Low</div>
                  </div>
                  <div className="bg-yellow-50 p-4 rounded-lg">
                    <div className="text-yellow-800 font-medium">Issues Found</div>
                    <div className="text-2xl font-bold text-yellow-900">2</div>
                  </div>
                </div>
                
                <div className="mt-6">
                  <h4 className="font-medium text-gray-900 mb-3">🤖 AI Suggestions</h4>
                  <ul className="space-y-2">
                    <li className="flex items-start space-x-2">
                      <span className="text-yellow-500">⚠️</span>
                      <span className="text-sm text-gray-700">Consider adding type hints for better code clarity</span>
                    </li>
                    <li className="flex items-start space-x-2">
                      <span className="text-blue-500">💡</span>
                      <span className="text-sm text-gray-700">This function could be optimized using list comprehension</span>
                    </li>
                    <li className="flex items-start space-x-2">
                      <span className="text-green-500">✅</span>
                      <span className="text-sm text-gray-700">Good use of error handling and logging</span>
                    </li>
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default CodeAnalysis
