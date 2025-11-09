# 🚀 AEP Professional – AI Engineering Partner for VS Code

**AEP (Autonomous Engineering Platform)** is your on-device AI engineering partner that brings contextual intelligence, automation, and safe code execution right inside Visual Studio Code.

> 💡 **Version:** 2.0.0  
> 🔗 **Custom Domain:** [auth.navralabs.com](https://auth.navralabs.com)  
> 🏢 **Publisher:** Navra Labs  
> 🧠 **Core Tech:** Auth0 • OpenAI GPT-4o • VS Code Webview UI Toolkit • TypeScript

---

## ✨ Features

| Capability | Description |
|-------------|-------------|
| 🧩 **Context-Aware Coding** | Understands your repositories, JIRA issues, and GitHub PRs in real time. |
| 🧭 **AI Planning Engine** | Converts natural-language goals into structured engineering plans. |
| 🧪 **Safe Action Mode** | The agent only applies changes after your approval. |
| 🔐 **Secure Auth0 Login** | Enterprise-ready authentication with your custom domain `auth.navralabs.com`. |
| 🧰 **Integrated Tools** | Seamless integration with VS Code commands, terminal, and source control. |
| 💬 **Smart Chat Interface (Coming Soon)** | Chat with your project-aware AI mentor within VS Code. |

---

## 🧑‍💻 Getting Started

### 1. Install the Extension
Search **"AEP Professional"** in the VS Code Extensions Marketplace and click **Install**.

Or manually:
```bash
code --install-extension aep-professional-dev-2.0.0.vsix
```

### 2. Sign In Securely

Open the **AEP** panel in the sidebar → click **"Sign in with Auth0"**
Your browser will redirect to the secure Navra Labs authentication page.

### 3. Connect Your Workspace

AEP automatically detects your project structure and configures context packs.
You can also manually set credentials via **Settings → AEP**.

---

## 🧠 Inside AEP

| Component          | Description                                                        |
| ------------------ | ------------------------------------------------------------------ |
| **Agent Panel**    | The main control hub with session overview and real-time status.   |
| **Plan & Act**     | AI-generated, reviewable code execution plans.                     |
| **Settings Panel** | Update Auth0 config, model preferences, and project context paths. |
| **History Panel**  | Review previous AI sessions and approved actions.                  |

---

## 🛡️ Privacy & Security

* Authentication via **Auth0** (custom domain `auth.navralabs.com`).
* No source code leaves your system without consent.
* All actions are user-approved and logged locally.
* Optional enterprise integration available for team rollout.

---

## 🧩 Tech Stack

* **Frontend:** VS Code Webview UI Toolkit
* **Backend:** TypeScript / Node
* **Auth:** Auth0 (custom domain)
* **AI Model:** GPT-4o, Claude Sonnet (configurable)

---

## 🧭 Roadmap

* [ ] AI Mentor Chat with persistent project memory
* [ ] Multi-organization workspace switching
* [ ] GitHub Actions + JIRA sync integration
* [ ] Agent sandbox execution
* [ ] In-editor AI diff explanations

---

## 🤝 Contributing

We welcome early feedback and ideas!
Fork the repo, build locally, and run the extension via VS Code's **"Run Extension"** mode.

---

## ⚙️ Commands Overview

| Command                | Action                         |
| ---------------------- | ------------------------------ |
| `AEP: Sign In`         | Initiates Auth0 authentication |
| `AEP: Start Session`   | Begins a contextual AI session |
| `AEP: Open Settings`   | Opens configuration panel      |
| `AEP: Sign Out`        | Signs out of current session   |

---

## 🧾 License

[MIT License](./LICENSE) © 2025 Navra Labs

---

### 🧠 Connect With Us

* 🌐 Website: [https://navralabs.com](https://navralabs.com)
* 🧑‍🚀 Founder: [Niranjan N.](https://linkedin.com/in/nnd-srinivas)
* 📧 Contact: [hello@navralabs.com](mailto:hello@navralabs.com)