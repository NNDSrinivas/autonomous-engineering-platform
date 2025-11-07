# Changelog

All notable changes to the AEP Autonomous Engineering Agent extension will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-rc1] - 2025-11-06

### Breaking Changes
- **Complete extension rewrite with modern architecture**
- **REMOVED: agent-core module dependency** 
  - Removed `baseUrl` and `paths` configuration in tsconfig.json for agent-core imports
  - All `agent-core/*` import paths are no longer valid
  - Extension now uses direct backend API integration instead of agent-core abstraction
  - Migration: Replace agent-core imports with direct API calls to backend services
- **New Enhanced Chat Panel with improved UI/UX**
- **Updated authentication flow with OAuth device code**
- **Modernized webview implementation with VS Code UI Toolkit**

### Added
- Enhanced chat panel with JIRA integration
- Modern landing page design with professional styling
- Improved error handling and XSS protection
- OAuth device code authentication flow
- Real-time communication capabilities
- Type-safe API response handling

### Changed
- **MAJOR VERSION BUMP**: Upgraded from 0.1.0 to 1.0.0-rc1
- Complete architectural overhaul justifies major version increase
- Significant breaking changes in extension API and structure
- Updated VS Code engine requirement to ^1.84.0
- Improved TypeScript configuration and type safety

### Security
- Enhanced XSS protection in chat panel
- Secure OAuth device code implementation
- Input sanitization and validation improvements

### Technical Notes
This major version bump reflects the complete rewrite of the extension architecture.
The significant changes include removal of legacy dependencies, modernized codebase,
and enhanced security measures, warranting the jump to version 1.0.0-rc1.