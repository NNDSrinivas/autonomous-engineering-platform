import { useState, useEffect } from 'react';

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  description?: string;
  attendees?: string[];
}

export interface CalendarIntegrationState {
  events: CalendarEvent[];
  loading: boolean;
  error: string | null;
  connected: boolean;
}

export function useCalendarIntegration() {
  const [state, setState] = useState<CalendarIntegrationState>({
    events: [],
    loading: false,
    error: null,
    connected: false,
  });

  useEffect(() => {
    // Mock Calendar integration
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    setState({
      events: [
        {
          id: '1',
          title: 'Daily Standup',
          start: new Date(today.setHours(9, 0, 0, 0)).toISOString(),
          end: new Date(today.setHours(9, 30, 0, 0)).toISOString(),
          description: 'Team sync and updates',
          attendees: ['john.doe@example.com', 'jane.smith@example.com']
        },
        {
          id: '2',
          title: 'Sprint Planning',
          start: new Date(tomorrow.setHours(14, 0, 0, 0)).toISOString(),
          end: new Date(tomorrow.setHours(15, 30, 0, 0)).toISOString(),
          description: 'Plan next sprint tasks',
          attendees: ['team@example.com']
        }
      ],
      loading: false,
      error: null,
      connected: true,
    });
  }, []);

  return state;
}