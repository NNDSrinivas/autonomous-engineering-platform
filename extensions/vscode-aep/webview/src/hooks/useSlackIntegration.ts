import { useState, useEffect } from 'react';

export interface SlackMessage {
  id: string;
  text: string;
  user: string;
  timestamp: string;
  channel: string;
}

export interface SlackIntegrationState {
  messages: SlackMessage[];
  loading: boolean;
  error: string | null;
  connected: boolean;
}

export function useSlackIntegration() {
  const [state, setState] = useState<SlackIntegrationState>({
    messages: [],
    loading: false,
    error: null,
    connected: false,
  });

  useEffect(() => {
    // Mock Slack integration
    setState({
      messages: [
        {
          id: '1',
          text: 'Good morning! Ready for today\'s standup?',
          user: 'john.doe',
          timestamp: new Date().toISOString(),
          channel: '#general'
        },
        {
          id: '2',
          text: 'The deployment went smoothly yesterday.',
          user: 'jane.smith',
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          channel: '#engineering'
        }
      ],
      loading: false,
      error: null,
      connected: true,
    });
  }, []);

  return state;
}