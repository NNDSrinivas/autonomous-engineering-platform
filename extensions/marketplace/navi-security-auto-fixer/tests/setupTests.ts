/**
 * Jest setup file for Security Auto-Fixer tests
 */

// Mock console methods to avoid noise in test output
const originalConsole = global.console;

beforeAll(() => {
    global.console = {
        ...originalConsole,
        // Suppress logs during tests unless explicitly needed
        log: jest.fn(),
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn()
    };
});

afterAll(() => {
    global.console = originalConsole;
});

// Global test timeout
jest.setTimeout(10000);

// Mock external dependencies that aren't available in test environment
jest.mock('fs', () => ({
    readFileSync: jest.fn(),
    writeFileSync: jest.fn(),
    existsSync: jest.fn(() => true),
    promises: {
        readFile: jest.fn(),
        writeFile: jest.fn()
    }
}));

jest.mock('path', () => ({
    join: jest.fn((...args) => args.join('/')),
    resolve: jest.fn((...args) => '/' + args.join('/')),
    basename: jest.fn((path) => path.split('/').pop()),
    dirname: jest.fn((path) => path.split('/').slice(0, -1).join('/'))
}));

// Use real semver behavior for dependency version checks
jest.mock('semver', () => jest.requireActual('semver'));

// Add custom matchers if needed
expect.extend({
    toBeSecurityFinding(received) {
        const requiredFields = ['id', 'title', 'description', 'severity', 'type', 'confidence', 'source'];
        const missingFields = requiredFields.filter(field => !(field in received));

        if (missingFields.length > 0) {
            return {
                message: () => `Expected object to have security finding fields: ${missingFields.join(', ')}`,
                pass: false
            };
        }

        return {
            message: () => 'Expected object not to be a valid security finding',
            pass: true
        };
    },

    toBeValidRemediationProposal(received) {
        const requiredFields = ['type', 'description', 'confidence', 'effort', 'risk', 'changes', 'testing', 'rollback'];
        const missingFields = requiredFields.filter(field => !(field in received));

        if (missingFields.length > 0) {
            return {
                message: () => `Expected object to have remediation proposal fields: ${missingFields.join(', ')}`,
                pass: false
            };
        }

        return {
            message: () => 'Expected object not to be a valid remediation proposal',
            pass: true
        };
    }
});

// Extend Jest matchers TypeScript definitions
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeSecurityFinding(): R;
      toBeValidRemediationProposal(): R;
    }
  }
}

// Ensure this file is treated as a module
export {};
