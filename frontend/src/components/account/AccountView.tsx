import { useState } from "react";
import "./AccountView.css";

declare global {
    const acquireVsCodeApi:
        | undefined
        | (() => { postMessage: (msg: any) => void });
}

const vscodeApi =
    typeof acquireVsCodeApi === "function" ? acquireVsCodeApi() : null;

interface ProviderKey {
    provider: "openai" | "anthropic";
    label: string;
    apiKey: string;
}

const INITIAL_KEYS: ProviderKey[] = [
    { provider: "openai", label: "OpenAI", apiKey: "" },
    { provider: "anthropic", label: "Anthropic", apiKey: "" },
];

export default function AccountView() {
    const [keys, setKeys] = useState<ProviderKey[]>(INITIAL_KEYS);

    const handleKeyChange = (provider: string, value: string) => {
        setKeys((prev) =>
            prev.map((k) =>
                k.provider === provider ? { ...k, apiKey: value } : k
            )
        );
    };

    const handleSave = () => {
        vscodeApi?.postMessage({
            type: "navi.saveByokKeys",
            payload: keys.reduce<Record<string, string>>((acc, k) => {
                if (k.apiKey.trim()) acc[k.provider] = k.apiKey.trim();
                return acc;
            }, {}),
        });
        alert("BYOK settings sent to extension to save (wire backend as needed).");
    };

    return (
        <div className="navi-settings-root">
            <div className="navi-settings-header">
                <h2 className="navi-settings-title">Account & API keys</h2>
                <p className="navi-settings-subtitle">
                    Configure how Navi identifies you and which model keys it can use.
                </p>
            </div>

            <div className="navi-settings-section">
                <h3 className="navi-settings-section-title">Profile</h3>
                <p className="navi-settings-text">
                    (Later you can show org / email / role pulled from VS Code or SSO.)
                </p>
            </div>

            <div className="navi-settings-section">
                <h3 className="navi-settings-section-title">BYOK (Bring Your Own Key)</h3>
                <p className="navi-settings-text">
                    These keys are only used when you select{" "}
                    <code>BYOK (your key)</code> as the provider in the chat mode strip.
                </p>

                <div className="navi-settings-grid">
                    {keys.map((k) => (
                        <div key={k.provider} className="navi-settings-card">
                            <div className="navi-settings-card-title">{k.label}</div>
                            <input
                                type="password"
                                className="navi-settings-input"
                                placeholder={`${k.label} API key`}
                                value={k.apiKey}
                                onChange={(e) =>
                                    handleKeyChange(k.provider, e.target.value)
                                }
                            />
                            <p className="navi-settings-help">
                                Stored in the extension/local secure storage (wire in backend).
                            </p>
                        </div>
                    ))}
                </div>

                <button
                    type="button"
                    className="navi-settings-save-btn"
                    onClick={handleSave}
                >
                    Save BYOK settings
                </button>
            </div>
        </div>
    );
}
