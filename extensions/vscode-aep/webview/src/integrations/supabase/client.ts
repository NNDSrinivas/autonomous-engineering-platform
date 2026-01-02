// Mock Supabase client for compatibility
// Replace with actual Supabase integration if needed

export const supabase = {
  from: (table: string) => ({
    select: () => ({
      data: null,
      error: null,
    }),
    insert: () => ({
      data: null,
      error: null,
    }),
    update: () => ({
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
    signInWithPassword: () => ({
      data: null,
      error: null,
    }),
    signUp: () => ({
      data: null,
      error: null,
    }),
    signOut: () => ({
      error: null,
    }),
  },
};