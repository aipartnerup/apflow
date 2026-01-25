# Extensions in apflow

apflow supports a powerful extension system for both CLI commands and core functionality. You can add your own extensions or override existing ones, making it easy to customize and adapt apflow to your needs.

## CLI Extensions: Custom Commands and Overriding

You can register new CLI command groups or single commands using the `@cli_register` decorator. You can also extend or override existing commands and groups by specifying the `group` and `override=True` parameters.

For detailed usage and examples, see the [CLI Guide](./cli.md) and [Library Usage Guide](./library-usage.md).

## Core Extensions: Custom and Override

apflow also supports custom extensions for executors, hooks, storage backends, and more. You can register your own or override built-in extensions by passing `override=True` when registering.

For how to override executors and other extensions, see the [API Quick Reference](../api/quick-reference.md) and [Python API Reference](../api/python.md).

For more details, see the [Extending Guide](../development/extending.md).

For more details, see the [Extending Guide](../development/extending.md).

## Best Practices
- Use `override=True` only when you want to replace an existing command or extension.
- Keep extension logic simple and well-documented.
- Test your extensions thoroughly.
