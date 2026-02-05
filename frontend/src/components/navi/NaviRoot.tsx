import React, { useState, useEffect } from 'react'
import NaviChatPanel from './NaviChatPanel'
import { NaviActionsBar } from './NaviActionsBar'
import { QuickActionsBar } from './QuickActionsBar'
import { ApprovalDialog } from './ApprovalDialog'
import { TaskCorrelationPanel } from './TaskCorrelationPanel'
import { EndToEndWorkflowPanel } from './EndToEndWorkflowPanel'
import { NaviApprovalPanel } from './NaviApprovalPanel'
import { NaviCheckErrorsAndFixPanel } from './NaviCheckErrorsAndFixPanel'

interface NaviRootProps {
  initialInput?: string
}

const NaviRoot: React.FC<NaviRootProps> = ({ initialInput = '' }) => {
  const [currentMode, setCurrentMode] = useState<'chat' | 'workflow' | 'approval' | 'errorcheck'>('chat')
  // Mock task for demo
  const mockTask = {
    id: '1',
    key: 'DEMO-123',
    title: 'Example task for workflow demonstration'
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white p-4">
        <h1 className="text-xl font-semibold text-gray-900">NAVI Assistant</h1>
        <p className="text-sm text-gray-600 mt-1">Autonomous Engineering Intelligence Platform</p>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Primary Panel */}
        <div className="flex-1 flex flex-col p-6">
          {currentMode === 'chat' && (
            <NaviChatPanel />
          )}
          
          {currentMode === 'workflow' && (
            <EndToEndWorkflowPanel task={mockTask} />
          )}
          
          {currentMode === 'approval' && (
            <NaviApprovalPanel />
          )}
          
          {currentMode === 'errorcheck' && (
            <NaviCheckErrorsAndFixPanel />
          )}
        </div>

        {/* Side Panel */}
        <div className="w-80 border-l border-gray-200 bg-white p-4">
          <h3 className="font-medium text-gray-900 mb-4">Quick Actions</h3>
          <div className="space-y-2">
            <button 
              onClick={() => setCurrentMode('chat')}
              className={`w-full text-left p-3 rounded-lg transition-colors ${
                currentMode === 'chat' 
                  ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                  : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              💬 Chat Mode
            </button>
            <button 
              onClick={() => setCurrentMode('workflow')}
              className={`w-full text-left p-3 rounded-lg transition-colors ${
                currentMode === 'workflow' 
                  ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                  : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              ⚡ Workflow Mode
            </button>
            <button 
              onClick={() => setCurrentMode('approval')}
              className={`w-full text-left p-3 rounded-lg transition-colors ${
                currentMode === 'approval' 
                  ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                  : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              ✅ Approval Panel
            </button>
            <button 
              onClick={() => setCurrentMode('errorcheck')}
              className={`w-full text-left p-3 rounded-lg transition-colors ${
                currentMode === 'errorcheck' 
                  ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                  : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              🔍 Error Check
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default NaviRoot