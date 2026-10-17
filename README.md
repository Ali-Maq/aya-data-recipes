# AYA data recipes

Saved JSON export recipes for Open WebUI. AYA builds the component from a GitHub feature request and tests it against the installed jq binary.

The factory lives in [Ali-Maq/aya](https://github.com/Ali-Maq/aya). This repository is the target application extension.

## Contract

`specs/export-recipe.json` defines the supported behavior. The component must use Python's standard library. It must not execute jq, a shell, or user programs.

The reviewed Open WebUI adapter resolves file permissions and calls a separate component runtime. Generated code does not run inside Open WebUI.

## Delivery

Feature work arrives through a pull request with agent-written tests, independent verification, a reference digest, and a GitHub Actions result. A passing test suite covers the declared subset. It does not prove equivalence to the full jq language.
