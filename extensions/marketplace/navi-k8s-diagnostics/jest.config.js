module.exports = {
    preset: 'ts-jest',
    testEnvironment: 'node',
    testMatch: [
        '**/tests/**/*.test.ts'
    ],
    collectCoverageFrom: [
        '**/*.ts',
        '!**/node_modules/**',
        '!**/dist/**',
        '!**/tests/**',
        '!jest.config.js',
        '!**/scripts/**'
    ],
    coverageReporters: [
        'text',
        'lcov',
        'html'
    ],
    coverageThreshold: {
        global: {
            branches: 80,
            functions: 80,
            lines: 80,
            statements: 80
        }
    },
    setupFilesAfterEnv: [],
    testTimeout: 10000,
    verbose: true
};