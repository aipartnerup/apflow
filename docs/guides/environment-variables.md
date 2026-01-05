# Environment Variables Reference

This document describes all environment variables used by apflow.

## Naming Convention

apflow follows a consistent naming pattern for environment variables:

- **Preferred**: Variables with `APFLOW_` prefix (e.g., `APFLOW_LOG_LEVEL`)
- **Fallback**: Generic names without prefix (e.g., `LOG_LEVEL`)

When both are set, `APFLOW_*` variables take precedence. This design allows apflow to:
- Run in multi-service environments without conflicts
- Integrate with existing systems that use generic variable names
- Maintain clear ownership of configuration

## Core Configuration

### Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_DATABASE_URL` | string | auto-detected | Database connection string. Takes precedence over `DATABASE_URL` |
| `DATABASE_URL` | string | auto-detected | Fallback database connection string |

**Priority for DuckDB file location:**
1. `APFLOW_DATABASE_URL` or `DATABASE_URL` (if set)
2. `.data/apflow.duckdb` (if exists in project)
3. `~/.aipartnerup/data/apflow.duckdb` (if exists, legacy)
4. `.data/apflow.duckdb` (default for new projects)
5. `~/.aipartnerup/data/apflow.duckdb` (default outside projects)

**Examples:**
```bash
# PostgreSQL
APFLOW_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/apflow

# Custom DuckDB path
APFLOW_DATABASE_URL=duckdb:///path/to/custom.duckdb

# Using generic fallback
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/apflow
```

### Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_LOG_LEVEL` | string | INFO | Log level for apflow. Takes precedence over `LOG_LEVEL` |
| `LOG_LEVEL` | string | INFO | Fallback log level |

**Valid values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Examples:**
```bash
# Use apflow-specific log level
APFLOW_LOG_LEVEL=DEBUG

# Or generic fallback
LOG_LEVEL=INFO
```

### API Server

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_API_HOST` | string | 0.0.0.0 | API server host address. Takes precedence over `API_HOST` |
| `API_HOST` | string | 0.0.0.0 | Fallback API host |
| `APFLOW_API_PORT` | integer | 8000 | API server port. Takes precedence over `API_PORT` |
| `API_PORT` | integer | 8000 | Fallback API port |
| `APFLOW_BASE_URL` | string | auto | Base URL for API service |
| `APFLOW_API_PROTOCOL` | string | a2a | API protocol type: `a2a` or `mcp` |

**Examples:**
```bash
# Use apflow-specific configuration
APFLOW_API_HOST=127.0.0.1
APFLOW_API_PORT=9000
APFLOW_API_PROTOCOL=mcp

# Or generic fallback
API_HOST=0.0.0.0
API_PORT=8000
```

### Security

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_JWT_SECRET` | string | - | Secret key for JWT token signing |
| `APFLOW_JWT_ALGORITHM` | string | HS256 | JWT signing algorithm |

**Example:**
```bash
APFLOW_JWT_SECRET=your-secret-key-here
APFLOW_JWT_ALGORITHM=HS256
```

### CORS

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_CORS_ORIGINS` | string | * | Comma-separated allowed CORS origins |
| `APFLOW_CORS_ALLOW_ALL` | boolean | false | Allow all CORS origins |

**Examples:**
```bash
# Specific origins
APFLOW_CORS_ORIGINS=http://localhost:3000,https://app.example.com

# Allow all (development only)
APFLOW_CORS_ALLOW_ALL=true
```

### API Features

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_ENABLE_SYSTEM_ROUTES` | boolean | true | Enable system information routes |
| `APFLOW_ENABLE_DOCS` | boolean | true | Enable API documentation routes |

### CLI Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_CONFIG_DIR` | string | auto-detected | Override CLI config directory location |

**Default locations (priority order):**
1. `APFLOW_CONFIG_DIR` (if set)
2. `.data/` (if in project)
3. `~/.aipartnerup/apflow/`

## Storage Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_MAX_SESSIONS` | integer | 10 | Maximum concurrent storage sessions |
| `APFLOW_SESSION_TIMEOUT` | integer | 300 | Session timeout in seconds |
| `APFLOW_TASK_TABLE_NAME` | string | tasks | Custom task table name |
| `APFLOW_TASK_MODEL_CLASS` | string | - | Custom task model class path |

## Extensions

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_EXTENSIONS` | string | - | Comma-separated extension names to load |
| `APFLOW_LLM_PROVIDER` | string | - | LLM provider for AI extensions |

**Example:**
```bash
APFLOW_EXTENSIONS=llm,docker,http
APFLOW_LLM_PROVIDER=openai
```

## Extension-Specific Variables

### STDIO Extension

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_STDIO_ALLOW_COMMAND` | boolean | false | Allow arbitrary command execution |
| `APFLOW_STDIO_COMMAND_WHITELIST` | string | - | Comma-separated allowed commands |

**Example:**
```bash
APFLOW_STDIO_ALLOW_COMMAND=true
APFLOW_STDIO_COMMAND_WHITELIST=echo,ls,cat
```

### Daemon

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_DAEMON_PID_FILE` | string | auto | Custom daemon PID file location |
| `APFLOW_DAEMON_LOG_FILE` | string | auto | Custom daemon log file location |

## Development & Testing

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APFLOW_DEMO_SLEEP_SCALE` | float | 1.0 | Scale factor for demo sleep times |

**Example:**
```bash
# Speed up demos by 10x
APFLOW_DEMO_SLEEP_SCALE=0.1
```

## Third-Party Service Keys

These variables follow the standard naming conventions of third-party services and should **not** have `APFLOW_` prefix:

| Variable | Service | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | OpenAI | API key for OpenAI services |
| `OPENAI_MODEL` | OpenAI | Default OpenAI model name |
| `ANTHROPIC_API_KEY` | Anthropic | API key for Anthropic services |
| `ANTHROPIC_MODEL` | Anthropic | Default Anthropic model name |

**Example:**
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-opus-20240229
```

## Complete Example

Here's a complete `.env` file example:

```env
# Database (choose one)
APFLOW_DATABASE_URL=duckdb:///.data/apflow.duckdb
# APFLOW_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/apflow

# Logging
APFLOW_LOG_LEVEL=INFO

# API Server
APFLOW_API_HOST=0.0.0.0
APFLOW_API_PORT=8000
APFLOW_API_PROTOCOL=a2a

# Security
APFLOW_JWT_SECRET=your-secret-key-change-in-production
APFLOW_JWT_ALGORITHM=HS256

# CORS (adjust for production)
APFLOW_CORS_ORIGINS=http://localhost:3000,https://app.example.com

# Features
APFLOW_ENABLE_SYSTEM_ROUTES=true
APFLOW_ENABLE_DOCS=true

# LLM Services (if using AI extensions)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
```

## Best Practices

1. **Use `.env` file**: Store environment variables in a `.env` file in your project root
2. **Never commit secrets**: Add `.env` to `.gitignore`
3. **Use APFLOW_ prefix**: Prefer `APFLOW_*` variables for better isolation
4. **Document overrides**: When using generic fallbacks, document why
5. **Validate in production**: Always validate required variables are set in production

## Priority Summary

When multiple configuration sources exist, apflow follows this priority:

1. **Environment variables with APFLOW_ prefix** (highest)
2. **Generic environment variables** (fallback)
3. **CLI config files** (`.data/` or `~/.aipartnerup/apflow/`)
4. **Default values** (lowest)

This allows maximum flexibility while maintaining sensible defaults.

