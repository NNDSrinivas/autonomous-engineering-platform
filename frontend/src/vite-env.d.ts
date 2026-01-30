/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CORE_API: string;
  readonly VITE_ORG_ID: string;
  readonly VITE_USER_ROLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
