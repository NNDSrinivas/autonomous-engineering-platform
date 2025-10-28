/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CORE_API: string;
  readonly VITE_ORG_ID: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
