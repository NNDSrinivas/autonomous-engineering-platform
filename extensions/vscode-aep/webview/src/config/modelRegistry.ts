import registryJson from "@shared/model-registry.json";

export type ProviderType = "saas" | "local" | "self_hosted";

export type RegistryModel = {
  id: string;
  name: string;
  description?: string;
  providerModel?: string;
  capabilities?: {
    streaming?: boolean;
    tools?: boolean;
    json?: boolean;
    vision?: boolean;
    search?: boolean;
  };
};

export type RegistryProvider = {
  id: string;
  label: string;
  type: ProviderType;
  models: RegistryModel[];
};

export type NaviMode = {
  id: string;
  label: string;
  description?: string;
  candidateModelIds: string[];
  policy?: {
    strictPrivate?: boolean;
  };
};

export type ModelRegistry = {
  version: string;
  defaults: {
    defaultModeId: string;
    defaultModelId: string;
  };
  naviModes: NaviMode[];
  providers: RegistryProvider[];
};

export type ModelOption = {
  id: string;
  name: string;
  description?: string;
};

export type ProviderGroup = {
  id: string;
  name: string;
  models: ModelOption[];
};

export const MODEL_REGISTRY: ModelRegistry = registryJson as ModelRegistry;

export const NAVI_MODELS: ModelOption[] = MODEL_REGISTRY.naviModes.map((mode) => ({
  id: mode.id,
  name: mode.label,
  description: mode.description,
}));

export const ADVANCED_PROVIDER_GROUPS: ProviderGroup[] = MODEL_REGISTRY.providers
  .filter((provider) => provider.type === "saas")
  .map((provider) => ({
    id: provider.id,
    name: provider.label,
    models: provider.models.map((model) => ({
      id: model.id,
      name: model.name,
      description: model.description,
    })),
  }));

export const LEGACY_MODEL_PROVIDER_GROUPS: ProviderGroup[] = [
  {
    id: "navi",
    name: "NAVI",
    models: NAVI_MODELS,
  },
  ...ADVANCED_PROVIDER_GROUPS,
];

const MODEL_LOOKUP = new Map<string, RegistryModel>();
for (const provider of MODEL_REGISTRY.providers) {
  for (const model of provider.models) {
    MODEL_LOOKUP.set(model.id, model);
  }
}

for (const mode of MODEL_REGISTRY.naviModes) {
  MODEL_LOOKUP.set(mode.id, {
    id: mode.id,
    name: mode.label,
    description: mode.description,
  });
}

export const getRegistryModel = (modelId: string): RegistryModel | null => {
  return MODEL_LOOKUP.get(modelId) || null;
};

export const getRegistryModelLabel = (modelId: string): string => {
  return getRegistryModel(modelId)?.name || modelId;
};
