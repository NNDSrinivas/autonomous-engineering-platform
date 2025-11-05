import React from 'react';
import SimpleConcierge from '../components/concierge/SimpleConcierge';

const ConciergePage: React.FC = () => {
  return (
    <div className="flex justify-center bg-gray-900 min-h-screen">
      <SimpleConcierge />
    </div>
  );
};

export default ConciergePage;