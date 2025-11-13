#!/usr/bin/env python3
"""Generate frontend auth_config.json from environment variables

This script creates the frontend Auth0 configuration by substituting
environment variables into the template, keeping sensitive credentials
out of the repository.

Usage:
    python scripts/generate_frontend_config.py

Environment Variables Required:
    AUTH0_DOMAIN: Auth0 custom domain (e.g., auth.navralabs.com)
    AUTH0_CLIENT_ID: Auth0 application client ID
    AUTH0_AUDIENCE: Auth0 API audience (e.g., https://api.navralabs.com)
"""

import json
import os
import sys
from pathlib import Path
from string import Template


def load_env_file():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    try:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip("'\"")  # Remove surrounding quotes
                        if key and value:  # Only set non-empty values
                            os.environ[key] = value
                    except ValueError:
                        # Skip malformed lines
                        continue


def generate_frontend_config():
    """Generate auth_config.json from template and environment variables"""

    # Load .env file first
    load_env_file()

    # Required environment variables
    required_vars = {
        "AUTH0_DOMAIN": os.getenv("AUTH0_DOMAIN"),
        "AUTH0_CLIENT_ID": os.getenv("AUTH0_CLIENT_ID"),
        "AUTH0_AUDIENCE": os.getenv("AUTH0_AUDIENCE"),
    }

    # Check for missing variables
    missing = [key for key, value in required_vars.items() if not value]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("\nPlease set these in your .env file or environment:")
        for var in missing:
            print(f"  {var}=your_value_here")
        sys.exit(1)

    # Load template
    template_path = (
        Path(__file__).parent.parent / "frontend" / "auth_config.template.json"
    )
    output_path = Path(__file__).parent.parent / "frontend" / "auth_config.json"

    if not template_path.exists():
        print(f"❌ Template not found: {template_path}")
        sys.exit(1)

    # Read and substitute template
    with open(template_path) as f:
        template_content = f.read()

    template = Template(template_content)
    config_content = template.substitute(required_vars)

    # Validate JSON
    try:
        config = json.loads(config_content)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON generated: {e}")
        sys.exit(1)

    # Write output with pretty formatting
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")  # Add newline at end

    print("✅ Generated frontend configuration:")
    print(f"   Template: {template_path}")
    print(f"   Output:   {output_path}")
    print(f"   Domain:   {config['auth0Domain']}")
    print(f"   Client:   {config['clientId'][:8]}***")
    print(f"   Audience: {config['audience']}")


if __name__ == "__main__":
    generate_frontend_config()
