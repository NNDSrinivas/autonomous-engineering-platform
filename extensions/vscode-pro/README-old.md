# AEP Agent Pro - VS Code Extension

A professional-grade autonomous engineering assistant that integrates seamlessly with VS Code to provide AI-powered development workflows.

## Features

🤖 **AI-Powered Chat Interface**
- Interactive chat assistant with workspace context awareness
- Real-time code analysis and suggestions
- Multi-session support with conversation history

📋 **Execution Plan Management**
- Step-by-step execution plans with approval workflow
- Visual plan viewer with file change previews
- Approve/reject individual steps for complete control

🔐 **Secure Authentication**
- OAuth 2.0 device flow integration with Auth0
- Persistent session management
- Enterprise-grade security

🔄 **Workspace Integration**
- Automatic file context detection
- Language-aware assistance
- Selection-based code analysis

## Quick Start

1. **Install the Extension**
   - Install from VS Code Marketplace or load as development extension

2. **Sign In**
   - Click the AEP icon in the Activity Bar
   - Select "Sign In" and follow the device flow authentication
   - Enter the provided code at the authentication URL

3. **Start Chatting**
   - Use the AI Assistant view to ask questions and get code help
   - The assistant automatically understands your current workspace context

4. **Review Execution Plans**
   - When the assistant suggests changes, review them in the Execution Plan view
   - Approve or reject individual steps
   - Files are automatically opened for review

## Extension Views

### Authentication View
- Shows connection status to AEP platform
- Handles sign-in/sign-out workflow
- Displays user account information

### AI Assistant View  
- Interactive chat interface
- Send messages and receive AI responses
- New session management
- Workspace context integration

### Execution Plan View
- Visual representation of proposed changes
- Step-by-step approval workflow
- File change previews
- Rejection reason tracking

## Commands

- **AEP: Focus Chat** - Focus the chat interface
- **AEP: New Chat Session** - Start a fresh conversation
- **AEP: Sign In** - Authenticate with AEP platform
- **AEP: Sign Out** - Sign out and clear session
- **AEP: Approve Step** - Approve current execution step
- **AEP: Reject Step** - Reject current execution step

## Configuration

```json
{
  "aep.apiUrl": "http://localhost:8001",
  "aep.autoFocusOnAuth": true,
  "aep.enableTelemetry": true
}
```

## Requirements

- VS Code 1.89.0 or higher
- Active AEP platform backend (running on configured API URL)
- Network access for authentication and API calls

## Architecture

This extension follows modern VS Code extension patterns:

- **Webview Providers** - Custom UI views with modern styling
- **Authentication Service** - OAuth 2.0 device flow implementation  
- **API Client** - Type-safe backend communication
- **Status Management** - Real-time status updates
- **Context Management** - Workspace state tracking

## Development

```bash
# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Watch mode for development
npm run watch

# Package extension
npm run package
```

## Security

- All authentication uses OAuth 2.0 device flow
- JWT tokens are securely stored in VS Code's secret storage
- No credentials are stored in plain text
- API communication uses HTTPS in production

## Support

For issues, feature requests, or questions:
- GitHub Issues: [Repository Issues](https://github.com/navralabs/autonomous-engineering-platform/issues)
- Documentation: [AEP Docs](http://localhost:3000)

## License

MIT License - See LICENSE file for details.

---

**Built with ❤️ by Navra Labs**