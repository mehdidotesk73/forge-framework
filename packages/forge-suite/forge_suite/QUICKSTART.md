# Forge Suite — Quick Reference

## Management UI

```bash
forge-suite serve                        # Start UI at http://localhost:5174
forge-suite serve --port 8080            # Custom port
forge-suite serve --no-open              # Don't open browser automatically
```

## Project Management

```bash
forge-suite init <path>                  # Scaffold + register a new project
forge-suite mount <path>                 # Register an existing project
forge-suite list                         # List all registered projects
forge-suite sync <path>                  # Re-sync project from forge.toml
```

## Project Operations *(no server required)*

```bash
forge-suite pipeline-run <path> <name>   # Run a named pipeline
forge-suite model-build <path>           # Rebuild model schemas + SDKs
forge-suite endpoint-build <path>        # Rebuild endpoint descriptor registry
forge-suite project-serve <path>         # Start project backend only (:8001)
```

## Maintenance

```bash
forge-suite quickstart                   # Print this reference to the terminal
forge-suite quickstart --open            # Open this file in your default editor
forge-suite uninstall                    # Remove forge-suite + forge-framework
```

---

## forge CLI *(run inside a project directory)*

```bash
forge init <name>                        # Scaffold a new Forge project
forge dev serve                          # Start dev server (:8000)
forge pipeline run <name>                # Run a pipeline
forge pipeline dag                       # Show pipeline dependency graph
forge pipeline history <name>            # Show run history for a pipeline
forge model build                        # Build model schemas + SDKs
forge model reinitialize <Type>          # Reset a model's backing dataset
forge endpoint build                     # Build endpoint descriptor registry
forge dataset load <file> --name <n>     # Load a dataset from a file
forge dataset list                       # List all datasets
forge dataset inspect <id>               # Inspect a dataset
forge build                              # Build frontend apps (npm run build)
forge export                             # Export project as .forgepkg
forge upgrade [--dry-run]                # Run migrations + rebuild artifacts
forge version                            # Show framework version
```

---

This file lives at `~/.forge-suite/QUICKSTART.md`.
Run `forge-suite quickstart` to print it to the terminal at any time.
Run `forge-suite quickstart --open` to open it in your default text editor.
