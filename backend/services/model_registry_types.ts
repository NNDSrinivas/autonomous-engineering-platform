export type RegistryEnvironment = "dev" | "staging" | "prod";
export type ModelProvider =
  | "openai"
  | "anthropic"
  | "google"
  | "groq"
  | "azure-openai"
  | "ollama"
  | "self_hosted";
export type GovernanceTier = "premium" | "standard" | "budget";
export type ModelCapability =
  | "chat"
  | "tool-use"
  | "json"
  | "vision"
  | "code"
  | "reasoning"
  | "long-context"
  | "streaming";

export interface ModelPricing {
  currency: "USD";
  inputPer1KTokens: number;
  outputPer1KTokens: number;
}

export interface ModelLimits {
  maxInputTokens: number;
  maxOutputTokens: number;
}

export interface ModelGovernance {
  tier: GovernanceTier;
  allowedEnvironments: RegistryEnvironment[];
  tags?: string[];
}

export interface ModelDeprecation {
  status: "active" | "deprecated" | "disabled";
  sunsetAt?: string;
  replacementModelId?: string;
}

export interface ModelHealthCheck {
  enabled: boolean;
  timeoutMs?: number;
}

export interface ModelRegistryEntry {
  id: string;
  provider: ModelProvider;
  displayName: string;
  enabled: boolean;
  productionApproved: boolean;
  deprecation?: ModelDeprecation;
  capabilities: ModelCapability[];
  pricing: ModelPricing;
  limits: ModelLimits;
  governance: ModelGovernance;
  healthCheck?: ModelHealthCheck;
}

export interface ModelRegistryFile {
  schemaVersion: number;
  environment: RegistryEnvironment;
  generatedAt?: string;
  models: ModelRegistryEntry[];
}
