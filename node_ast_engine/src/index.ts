#!/usr/bin/env node
/**
 * Node AST Engine - Entry Point
 * Production-grade CLI interface for Python to call AST transformations
 * 
 * Usage: echo '{"command":"renameSymbol", ...}' | node dist/index.js
 */

const { runTransform } = require("./runner");

async function main() {
  try {
    const input = await readStdin();
    
    if (!input.trim()) {
      throw new Error("No input provided. Expected JSON payload via stdin.");
    }

    let payload;
    try {
      payload = JSON.parse(input);
    } catch (e) {
      throw new Error(`Invalid JSON input: ${e instanceof Error ? e.message : String(e)}`);
    }

    // Validate required fields
    if (!payload.command) {
      throw new Error("Missing required field: command");
    }
    if (!payload.filePath) {
      throw new Error("Missing required field: filePath");  
    }
    if (!payload.code) {
      throw new Error("Missing required field: code");
    }

    const result = await runTransform(payload);
    
    // Ensure we output valid JSON
    process.stdout.write(JSON.stringify(result, null, 2));
    
  } catch (error) {
    const errorResponse = {
      success: false,
      error: error instanceof Error ? error.message : String(error),
      timestamp: new Date().toISOString()
    };
    
    process.stderr.write(JSON.stringify(errorResponse, null, 2));
    process.exit(1);
  }
}

function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    
    // Set timeout to prevent hanging
    const timeout = setTimeout(() => {
      reject(new Error("Timeout waiting for stdin input"));
    }, 30000); // 30 second timeout
    
    process.stdin.setEncoding("utf8");
    
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    
    process.stdin.on("end", () => {
      clearTimeout(timeout);
      resolve(data);
    });
    
    process.stdin.on("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
  });
}

// Handle uncaught errors gracefully
process.on('uncaughtException', (error) => {
  const errorResponse = {
    success: false,
    error: `Uncaught exception: ${error.message}`,
    stack: error.stack,
    timestamp: new Date().toISOString()
  };
  
  process.stderr.write(JSON.stringify(errorResponse, null, 2));
  process.exit(1);
});

process.on('unhandledRejection', (reason) => {
  const errorResponse = {
    success: false,
    error: `Unhandled rejection: ${String(reason)}`,
    timestamp: new Date().toISOString()
  };
  
  process.stderr.write(JSON.stringify(errorResponse, null, 2));
  process.exit(1);
});

main();