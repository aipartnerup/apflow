# CLI Configuration Management

## Overview

The CLI configuration system supports both project-local and user-global configuration. Configuration is stored in two separate files for security:

- **`config.json`** (644 permissions) - Non-sensitive settings
- **`secrets.json`** (600 permissions, owner-only) - Sensitive credentials

## Multi-Location Priority System

Configuration can be stored in multiple locations with the following priority (highest to lowest):

1. **Environment Variable**: `APFLOW_CONFIG_DIR` (highest priority)
2. **Project-Local**: `.data/` directory in project root
3. **User-Global**: `~/.aipartnerup/apflow/` directory
4. **Default**: Current working directory (if no other location found)

When you save configuration, it goes to the active location determined by this priority system.

## File Structure

### config.json (Non-Sensitive)

Non-sensitive configuration like API server URL:

```json
{
  "api_server": "http://localhost:8000",
  "api_timeout": 30,
  "api_retry_count": 3,
  "auto_use_api_if_configured": true
}
```

**Permissions**: `644` (owner: read/write, group: read, others: read)

**Who can read**: Everyone on the system  
**Who can write**: Owner only

### secrets.json (Sensitive)

Sensitive credentials stored separately:

```json
{
  "api_auth_token": "your-jwt-token-here",
  "jwt_secret": "your-jwt-secret-here"
}
```

**Permissions**: `600` (owner: read/write, group: none, others: none)

**Who can read**: Owner only  
**Who can write**: Owner only

## Configuration Commands

### View Configuration Locations

```bash
apflow config path
```

Example output:
```
Configuration Locations (in priority order):
1. APFLOW_CONFIG_DIR env var:  Not set
2. Project-local (.data/):     /home/user/project/.data/
3. User-global (~/.aipartnerup/apflow/):  ~/.aipartnerup/apflow/
4. Current directory:          /home/user/project

Active location: /home/user/project/.data/
```

### Initialize Configuration (Quick Setup)

```bash
apflow config init-server
```

This command:
1. Creates `.data/config.json` in project (if not exists)
2. Creates `.data/secrets.json` with JWT secret (if not exists)
3. Sets `api_server` to `http://localhost:8000`
4. Shows all file paths for verification

Example output:
```
Configuration initialized successfully:
  Config:  .data/config.json (644)
  Secrets: .data/secrets.json (600)
  API Server: http://localhost:8000
  JWT Secret: Generated and saved
```

### Set Configuration Value

```bash
# Set non-sensitive value
apflow config set api_server http://api.example.com

# Set sensitive value
apflow config set api_auth_token my-secret-token --sensitive
```

### Generate JWT Token

```bash
apflow config gen-token --role admin --save
```

This command:
1. Generates a new JWT token
2. Saves to `secrets.json` (with 600 permissions)
3. Shows token value for reference

Options:
- `--role <role>` - User role (default: user)
- `--user-id <id>` - User ID (optional)
- `--save` - Save to secrets.json

## Environment Variables

### APFLOW_CONFIG_DIR

Override default configuration directory:

```bash
# Save configuration to a specific directory
export APFLOW_CONFIG_DIR=/custom/config/path
apflow config init-server

# Unset to use default priority system
unset APFLOW_CONFIG_DIR
```

This is useful for:
- Docker/container deployments (use mounted volumes)
- Testing (isolated config directories)
- CI/CD pipelines (centralized config)

### DATABASE_URL

Specify database connection (optional):

```bash
# Use default DuckDB
# (no DATABASE_URL needed)

# Use PostgreSQL
export DATABASE_URL="postgresql+asyncpg://user:password@localhost/apflow"
apflow run flow --tasks '[...]'
```

## Configuration Loading

### How CLI Loads Configuration

When you run CLI commands, configuration is loaded from:

1. **Check APFLOW_CONFIG_DIR** - If set, load from here first
2. **Check project-local** - If `.data/config.json` exists, load from here
3. **Check user-global** - If `~/.aipartnerup/apflow/config.json` exists, load from here
4. **Use defaults** - If nothing found, use built-in defaults

Configuration is merged, so you can have:
- `config.json` in project-local
- `secrets.json` in user-global
- CLI will load both and merge them

### How API Server Loads Configuration

The API server uses the same multi-location system via `core/config_manager.py`:

```python
from apflow.cli.cli_config import load_cli_config, load_secrets_config

# API loads from multi-location system
config = load_cli_config()
secrets = load_secrets_config()
```

## Configuration Scenarios

### Scenario 1: Quick Local Development

No configuration needed - just use CLI:

```bash
cd ~/my-project
apflow run flow --tasks '[{"id": "t1", "name": "Task 1", "schemas": {"method": "system_info_executor"}, "inputs": {"resource": "cpu"}}]'
```

Database is created automatically in `~/.aipartnerup/data/apflow.duckdb`

### Scenario 2: Multi-Project Setup

Use project-local configuration to keep settings separate:

```bash
# Project A
cd ~/project-a
apflow config init-server
# Creates .data/config.json and .data/secrets.json in project-a

# Project B
cd ~/project-b
apflow config init-server
# Creates .data/config.json and .data/secrets.json in project-b
```

Each project has its own isolated configuration.

### Scenario 3: Team Shared Configuration

Use user-global configuration for shared settings:

