import React from 'react';
import ConciergeGreeting from '../components/concierge/ConciergeGreeting';

const ConciergePage: React.FC = () => {
  const handleActionClick = (action: string, data?: any) => {
    console.log('Action clicked:', action, data);
    
    // Handle different actions
    switch (action) {
      case 'open_wallpaper_settings':
        console.log('Opening wallpaper settings...');
        break;
      case 'create_jira_ticket':
        console.log('Creating JIRA ticket...');
        break;
      case 'start_focus_session':
        console.log('Starting focus session...');
        break;
      case 'join_standup':
        console.log('Joining standup...');
        break;
      case 'view_docs':
        console.log('Opening documentation...');
        break;
      default:
        console.log('Unhandled action:', action);
    }
  };

  return (
    <div className="w-full h-screen">
      <ConciergeGreeting 
        onActionClick={handleActionClick}
        className="bg-gray-100"
      />
    </div>
  );
};

export default ConciergePage;