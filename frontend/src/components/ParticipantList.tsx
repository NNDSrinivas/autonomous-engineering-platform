/**
 * ParticipantList - Display list of participants
 */

import React from 'react';

interface ParticipantListProps {
  list: string[];
}

export const ParticipantList: React.FC<ParticipantListProps> = ({ list }) => {
  if (list.length === 0) {
    return (
      <div className="text-sm text-gray-500">
        No participants yet
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {list.map((participant, idx) => (
        <span
          key={idx}
          className="px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full text-xs font-medium"
        >
          👤 {participant}
        </span>
      ))}
    </div>
  );
};