```bash
# Set up once in home directory
apflow config set api_server http://team-api.example.com
# Saves to ~/.aipartnerup/apflow/config.json

# Now use from any project
cd ~/project-a
apflow run flow --tasks '[...]'
# Automatically uses ~/.aipartnerup/apflow/config.json
```

All team members share the same API server.

### Scenario 4: Docker/Container Deployment

Use environment variable for isolated configuration:

```bash
# In Dockerfile or docker-compose.yml
ENV APFLOW_CONFIG_DIR=/etc/apflow/config

# Run container
docker run -v /etc/apflow/config:/etc/apflow/config my-app

# Or in docker-compose.yml
environment:
  - APFLOW_CONFIG_DIR=/config
volumes:
  - ./config:/config
```

Configuration comes from mounted volume.

### Scenario 5: CI/CD Pipeline

Use environment variables for pipeline-specific configuration:

```bash
# In GitHub Actions workflow
env:
  APFLOW_CONFIG_DIR: ./.github/config
  API_AUTH_TOKEN: ${{ secrets.API_AUTH_TOKEN }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: apflow config set api_auth_token $API_AUTH_TOKEN --sensitive
      - run: apflow run flow --tasks '[...]'
```

Configuration is isolated per pipeline run.

## Command Reference

### apflow config path

Show all configuration locations:

```bash
apflow config path
```

### apflow config init-server

Quick setup for API server:

```bash
apflow config init-server [--api-server <url>]
```

### apflow config set

Set a configuration value:

```bash
apflow config set <key> <value> [--sensitive]
```

Examples:
```bash
apflow config set api_server http://api.example.com
apflow config set api_timeout 60
apflow config set api_auth_token my-secret --sensitive
```

### apflow config gen-token

Generate JWT token:

```bash
apflow config gen-token [--role <role>] [--user-id <id>] [--save]
```

Examples:
```bash
# Generate and show token
apflow config gen-token --role admin

# Generate and save to secrets.json
apflow config gen-token --role admin --user-id user123 --save
```

## File Permissions Explanation

### Why 644 for config.json?

- **Readable by others**: System services, monitoring tools, or other users on the system may need to know the API server URL
- **No secrets**: Only non-sensitive settings like `api_server` URL, timeouts, etc.
- **Easier debugging**: Other processes can read config to troubleshoot connectivity issues

### Why 600 for secrets.json?

- **Owner only**: Sensitive credentials must not be readable by other users
- **No compromise**: If a service is compromised, it cannot read other users' credentials
- **Security principle**: Secrets are isolated per user

### On macOS/Linux

Check permissions:
```bash
ls -la ~/.aipartnerup/apflow/
# Output:
# -rw-r--r-- 1 user group config.json
# -rw------- 1 user group secrets.json
```

Manually fix permissions (if needed):
```bash
chmod 644 ~/.aipartnerup/apflow/config.json
chmod 600 ~/.aipartnerup/apflow/secrets.json
```

## Best Practices

### 1. Use Multi-Location System

Let CLI manage configuration locations:

```bash
# ✅ Good: Use default system
cd ~/my-project
apflow config init-server

# ❌ Avoid: Hardcoding paths
export APFLOW_CONFIG_DIR=/tmp/config
```

### 2. Keep Secrets in secrets.json

Never put secrets in config.json:

```bash
# ❌ Bad: API token in config.json
apflow config set api_auth_token my-secret

# ✅ Good: Use --sensitive flag
apflow config set api_auth_token my-secret --sensitive
```

### 3. Use Project-Local for Team Settings

Each project has its own configuration:

```bash
# ✅ Good: Project-specific config
cd ~/project-a
apflow config set api_server http://project-a-api.com

cd ~/project-b
apflow config set api_server http://project-b-api.com
```

### 4. Use User-Global for Common Settings

Shared settings across all projects:

```bash
# ✅ Good: Shared config in ~/.aipartnerup/apflow/
apflow config set api_retry_count 5
# Now all projects use this value
```

### 5. Verify Configuration Before Using

Check active configuration:

```bash
apflow config path
# Shows which location is being used
```

## Troubleshooting

### Problem: "Configuration file not found"

**Solution**: Initialize configuration:
```bash
apflow config init-server
```

### Problem: "Permission denied on secrets.json"

**Solution**: Check permissions:
```bash
ls -la ~/.aipartnerup/apflow/secrets.json
# Should show: -rw------- (600)

# Fix if needed:
chmod 600 ~/.aipartnerup/apflow/secrets.json
```

### Problem: "API server URL not working"

**Solution**: Verify configuration:
```bash
apflow config path
apflow config set api_server http://correct-url.com
```

### Problem: "Multiple configuration files exist"

**Solution**: Check priority order:
```bash
apflow config path
# Shows all locations and which one is active
```

Suggestion: Keep configuration in one location to avoid confusion.

### Problem: "Different config per machine"

**Solution**: Use environment variable:
```bash
# On development machine
export APFLOW_CONFIG_DIR=~/.apflow-dev

# On production machine
export APFLOW_CONFIG_DIR=/etc/apflow
```

## Summary

- ✅ Configuration stored in 2 files (config.json + secrets.json)
- ✅ Multi-location support (project-local + user-global)
- ✅ Environment variable override (APFLOW_CONFIG_DIR)
- ✅ Proper file permissions (644 + 600)
- ✅ Easy commands to initialize and manage
- ✅ Shared between CLI and API server

Configuration is flexible enough for both local development and production deployment.
