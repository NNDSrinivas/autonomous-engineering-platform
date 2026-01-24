// Mock Supabase client for compatibility
// Replace with actual Supabase integration if needed

type Subscription = {
  unsubscribe: () => void;
};

type AuthChangeCallback = (event: string, session: MockSession | null) => void;

interface MockSession {
  user: {
    id: string;
    email?: string;
  };
  access_token: string;
}

interface MockQueryBuilder {
  eq: (_column: string, _value: unknown) => MockQueryBuilder;
  single: () => Promise<{ data: null; error: null }>;
  data: null;
  error: null;
}

const createQueryBuilder = (): MockQueryBuilder => {
  const builder: MockQueryBuilder = {
    eq: () => builder,
    single: () => Promise.resolve({ data: null, error: null }),
    data: null,
    error: null,
  };
  return builder;
};

export const supabase = {
  from: (_table: string) => ({
    select: (_columns?: string) => createQueryBuilder(),
    insert: (_data: unknown) => ({
      data: null,
      error: null,
    }),
    update: (_data: unknown) => ({
      eq: (_column: string, _value: unknown) => ({
        data: null,
        error: null,
      }),
      data: null,
      error: null,
    }),
    upsert: (_data: unknown, _options?: { onConflict?: string }) => ({
      data: null,
      error: null,
    }),
    delete: () => ({
      eq: (_column: string, _value: unknown) => ({
        data: null,
        error: null,
      }),
      data: null,
      error: null,
    }),
  }),
  auth: {
    getUser: () => ({
      data: { user: null as MockSession['user'] | null },
      error: null,
    }),
    getSession: () => Promise.resolve({
      data: { session: null as MockSession | null },
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
