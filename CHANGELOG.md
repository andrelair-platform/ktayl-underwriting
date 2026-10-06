# Changelog

## [0.1.1](https://github.com/andrelair-platform/ktayl-underwriting/compare/ktayl-underwriting-v0.1.0...ktayl-underwriting-v0.1.1) (2026-10-06)


### Features

* **frontend:** BFF mints Authentik client-credentials token for prod auth ([#30](https://github.com/andrelair-platform/ktayl-underwriting/issues/30)) ([5ffc4fe](https://github.com/andrelair-platform/ktayl-underwriting/commit/5ffc4fe32f568d0887acfdaaed95e02e53b3ac4e))
* **frontend:** consume @andrelair-platform/bff-auth (shared BFF token lib) ([#33](https://github.com/andrelair-platform/ktayl-underwriting/issues/33)) ([e500991](https://github.com/andrelair-platform/ktayl-underwriting/commit/e50099103d5522e12010322ba6930410c91bdbaa))
* **frontend:** underwriter workbench (Next.js BFF) + inbox list endpoint ([#24](https://github.com/andrelair-platform/ktayl-underwriting/issues/24)) ([7981ed3](https://github.com/andrelair-platform/ktayl-underwriting/commit/7981ed39e918c9d6a1a4d743526759849d15443a))
* ktayl-underwriting product bootstrap (insurance lob) ([1eed1b3](https://github.com/andrelair-platform/ktayl-underwriting/commit/1eed1b3adc71d503b113bdf3ae2700d90441b39c))
* self-migrate DB schema on startup (matches ktayl-policy-service) ([#14](https://github.com/andrelair-platform/ktayl-underwriting/issues/14)) ([b72d05f](https://github.com/andrelair-platform/ktayl-underwriting/commit/b72d05fe640da9a6e5950b64f5821d8b112c9aa8))
* **UW-01-S01:** underwriting workbench core — intake → appetite → decision + audit ([#10](https://github.com/andrelair-platform/ktayl-underwriting/issues/10)) ([121d459](https://github.com/andrelair-platform/ktayl-underwriting/commit/121d459c3b58003c32c3ed4d1581df456e8fc6a3))
* **UW-01-S02:** bind a quoted risk to the live policy service + bound-risk event (ADR-006) ([#17](https://github.com/andrelair-platform/ktayl-underwriting/issues/17)) ([9248482](https://github.com/andrelair-platform/ktayl-underwriting/commit/92484822ad0025225c104db12835c374d654ec90))
* **UW-04-S01:** rating engine + explainable quote (versioned rate tables) ([#15](https://github.com/andrelair-platform/ktayl-underwriting/issues/15)) ([1b2ad68](https://github.com/andrelair-platform/ktayl-underwriting/commit/1b2ad683cb9d6f292c0a9b5db5369152c559db6e))


### Bug Fixes

* **api:** bound the inbox offset so overflow returns 422, not 500 (QA B1 blocker) ([#29](https://github.com/andrelair-platform/ktayl-underwriting/issues/29)) ([591ae9c](https://github.com/andrelair-platform/ktayl-underwriting/commit/591ae9cf9ca0747277ab5748b028f338c33904d7))
* **bind:** send RFC3339 datetimes to policy-service (was a bare date → 400) ([#19](https://github.com/andrelair-platform/ktayl-underwriting/issues/19)) ([52b13a0](https://github.com/andrelair-platform/ktayl-underwriting/commit/52b13a0aa917274acef200d858e296708fcc90e7))
* **ci:** accept the vendored-in-Next tar CVE via a documented .trivyignore ([#27](https://github.com/andrelair-platform/ktayl-underwriting/issues/27)) ([d82b7d5](https://github.com/andrelair-platform/ktayl-underwriting/commit/d82b7d5ece63594851b9530ff98ffd2f7c9f1cfd))
* **frontend:** add public/ dir so the standalone Docker build's COPY succeeds ([#25](https://github.com/andrelair-platform/ktayl-underwriting/issues/25)) ([c1a172b](https://github.com/andrelair-platform/ktayl-underwriting/commit/c1a172b4cf272ad2eda11aeec01a2360bf47b024))
* **frontend:** bff-auth 0.1.2 (openid-client-backed) ([#34](https://github.com/andrelair-platform/ktayl-underwriting/issues/34)) ([978f0ec](https://github.com/andrelair-platform/ktayl-underwriting/commit/978f0ecd938bbc12164868392b07148590b16043))
* **frontend:** bump Next.js 16.2.7 → 16.3.3 (CVE-2026-75604 critical RCE) ([#26](https://github.com/andrelair-platform/ktayl-underwriting/issues/26)) ([461605c](https://github.com/andrelair-platform/ktayl-underwriting/commit/461605cd14fb71ff59211fc5f27e5e02d29faa66))
* **M2 root cause:** alembic fileConfig must not disable existing loggers ([#22](https://github.com/andrelair-platform/ktayl-underwriting/issues/22)) ([a676492](https://github.com/andrelair-platform/ktayl-underwriting/commit/a676492e452eeefd2bd618eb00e6ccc1408498c9))
* **M2:** request logger needs its own stdout handler (uvicorn silences it) ([#21](https://github.com/andrelair-platform/ktayl-underwriting/issues/21)) ([7632c42](https://github.com/andrelair-platform/ktayl-underwriting/commit/7632c4287456402efd17a3215dc1312e31daf49c))
* **qa:** prod-hardening — authz+scopes, actor-from-token, bind-lock, logging, publish retry ([#20](https://github.com/andrelair-platform/ktayl-underwriting/issues/20)) ([2f39895](https://github.com/andrelair-platform/ktayl-underwriting/commit/2f398956146adc30e24c3a114d8ce1e4091f8975))
* **security:** bump Next.js 16.3.3 -&gt; 16.3.6 (GHSA-vcvr-r3jv-pc5j, CRITICAL) ([#32](https://github.com/andrelair-platform/ktayl-underwriting/issues/32)) ([c86d277](https://github.com/andrelair-platform/ktayl-underwriting/commit/c86d277f602ad7f57c8d27466dd23cd4a1847596))
* **security:** bump PyJWT 2.10.1 -&gt; 2.14.0 (CVE-2026-102268, CRITICAL) ([#31](https://github.com/andrelair-platform/ktayl-underwriting/issues/31)) ([6c620ca](https://github.com/andrelair-platform/ktayl-underwriting/commit/6c620cae4e365492ee2ba650f530a6a8a77bd343))


### Documentation

* add forward-deployed-engineer playbook for underwriting and pricing ([#6](https://github.com/andrelair-platform/ktayl-underwriting/issues/6)) ([0ae07b0](https://github.com/andrelair-platform/ktayl-underwriting/commit/0ae07b094f296c6e314e20c8df3a4cafdd1c381b))
* add regulatory impact -&gt; controls -> evidence -> monitoring section (reference) ([#8](https://github.com/andrelair-platform/ktayl-underwriting/issues/8)) ([6138679](https://github.com/andrelair-platform/ktayl-underwriting/commit/6138679a3d78c2c59522d2045359060d40e48397))
* auto-generated ERD + CI schema drift-check (Alembic) ([#35](https://github.com/andrelair-platform/ktayl-underwriting/issues/35)) ([e3eb8f2](https://github.com/andrelair-platform/ktayl-underwriting/commit/e3eb8f28267899fc2404720c811a00e07b994e37))
* BMAD Path-C planning artefact set for Underwriting & Pricing ([#12](https://github.com/andrelair-platform/ktayl-underwriting/issues/12)) — for review ([#9](https://github.com/andrelair-platform/ktayl-underwriting/issues/9)) ([7017538](https://github.com/andrelair-platform/ktayl-underwriting/commit/701753877650752dad7ada9a13beeb2f5312d5e3))
* **catalog:** add governance capability-registry annotations (§8) [skip ci] ([477758d](https://github.com/andrelair-platform/ktayl-underwriting/commit/477758dca281406c9883431d4c815bda7a097d99))
* **governance:** backfill the frontend/workbench governance artefacts ([#28](https://github.com/andrelair-platform/ktayl-underwriting/issues/28)) ([d70e3f5](https://github.com/andrelair-platform/ktayl-underwriting/commit/d70e3f5b595e8158790e496b796e7dc0843481e0))
* remove reference-insurer identifying mention from uw playbook ([#7](https://github.com/andrelair-platform/ktayl-underwriting/issues/7)) ([7bdef8d](https://github.com/andrelair-platform/ktayl-underwriting/commit/7bdef8d42bed55731aa5770314876cbc78d07af6))

## Changelog

All notable changes to ktayl-underwriting are documented here.

This file is maintained by [release-please](https://github.com/googleapis/release-please).
