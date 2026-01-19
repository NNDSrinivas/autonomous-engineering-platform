// Mock Supabase client for compatibility
// Replace with actual Supabase integration if needed

type Subscription = {
  unsubscribe: () => void;
};

type AuthChangeCallback = (event: string, session: null) => void;

export const supabase = {
  from: (_table: string) => ({
    select: (_columns?: string) => ({
      eq: (_column: string, _value: unknown) => ({
        single: () => Promise.resolve({
          data: null,
          error: null,
        }),
        data: null,
        error: null,
      }),
      data: null,
      error: null,
    }),
    insert: (_data: unknown) => ({
      data: null,
      error: null,
    }),
    update: (_data: unknown) => ({
      data: null,
      error: null,
    }),
    delete: () => ({
      data: null,
      error: null,
    }),
  }),
  auth: {
    getUser: () => ({
      data: { user: null },
      error: null,
    }),
    getSession: () => Promise.resolve({
      data: { session: null },
      error: null,
    }),
    onAuthStateChange: (_callback: AuthChangeCallback): { data: { subscription: Subscription } } => ({
      data: {
        subscription: {
          unsubscribe: () => {},
        },
      },
    }),
    signInWithPassword: (_credentials: { email: string; password: string }) => ({
      data: null,
      error: null,
    }),
    signUp: (_credentials: { email: string; password: string }) => ({
      data: null,
      error: null,
    }),
    signOut: () => ({
      error: null,
    }),
  },
};