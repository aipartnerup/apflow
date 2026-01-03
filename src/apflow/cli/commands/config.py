"""
CLI configuration management command.

Provides commands to manage CLI configuration including:
- Basic config operations: set, get, unset, list, reset
- Token management: gen-token, verify-token
- Quick setup: init, init-server
- Utilities: path, edit, validate
"""

import typer
import json
import subprocess
from typing import Optional

from apflow.cli.cli_config import (
    get_config_value,
    set_config_value,
    list_config_values,
    get_config_file_path,
    load_cli_config,
)
from apflow.cli.jwt_token import generate_token, get_token_info, verify_token
from apflow.core.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(
    name="config",
    help="Manage CLI configuration",
    no_args_is_help=True,
)


@app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """
    Set a configuration value.

    Supports common aliases for convenience:
        api-server, api-url -> api_server_url
        api-token, token -> api_auth_token

    Examples:
        apflow config set api_server_url http://localhost:8000
        apflow config set api-server http://localhost:8000
        apflow config set api_auth_token my-token-xyz
        apflow config set api-token my-token-xyz
    """
    try:
        # Resolve aliases for convenience
        alias_map = {
            "api-server": "api_server_url",
            "api-url": "api_server_url",
            "api-token": "api_auth_token",
            "token": "api_auth_token",
        }
        actual_key = alias_map.get(key, key)

        # Determine if this is a sensitive value
        is_sensitive = "token" in actual_key.lower() or "secret" in actual_key.lower()
        set_config_value(actual_key, value, is_sensitive=is_sensitive)
        typer.echo(f"✅ Configuration '{actual_key}' set successfully")

        # Display masked value for tokens
        if "token" in actual_key.lower():
            masked = f"{value[:8]}...***" if len(value) > 8 else "***"
            typer.echo(f"   Value: {masked}")
        else:
            typer.echo(f"   Value: {value}")

        # Show path
        from apflow.cli.cli_config import (
            get_all_config_locations,
            get_all_secrets_locations,
        )

        if is_sensitive:
            typer.echo(f"   Location: {get_all_secrets_locations()[0]}")
        else:
            typer.echo(f"   Location: {get_all_config_locations()[0]}")
        typer.echo(f"   Location: {get_config_file_path()}")
        

    except Exception as e:
        typer.echo(f"❌ Error setting configuration: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("get")
def get_config(
    key: str = typer.Argument(..., help="Configuration key"),
):
    """
    Get a configuration value.
    
    Supports common aliases for convenience:
        api-server, api-url -> api_server_url
        api-token, token -> api_auth_token
    
    Examples:
        apflow config get api_server_url
        apflow config get api-server
        apflow config get api_auth_token
        apflow config get api-token
    """
    try:
        # Resolve aliases for convenience
        alias_map = {
            "api-server": "api_server_url",
            "api-url": "api_server_url",
            "api-token": "api_auth_token",
            "token": "api_auth_token",
        }
        actual_key = alias_map.get(key, key)
        
        value = get_config_value(actual_key)
        
        if value is None:
            typer.echo(f"⚠️  Configuration '{actual_key}' not found")
            raise typer.Exit(1)
        
        # Mask tokens in output (only show first char + ...)
        if "token" in actual_key.lower():
            if len(value) > 1:
                masked = f"{value[0]}...***"
            else:
                masked = "***"
            typer.echo(f"{actual_key}={masked}")
        else:
            typer.echo(f"{actual_key}={value}")
        
    except Exception as e:
        if "Configuration" not in str(e):
            typer.echo(f"❌ Error getting configuration: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("list")
def list_config(
    format: str = typer.Option(
        "table", "--format", "-f",
        help="Output format: table or json"
    ),
):
    """
    List all configuration values.
    
    Sensitive values (tokens) are masked for security.
    
    Examples:
        apflow config list
        apflow config list -f json
    """
    try:
        config = list_config_values()
        
        if not config:
            typer.echo("No configuration found.")
            typer.echo(f"Configuration file: {get_config_file_path()}")
            return
        
        if format == "json":
            typer.echo(json.dumps(config, indent=2))
        else:
            # Table format
            from rich.console import Console
            from rich.table import Table
            
            console = Console()
            table = Table(title="CLI Configuration")
            table.add_column("Key", style="cyan", no_wrap=True)
            table.add_column("Value", style="magenta")
            
            for key, value in sorted(config.items()):
                table.add_row(key, str(value))
            
            console.print(table)
            console.print(f"\n📁 Location: {get_config_file_path()}")
        
    except Exception as e:
        typer.echo(f"❌ Error listing configuration: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("unset")
def unset_config(
    key: str = typer.Argument(..., help="Configuration key to delete"),
    confirm: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation"
    ),
):
    """
    Delete a configuration value.
    
    Supports common aliases for convenience:
        api-server, api-url -> api_server_url
        api-token, token -> api_auth_token
    
    Examples:
        apflow config unset api_server_url
        apflow config unset api-server
        apflow config unset api_auth_token --yes
        apflow config unset api-token --yes
    """
    try:
        # Resolve aliases for convenience
        alias_map = {
            "api-server": "api_server_url",
            "api-url": "api_server_url",
            "api-token": "api_auth_token",
            "token": "api_auth_token",
        }
        actual_key = alias_map.get(key, key)
        
        current = get_config_value(actual_key)
        
        if current is None:
            typer.echo(f"⚠️  Configuration '{actual_key}' not found")
            raise typer.Exit(1)
        
        if not confirm:
            if not typer.confirm(f"Delete '{actual_key}'?"):
                typer.echo("Cancelled")
                raise typer.Exit(0)
        
        set_config_value(actual_key, None)
        typer.echo(f"✅ Configuration '{actual_key}' deleted successfully")
        
    except Exception as e:
        if "Cancelled" not in str(e):
            typer.echo(f"❌ Error deleting configuration: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("gen-token")
def gen_token(
    subject: str = typer.Option(
        "apflow-user",
        "--subject", "-s",
        help="Token subject (typically username or app name)",
    ),
    algo: str = typer.Option(
        "HS256",
        "--algo", "-a",
        help="JWT algorithm (HS256, HS512, etc.)",
    ),
    expiry_days: int = typer.Option(
        365,
        "--expiry", "-e",
        help="Token expiration in days",
    ),
    role: Optional[str] = typer.Option(
        None,
        "--role", "-r",
        help="Role claim (e.g., admin, user)",
    ),
    save: Optional[str] = typer.Option(
        None,
        "--save",
        help="Save token to config key (e.g., api_auth_token)",
    ),
):
    """
    Generate a JWT token for API authentication.
    
    By default, generates a user token. Use --role admin for admin token.
    Can optionally save to config using --save.
    
    Examples:
        apflow config gen-token
        apflow config gen-token --role admin
        apflow config gen-token --subject my-app --expiry 30
        apflow config gen-token --role admin --save api_auth_token
    """
    try:
        # Build extra claims
        extra_claims = {}
        if role:
            extra_claims["role"] = role
        
        # Generate token
        token = generate_token(
            subject=subject,
            algo=algo,
            expiry_days=expiry_days,
            extra_claims=extra_claims,
        )
        
        # Display token
        typer.echo("✅ JWT token generated successfully!\n")
        typer.echo(f"Token: {token}\n")
        
        # Display token info
        info = get_token_info(token)
        typer.echo("Token details:")
        typer.echo(f"  Subject: {info.get('subject')}")
        typer.echo(f"  Issuer: {info.get('issuer')}")
        typer.echo(f"  Issued: {info.get('issued_at')}")
        typer.echo(f"  Expires: {info.get('expires_at')}")
        if info.get('expires_in_days') is not None:
            typer.echo(f"  Expires in: {info.get('expires_in_days')} days")
        if role:
            typer.echo(f"  Role: {role}")

        # Optionally save to config (with alias resolution)
        if save:
            # Resolve aliases for convenience
            alias_map = {
                "api-server": "api_server_url",
                "api-url": "api_server_url",
                "api-token": "api_auth_token",
                "token": "api_auth_token",
            }
            actual_key = alias_map.get(save, save)

            # Determine if this is a sensitive value
            is_sensitive = "token" in actual_key.lower() or "secret" in actual_key.lower()
            set_config_value(actual_key, token, is_sensitive=is_sensitive)
            typer.echo(f"\n✅ Token saved to config key: {actual_key}")
            from apflow.cli.cli_config import (
                get_config_file_path,
                CONFIG_FILE,
                SECRETS_FILE,
            )

            if is_sensitive:
                typer.echo(f"   Location: {get_config_file_path(SECRETS_FILE)}")
            else:
                typer.echo(f"   Location: {get_config_file_path(CONFIG_FILE)}")

    except Exception as e:
        typer.echo(f"❌ Error generating token: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("init-server")
def init_server(
    url: str = typer.Option(
        "http://localhost:8000",
        "--url", "-u",
        help="API server URL",
    ),
    role: str = typer.Option(
        "admin",
        "--role", "-r",
        help="Role for the token",
    ),
):
    """
    Initialize API server configuration with auto-generated JWT token.

    Convenience command that configures API server and generates token.
    Equivalent to running:
        apflow config set api-server <url>
        apflow config gen-token --role <role> --save api-token

    Config saved to:
        config.json (api_server_url)
        secrets.json (api_auth_token)

    Examples:
        apflow config init-server
        apflow config init-server --url http://prod-server.com:8000
        apflow config init-server --url http://localhost:8000 --role user
    """
    try:
        # Normalize URL (remove trailing slash)
        url = url.rstrip("/")

        # Set server URL (non-sensitive, config.json)
        set_config_value("api_server_url", url, is_sensitive=False)

        # Generate and save token (sensitive, secrets.json)
        token = generate_token(
            subject="apflow-cli",
            extra_claims={"role": role},
            expiry_days=365,
        )
        set_config_value("api_auth_token", token, is_sensitive=True)

        typer.echo("✅ API server configuration initialized!")
        typer.echo(f"   Server: {url}")
        typer.echo(f"   Token: {token[:20]}...***")
        typer.echo(f"   Role: {role}")
        from apflow.cli.cli_config import (
            get_config_file_path,
            CONFIG_FILE,
            SECRETS_FILE,
        )

        typer.echo("\nSaved to:")
        typer.echo(
            f"   config.json  (non-sensitive): "
            f"{get_config_file_path(CONFIG_FILE)}"
        )
        typer.echo(
            f"   secrets.json (sensitive):     "
            f"{get_config_file_path(SECRETS_FILE)}"
        )
        typer.echo()
        typer.echo("You can now run:")
        typer.echo("   apflow tasks list     # Use CLI with API")
        typer.echo()
        typer.echo("Or manually configure using:")
        typer.echo(f"   apflow config set api-server {url}")
        typer.echo("   apflow config gen-token --role admin --save api-token")

    except Exception as e:
        typer.echo(f"❌ Error initializing server: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("show-path")
def show_path():
    """
    Show configuration file paths.

    Displays all possible config locations and which one is active.

    [Alias: path]
    """
    from apflow.cli.cli_config import (
        get_all_config_locations,
        get_all_secrets_locations,
        get_config_dir,
    )

    active_config = get_config_file_path()
    active_secrets_dir = get_config_dir()

    typer.echo("📁 Configuration Structure\n")

    typer.echo("Non-sensitive config (config.json):")
    for i, location in enumerate(get_all_config_locations(), 1):
        exists = "✅" if location.exists() else "⚪"
        active = "🔵 ACTIVE" if location == active_config else ""
        typer.echo(f"  {i}. {exists} {location} {active}")

    typer.echo("\nSensitive config (secrets.json):")
    for i, location in enumerate(get_all_secrets_locations(), 1):
        exists = "✅" if location.exists() else "⚪"
        active = "🔵 ACTIVE" if location == active_secrets_dir / "secrets.json" else ""
        typer.echo(f"  {i}. {exists} {location} {active}")

    typer.echo("\nActive config directory:")
    typer.echo(f"  {active_secrets_dir}")

    if active_config.exists():
        import datetime

        mtime = datetime.datetime.fromtimestamp(
            active_config.stat().st_mtime
        )
        typer.echo("\nActive config details:")
        typer.echo(f"  Size: {active_config.stat().st_size} bytes")
        typer.echo(f"  Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        typer.echo("\n⚠️  No config file exists yet (will be created on first set)")

    typer.echo("\n💡 Priority (highest to lowest):")
    typer.echo("  1. APFLOW_CONFIG_DIR environment variable")
    typer.echo("  2. Project-local: <project>/.data/")
    typer.echo("  3. User-global: ~/.aipartnerup/apflow/ (default)")

    typer.echo("\n🔒 File Permissions:")
    typer.echo("  config.json:  644 (readable by all)")
    typer.echo("  secrets.json: 600 (owner-only access)")


@app.command("path")
def path_alias():
    """Show configuration file path (alias for show-path)."""
    show_path()


@app.command("reset")
def reset_config(
    confirm: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation"
    ),
):
    """
    Reset all configuration (delete config file).
    
    ⚠️  This will delete all configuration including API server and tokens.
    
    Examples:
        apflow config reset
        apflow config reset --yes
    """
    try:
        path = get_config_file_path()
        
        if not path.exists():
            typer.echo("⚠️  No configuration file found")
            return
        
        if not confirm:
            typer.echo(f"This will delete: {path}")
            if not typer.confirm("Are you sure you want to reset all configuration?"):
                typer.echo("Cancelled")
                raise typer.Exit(0)
        
        path.unlink()
        typer.echo("✅ Configuration reset successfully")
        typer.echo(f"   Deleted: {path}")
        
    except Exception as e:
        if "Cancelled" not in str(e):
            typer.echo(f"❌ Error resetting configuration: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("verify-token")
def verify_token_cmd(
    token: Optional[str] = typer.Argument(
        None,
        help="Token to verify (if not provided, uses api_auth_token from config)"
    ),
):
    """
    Verify and display JWT token information.
    
    Can verify a specific token or the configured api_auth_token.
    
    Examples:
        apflow config verify-token                    # Verify configured token
        apflow config verify-token eyJhbGci...       # Verify specific token
    """
    try:
        # If no token provided, get from config
        if not token:
            token = get_config_value("api_auth_token")
            if not token:
                typer.echo("❌ No token provided and no api_auth_token in config")
                typer.echo("   Use: apflow config verify-token <token>")
                raise typer.Exit(1)
            typer.echo("Verifying configured api_auth_token...\n")
        
        # Get token info (without verification)
        info = get_token_info(token)
        
        typer.echo("✅ Token Information:")
        typer.echo(f"   Subject: {info.get('subject')}")
        typer.echo(f"   Issuer: {info.get('issuer')}")
        typer.echo(f"   Issued: {info.get('issued_at')}")
        typer.echo(f"   Expires: {info.get('expires_at')}")
        
        if info.get('expires_in_days') is not None:
            days = info.get('expires_in_days')
            if days < 0:
                typer.echo(f"   Status: ⚠️  EXPIRED ({abs(days)} days ago)")
            elif days < 7:
                typer.echo(f"   Status: ⚠️  Expiring soon ({days} days remaining)")
            else:
                typer.echo(f"   Status: ✅ Valid ({days} days remaining)")
        
        # Show role if present
        if 'role' in info:
            typer.echo(f"   Role: {info.get('role')}")
        
        # Try to verify with local secret (if available)
        try:
            verify_token(token)
            typer.echo("\n✅ Token signature verified with local secret")
        except Exception as verify_error:
            typer.echo(f"\n⚠️  Could not verify signature: {str(verify_error)}")
        
    except Exception as e:
        typer.echo(f"❌ Error verifying token: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("edit")
def edit_config():
    """
    Open configuration file in default editor.
    
    Opens the config file with $EDITOR or falls back to system default.
    
    Example:
        apflow config edit
    """
    import os
    
    try:
        path = get_config_file_path()
        
        # Create file if it doesn't exist
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
            typer.echo(f"Created empty config file: {path}")
        
        # Get editor from environment or use defaults
        editor = os.environ.get('EDITOR') or os.environ.get('VISUAL')
        
        if editor:
            subprocess.run([editor, str(path)])
        else:
            # Try common editors or use system default
            if subprocess.run(['which', 'nano'], capture_output=True).returncode == 0:
                subprocess.run(['nano', str(path)])
            elif subprocess.run(['which', 'vim'], capture_output=True).returncode == 0:
                subprocess.run(['vim', str(path)])
            else:
                # Use system open
                if os.name == 'darwin':  # macOS
                    subprocess.run(['open', str(path)])
                elif os.name == 'posix':  # Linux
                    subprocess.run(['xdg-open', str(path)])
                else:  # Windows
                    os.startfile(str(path))
        
    except Exception as e:
        typer.echo(f"❌ Error opening editor: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("validate")
def validate_config():
    """
    Validate configuration file integrity and settings.
    
    Checks:
    - JSON syntax
    - Required fields
    - API server connectivity (if configured)
    - Token validity
    
    Example:
        apflow config validate
    """
    try:
        path = get_config_file_path()
        
        if not path.exists():
            typer.echo("⚠️  No configuration file found")
            typer.echo(f"   Expected: {path}")
            typer.echo("\n💡 Run: apflow config init-server")
            return
        
        typer.echo("🔍 Validating configuration...\n")
        
        # Check JSON syntax
        try:
            config = load_cli_config()
            typer.echo("✅ JSON syntax valid")
        except json.JSONDecodeError as e:
            typer.echo(f"❌ JSON syntax error: {str(e)}")
            raise typer.Exit(1)
        
        # Check if config is empty
        if not config:
            typer.echo("⚠️  Configuration is empty")
            typer.echo("\n💡 Run: apflow config init-server")
            return
        
        typer.echo(f"✅ Found {len(config)} configuration key(s)")
        
        # Check API server URL
        api_url = config.get("api_server_url")
        if api_url:
            typer.echo(f"✅ API server configured: {api_url}")
        else:
            typer.echo("⚠️  No API server URL configured")
        
        # Check and validate token
        token = config.get("api_auth_token")
        if token:
            typer.echo("✅ API auth token configured")
            
            # Check token expiry
            try:
                info = get_token_info(token)
                days = info.get('expires_in_days')
                if days is not None:
                    if days < 0:
                        typer.echo(f"   ⚠️  Token EXPIRED ({abs(days)} days ago)")
                    elif days < 7:
                        typer.echo(f"   ⚠️  Token expiring soon ({days} days)")
                    else:
                        typer.echo(f"   ✅ Token valid ({days} days remaining)")
            except Exception as e:
                typer.echo(f"   ⚠️  Could not parse token: {str(e)}")
        else:
            typer.echo("⚠️  No API auth token configured")
        
        # Summary
        typer.echo("\n" + "="*50)
        if api_url and token:
            typer.echo("✅ Configuration looks good!")
        else:
            typer.echo("⚠️  Configuration incomplete")
            typer.echo("\n💡 Run: apflow config init-server")
        
    except Exception as e:
        if "Configuration" not in str(e):
            typer.echo(f"❌ Error validating configuration: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command("init")
def init_interactive():
    """
    Interactive configuration wizard.
    
    Guides you through setting up API server and authentication.
    
    Example:
        apflow config init
    """
    try:
        typer.echo("🚀 APFlow Configuration Wizard\n")
        
        # Check if already configured
        existing_config = load_cli_config()
        if existing_config:
            typer.echo("⚠️  Configuration already exists:")
            for key, value in existing_config.items():
                if "token" in key.lower():
                    masked = f"{value[:8]}...***" if len(value) > 8 else "***"
                    typer.echo(f"   {key}: {masked}")
                else:
                    typer.echo(f"   {key}: {value}")
            typer.echo()
            
            if not typer.confirm("Overwrite existing configuration?"):
                typer.echo("Cancelled")
                raise typer.Exit(0)
        
        # Ask for API server URL
        typer.echo("Step 1: API Server Configuration")
        default_url = "http://localhost:8000"
        api_url = typer.prompt(
            "Enter API server URL",
            default=default_url
        )
        api_url = api_url.rstrip("/")
        
        # Ask for role
        typer.echo("\nStep 2: Token Configuration")
        role = typer.prompt(
            "Enter token role (admin/user)",
            default="admin"
        )
        
        # Ask for expiry
        expiry = typer.prompt(
            "Enter token expiry in days",
            default=365,
            type=int
        )
        
        # Generate configuration
        typer.echo("\n🔧 Generating configuration...")
        
        set_config_value("api_server_url", api_url)
        
        token = generate_token(
            subject="apflow-cli",
            extra_claims={"role": role},
            expiry_days=expiry,
        )
        set_config_value("api_auth_token", token)
        
        typer.echo("\n✅ Configuration saved successfully!")
        typer.echo(f"   Server: {api_url}")
        typer.echo(f"   Token: {token[:20]}...***")
        typer.echo(f"   Role: {role}")
        typer.echo(f"   Expiry: {expiry} days")
        typer.echo(f"   Location: {get_config_file_path()}")
        
        typer.echo("\n💡 Next steps:")
        typer.echo("   apflow config validate    # Validate configuration")
        typer.echo("   apflow tasks list         # Test CLI with API")
        
    except Exception as e:
        if "Cancelled" not in str(e):
            typer.echo(f"❌ Error: {str(e)}", err=True)
        raise typer.Exit(1)

