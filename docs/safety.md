# Safety Notes

This repository is structured for public-safe development. It avoids embedding private infrastructure details, credentials, or environment-specific workflows.

## Baseline Rules

- do not commit secrets, tokens, keys, or private endpoints
- keep example files synthetic and non-sensitive
- use environment variables for local overrides
- treat integrations as optional until they are publicly documented

## Local State Guidance

- commit only templates such as `examples/env.example`
- keep real `.env` files untracked
- keep runtime state in ignored local directories such as `./.agent-hub/`
- avoid committing caches such as `__pycache__/`

## Integration Guidance

- add external service adapters behind clear interfaces
- keep authentication and transport details out of public examples
- avoid assuming access to private boards, control planes, or internal APIs
- require explicit opt-in for any destructive or stateful operation

## Release Hygiene

Before publishing or tagging a release:

- review docs and examples for sensitive references
- verify `.gitignore` covers local state and developer files
- confirm no private deployment artifacts were copied into the tree
- choose and add a public OSS license if the repository is meant to be distributed
