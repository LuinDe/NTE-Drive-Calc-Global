# Native Core component source

Base commit: b58a86589563fa06e91be3b8807e5b13704a206c. Modified working-tree input SHA-256: 9003aba7a9135fb9cbe4dac6f57b9c5af5552084ebb4e736cdfecdd854765ffe. The base alone does not reproduce this build.

Locked Release CLI build with embedded resources and remapped private build paths. Native battle capture consumes character, team and environment observations. The character business page includes native_battle_equipped_v1: a validated equipped-only subset from the same pinned character observation, with exact item identity, owner, active-slot coverage, stat and placement checks. It never establishes a complete inventory collection. The companion Calc battle path does not refresh or paginate full inventory; normal inventory synchronization remains available.

Focused Rust mapping checks passed. Offline re-projection of one archived real first-hit character observation resolved four team members and 32 equipped items, with original first-hit identity validation passing. Historical account records were not changed. Live capture acceptance remains pending. Existing signed DLLs, Loader and protocol remain the same component inputs.

## NTE Drive Calc Global resource modification

Global 2.3.5 includes CN 1.5.4 character 1090 (Elyms) in the embedded character and equipment mapping resources used by native inventory sync. The Rust source identity and upstream test results above describe the base Core. The Global source package includes build_tools/elyms_core.py and the catalog inputs to reproduce this change.

Upstream Core SHA-256: 1f875858409ad47eed83ded7991d7a3133eb4afafebf2c2b09cd52802c7b2fed

Global Core SHA-256: a352a93fffef24ff0a2b28faf3688b8ef9584905e76b4dfd4660502b37587b36
