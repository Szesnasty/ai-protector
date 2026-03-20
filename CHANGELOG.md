# Changelog

## [0.1.12](https://github.com/Szesnasty/ai-protector/compare/v0.1.11...v0.1.12) (2026-03-20)


### Features

* **01:** mock provider + MODE routing ([db89a6e](https://github.com/Szesnasty/ai-protector/commit/db89a6e118690124561f80a3d93f18c910023d47))
* **02:** Docker profiles + Makefile targets ([714ee0f](https://github.com/Szesnasty/ai-protector/commit/714ee0fe4d8726a5fac804c2ffea9c25e77a2e8f))
* **03:** CSP & security headers + CORS hardening ([c0dceac](https://github.com/Szesnasty/ai-protector/commit/c0dceacf44c4429b80557bb2820e4503c40df179))
* **04:** UI demo mode ([30744a1](https://github.com/Szesnasty/ai-protector/commit/30744a198f857205fb29a9da36dc4d4224862567))
* **05:** seed demo data script ([a28cb67](https://github.com/Szesnasty/ai-protector/commit/a28cb67c39fd7b7c31ccf389816c76ad3faf787e))
* **06d:** wire pipeline into chat router, graph integration tests ([bf804e5](https://github.com/Szesnasty/ai-protector/commit/bf804e5dc746bd7ca51f10e2f45131cc1da51620))
* **06:** README rewrite for GitHub landing page ([8ce7522](https://github.com/Szesnasty/ai-protector/commit/8ce7522876e18c2e05c6549721ff4d9fd3c14e52))
* **07a:** LLM Guard scanner node with 5 input scanners ([60159df](https://github.com/Szesnasty/ai-protector/commit/60159df82ae7ac5525f5816d7a4fcfe8b9bd9307))
* **07b:** Presidio PII detection & anonymization node ([3ccf876](https://github.com/Szesnasty/ai-protector/commit/3ccf8765545a2f8769fb6d819ffc991717be1b8b))
* **07c:** parallel scanner execution & pipeline integration ([69b433f](https://github.com/Szesnasty/ai-protector/commit/69b433f0ec875e707a248371ac918a56b0e9e663))
* **07:** enable CI workflows + release prep ([76a8078](https://github.com/Szesnasty/ai-protector/commit/76a8078477a640c8fd9602e975d04644b8b1dcec))
* **08a:** policies CRUD router — 5 endpoints with Redis invalidation ([8f24dfc](https://github.com/Szesnasty/ai-protector/commit/8f24dfcec1347236112efbacaad12fd1659151da))
* **08b:** policy config validation + seed data alignment ([9799f5e](https://github.com/Szesnasty/ai-protector/commit/9799f5e0a8bf5f8bdd4034c53c9c03ca87cfbc68))
* **08c:** policy-aware decision node with configurable weights ([decd51a](https://github.com/Szesnasty/ai-protector/commit/decd51ad7e95b898388ade845ef1a82e32444a09))
* **09a:** output filter node — PII, secrets & system prompt leak redaction ([7458e1f](https://github.com/Szesnasty/ai-protector/commit/7458e1fd1b00d5fe24955aacfa427c3bcb1e6f7f))
* **09b:** memory hygiene — conversation sanitization utility ([c1bd388](https://github.com/Szesnasty/ai-protector/commit/c1bd3881856e45a099c95d1af3a824e651d2a956))
* **09c:** logging node — Postgres audit + Langfuse tracing ([9bfc966](https://github.com/Szesnasty/ai-protector/commit/9bfc966317cf864c8c8cb09ccb0db8f85ef14226))
* **09d:** graph integration — output_filter + logging wired into pipeline ([4926ef3](https://github.com/Szesnasty/ai-protector/commit/4926ef3f4a34fad91d2262a1103b47b8d14eaa3b))
* add benchmark suite + JailbreakBench external validation ([2131a4a](https://github.com/Szesnasty/ai-protector/commit/2131a4a5023c5fc593282dabf29ac3833e0b03bc))
* add integration guide page with links from Agents & Wizard ([327fc38](https://github.com/Szesnasty/ai-protector/commit/327fc384c676ed7cf2c55e2b44a8caed9d99d9c8))
* add pentest E2E runner + scenario IDs + disable CI workflows ([a5cc03e](https://github.com/Szesnasty/ai-protector/commit/a5cc03e9f9b640779c2bfc9d8696768c0ba7d0a9))
* add tagline below wizard CTA in sidebar ([0272e0d](https://github.com/Szesnasty/ai-protector/commit/0272e0df0c7fd911982616737d13f2a9b5a70954))
* agent-demo auto-registers with wizard + centralized trace ingestion ([eb26f16](https://github.com/Szesnasty/ai-protector/commit/eb26f163c061d85e33cb8e40f4db1973dc71df4f))
* **agent-demo:** implement Step 11 — Customer Support Copilot ([56383cb](https://github.com/Szesnasty/ai-protector/commit/56383cb7d77be749ad8eec6cf8bfd91e481155d4))
* **agent-demo:** Step 12 — Agent ↔ Firewall Integration ([8b2198b](https://github.com/Szesnasty/ai-protector/commit/8b2198be92cf59405ce4cae0ca51b358eb651f75))
* **agent:** implement pre-tool enforcement gate (spec 01) ([c99c3be](https://github.com/Szesnasty/ai-protector/commit/c99c3be6134f0201ccbfcabab5203dcdfaee9568))
* **agent:** implement spec 02 — RBAC + Tool Allowlist ([300f109](https://github.com/Szesnasty/ai-protector/commit/300f109cf799463e782e60ca92506f34bd79e0d1))
* **agent:** implement spec 03 — Post-tool Enforcement Gate ([608109e](https://github.com/Szesnasty/ai-protector/commit/608109e058d7cf495ee1d76dc801c4ddd7644b32))
* **agent:** implement spec 04 — Argument Validation & Schema Enforcement ([6bb8040](https://github.com/Szesnasty/ai-protector/commit/6bb8040e0404a145ef74139658f9da2cb3aeecce))
* agents wizard docs - spec alignment + README pre-publish ([6751ea1](https://github.com/Szesnasty/ai-protector/commit/6751ea146b9f857b1697296023eaf01ceae9d9db))
* **agent:** spec 07 — Agent Trace Phase 1 (in-memory trace + API response) ([a995751](https://github.com/Szesnasty/ai-protector/commit/a9957512e5b595f516d09eef238637339a45f0bd))
* **agent:** spec 07 Phase 2+3 — trace store, REST API, Langfuse, export ([f5d643c](https://github.com/Szesnasty/ai-protector/commit/f5d643cbb99c3518b46a965722782d54c191e10e))
* **agents:** pre-scan + security test buttons + highlighted source ([156014d](https://github.com/Szesnasty/ai-protector/commit/156014d07ff1fc97375d710cb57851c6fef889c1))
* **agents:** route LLM responses through proxy firewall (balanced) ([a453dbf](https://github.com/Szesnasty/ai-protector/commit/a453dbf666f0c95a85dc19b85ab51ba45d8028c9))
* **agents:** spec 05 — message role separation & anti-spoofing ([01ac16a](https://github.com/Szesnasty/ai-protector/commit/01ac16a6bc2a881a5119b36e282729ab1c3f881f))
* **agents:** spec 06 — limits, rate limiting, iteration caps, budget caps ([c0acb8b](https://github.com/Szesnasty/ai-protector/commit/c0acb8bb50360b15a9fedb5d780aa54c46dc9eac))
* **compare:** add dedicated attack scenarios panel for Compare Playground ([4ae154e](https://github.com/Szesnasty/ai-protector/commit/4ae154eddbb7bcbe3781c26979056b9a1c70fffe))
* **compare:** direct browser to provider API for right panel ([8afe771](https://github.com/Szesnasty/ai-protector/commit/8afe77118428e5dfaf3a311a000d2058de2eb880))
* **compare:** two-mode compare system with semantic color logic ([20a19bc](https://github.com/Szesnasty/ai-protector/commit/20a19bc616555b10a1da9cf4410c5af54e5df293))
* differentiate no_match from security block in UX ([fd06ce5](https://github.com/Szesnasty/ai-protector/commit/fd06ce5c561266d78fe18a7c334571834266ecd6))
* expand attack scenarios to 157 playground + 103 agent (from 57+48), panels collapsed by default ([83ecc2a](https://github.com/Szesnasty/ai-protector/commit/83ecc2a59463ee2bbbe0c78a82b3c5ba2da6dd34))
* expand attack scenarios with OWASP LLM Top 10 2025 research (+98 items, +14 groups) ([424aea2](https://github.com/Szesnasty/ai-protector/commit/424aea24b252846fe68c08a262bef1cd24f96f32))
* **frontend:** add test agent pages with chat and gate log ([ec1c010](https://github.com/Szesnasty/ai-protector/commit/ec1c0108c6c106d0678db2c5e3e253b89f648ced))
* **frontend:** add visible tooltip icons to chips and improve info styling ([ff318b6](https://github.com/Szesnasty/ai-protector/commit/ff318b6603451c177cf25ffd056032290778f3e6))
* **frontend:** Agent Traces page — browse, filter, expand, export traces ([09a09c7](https://github.com/Szesnasty/ai-protector/commit/09a09c77c5f201468e29563cc27d02e32fb9e46d))
* **frontend:** fresh data, alphabetical scenarios, autocomplete filter, policy ordering ([7ffc6a5](https://github.com/Szesnasty/ai-protector/commit/7ffc6a5d8d94ca314be3f0ce4f99a2641c411c94))
* **frontend:** implement Step 05 — Frontend Foundation ([fdd419b](https://github.com/Szesnasty/ai-protector/commit/fdd419b789c687549cb32e27bf77c227cb9e2c8f))
* **frontend:** inline pipeline decision in chat messages, update MVP-PLAN ([4170aa4](https://github.com/Szesnasty/ai-protector/commit/4170aa416bc79dc552ff255c70cb0f0df384037b))
* **frontend:** remember last selected model per view in localStorage ([db6e320](https://github.com/Szesnasty/ai-protector/commit/db6e320629cc5ff843646f0dee1f9052d3780418))
* **frontend:** spec 33 — Agent Wizard UI with composables, stepper, 7 wizard steps, list page, detail page with 8 tabs ([ae50cf8](https://github.com/Szesnasty/ai-protector/commit/ae50cf8d73b747e61210d5bdf90be3834e2a72da))
* **frontend:** Step 13 — Agent Demo UI ([d4a6f39](https://github.com/Szesnasty/ai-protector/commit/d4a6f399dc83e2d78ae23c75416a70af8c31261b))
* **frontend:** unified semantic color system, request log UX, settings security info ([23cb871](https://github.com/Szesnasty/ai-protector/commit/23cb871f13659115c3419931851493e2348fc506))
* **infra:** add Docker profiles for test agents, update CSP and frontend config ([36e7429](https://github.com/Szesnasty/ai-protector/commit/36e7429488f8d716f1288172f130c72ba9d4b50b))
* near-realtime analytics — sub-minute polling, 5m/15m ranges ([7fef20d](https://github.com/Szesnasty/ai-protector/commit/7fef20d20a923be19f1bfc43306c71bbefd22c6a))
* **nemo:** add NeMo Guardrails to policy editor UI + backend validation ([0ccd62a](https://github.com/Szesnasty/ai-protector/commit/0ccd62adee8382e9f3c95e42d167ec6226ec747c))
* **policies:** make built-in policies read-only ([7d162b6](https://github.com/Szesnasty/ai-protector/commit/7d162b6ef7fbbfb42d5d1c17d90b6f2b8b173b78))
* pre-commit hooks, coverage badge, session-scoped DB fixture ([07f0275](https://github.com/Szesnasty/ai-protector/commit/07f027568f17cae724386de416bd98c7d3ee40f4))
* preload ML models on startup + add known issues tracker ([2434ec2](https://github.com/Szesnasty/ai-protector/commit/2434ec28e4450673212e2fa124d061c72ef5e633))
* real-time system metrics in health popover (RAM, CPU, disk, uptime, threads, requests) ([1be0958](https://github.com/Szesnasty/ai-protector/commit/1be0958c566eff54717e1430efcd0ab4c091f746))
* **seed:** two fully-configured demo agents on first startup ([2b719a6](https://github.com/Szesnasty/ai-protector/commit/2b719a6036b0102f688e07692cb64f8014203aec))
* show only available models + move API URLs to env vars ([5f1348c](https://github.com/Szesnasty/ai-protector/commit/5f1348c36a5bd18d877a163d634a3887829f9e1c))
* skull FAB button + expanded scenarios (57 Playground, 48 Agent) ([2a938e1](https://github.com/Szesnasty/ai-protector/commit/2a938e192be72ec2931ef8bf4d555e266c9783fe))
* **source-viewer:** color-coded AI Protector highlight categories ([d605dfa](https://github.com/Szesnasty/ai-protector/commit/d605dfa463884ded424a676b91a1567fa051ccaf))
* step 01 — project scaffolding ([a0cd268](https://github.com/Szesnasty/ai-protector/commit/a0cd268484b157bdfbdf9a62cfcc31377a4652b7))
* step 02 — infrastructure (Docker Compose) ([5fb8ef9](https://github.com/Szesnasty/ai-protector/commit/5fb8ef9a3d8613539407350aa0e0c7debb69e2df))
* Step 20 — Attack Scenarios Panel with 40 attack prompts for live demos ([9e3c0e0](https://github.com/Szesnasty/ai-protector/commit/9e3c0e04b1011738678a53934d193c93ecbea73f))
* **step-03:** proxy service foundation ([829979e](https://github.com/Szesnasty/ai-protector/commit/829979e1b2b830a3dcba00f2dbdd5fa4161cfc2e))
* **step-04a:** LiteLLM client, chat schemas, LLM exceptions ([6a5797c](https://github.com/Szesnasty/ai-protector/commit/6a5797c37222d62250d820587459cfbf7c758315))
* **step-04b:** chat completions endpoint with SSE streaming ([1dcdeaf](https://github.com/Szesnasty/ai-protector/commit/1dcdeafbc3afe5bb413f08bbf58ebefdd282b246))
* **step-04c:** request logger, 27 tests, spec checkboxes updated ([a17a863](https://github.com/Szesnasty/ai-protector/commit/a17a863651c9a197c2e0aecf4e304ea1ce3d1187))
* **step-06a:** PipelineState, timed_node decorator, ParseNode ([93d637f](https://github.com/Szesnasty/ai-protector/commit/93d637fe37838ee86242bc1d8d1da88949ce4403))
* **step-06b:** IntentNode, RulesNode, denylist service, seed phrases ([47d6f1f](https://github.com/Szesnasty/ai-protector/commit/47d6f1f2e562303b98b3748a3e2acf17132bcad6))
* **step-06c:** DecisionNode, TransformNode, LLMCallNode, StateGraph pipeline ([8585bd1](https://github.com/Szesnasty/ai-protector/commit/8585bd1c6f341f090d25ed80f37d8d9b2afbd73e))
* **step-14:** custom security rules — model, CRUD API, pipeline integration, frontend editor ([988e111](https://github.com/Szesnasty/ai-protector/commit/988e111fa9cf494c1c3e0a31526f041650cca4b1))
* **step-15:** policies CRUD UI, request log API & UI ([0c124ea](https://github.com/Szesnasty/ai-protector/commit/0c124eae719cd4feb6cc0e88d9299d11751dd077))
* **step-16:** analytics API & dashboard UI ([fb4024d](https://github.com/Szesnasty/ai-protector/commit/fb4024d7baf0c5c1db48eb5d47723afe0936cc5b))
* **step-22:** implement NeMo Guardrails + agent security hardening ([a3410b4](https://github.com/Szesnasty/ai-protector/commit/a3410b4092931e9d596929fafe088427cd014684))
* **step-23:** external LLM providers with SessionStorage API keys ([cce3719](https://github.com/Szesnasty/ai-protector/commit/cce3719e54f09a8327b6e52a8d07c889595242e9))
* **step-24:** compare playground — proxy vs direct side-by-side ([ba2c43a](https://github.com/Szesnasty/ai-protector/commit/ba2c43a4473c795e14bd2711d25bce61e2034cda))
* **step-24:** refactor Compare — external-only, sequential requests ([ce03457](https://github.com/Szesnasty/ai-protector/commit/ce03457026f3ad29fb805e916a95832380faeac1))
* **test-agents:** add LangGraph test agent with security graph ([878d4d3](https://github.com/Szesnasty/ai-protector/commit/878d4d318d91721f7fcb26e45388ead9b6d0fb0d))
* **test-agents:** add pure Python test agent with protection layer ([b3fbfb6](https://github.com/Szesnasty/ai-protector/commit/b3fbfb6a60eb16f41f72df182df9aeb4558bea4c))
* **test-agents:** add shared mock tools, tool definitions & 85 tests ([84048b8](https://github.com/Szesnasty/ai-protector/commit/84048b85d676ad4de4959e7865dfb8305d2f46de))
* **test-agents:** playground-style LLM/mock mode with provider picker ([d524ec5](https://github.com/Szesnasty/ai-protector/commit/d524ec53b455ffba0b4b5639b5eac7c1bfbd0b3c))
* **test-agents:** use shared model catalog + stored API keys from Settings ([9839422](https://github.com/Szesnasty/ai-protector/commit/983942276cbb3f2e65ad2168216fdbdb8c08f276))
* **ui:** comprehensive UI overhaul ([b46fc25](https://github.com/Szesnasty/ai-protector/commit/b46fc254f049b7f16dd28cc66056ad0c1914800e))
* **ui:** highlight Agent Wizard nav item + fix policy pack display ([8350b61](https://github.com/Szesnasty/ai-protector/commit/8350b61b415539400bd7bb122179b422c724bd1e))
* update UI components, attack scenarios panel, and logo assets ([0e53ada](https://github.com/Szesnasty/ai-protector/commit/0e53ada6392ed97bc8bc0bfb50c1c674c85643d8))
* wizard button 48px below Settings, add 81 kit variant tests ([e5fc454](https://github.com/Szesnasty/ai-protector/commit/e5fc45406abea7658b504824f12fdd930fec3ce2))
* **wizard:** add aw_006 migration for traces, incidents, gates, promotions ([05efa9d](https://github.com/Szesnasty/ai-protector/commit/05efa9db8241a9348bb8ff0ed2cf090777af9a73))
* **wizard:** add tool and role presets for quick-start users ([7aad2a3](https://github.com/Szesnasty/ai-protector/commit/7aad2a3769fd6da3d74f8d228c45cd0af5625ffc))
* **wizard:** implement spec 26 — Agent CRUD in self-contained src/wizard/ package ([cd207a9](https://github.com/Szesnasty/ai-protector/commit/cd207a94c0cebbc3c5263a305830be784d8620dc))
* **wizard:** spec 27 - Tools & Roles CRUD with permissions, 52 tests ([151da32](https://github.com/Szesnasty/ai-protector/commit/151da32fc4e9881f50b8c596e4f34d453e75c631))
* **wizard:** spec 28 — config generation (rbac/limits/policy YAML + policy packs + ZIP download) ([b926a7b](https://github.com/Szesnasty/ai-protector/commit/b926a7b9f8a87991046ffd46cb02d26e6e7feb3b))
* **wizard:** spec 29 — integration kit generator (7 Jinja2 templates + API + ZIP download) ([68863e1](https://github.com/Szesnasty/ai-protector/commit/68863e1451822fbb4a9f5b6aeffc03c836f4d296))
* **wizard:** spec 30 — validation runner (42/42 tests) ([6115e62](https://github.com/Szesnasty/ai-protector/commit/6115e6219b6a19913b66ff2db455ddb3b980ab60))
* **wizard:** spec 31 — rollout modes (observe/warn/enforce) with promotion flow (48/48 tests) ([c5239cb](https://github.com/Szesnasty/ai-protector/commit/c5239cb33841f447446501d6150c6f7a02bfc37d))
* **wizard:** spec 32 — agent traces & incidents persistence (50/50 tests) ([c900153](https://github.com/Szesnasty/ai-protector/commit/c900153fc3d27f3435686689bf944a7cb6c0777f))


### Bug Fixes

* **01:** mock_completion returns attr-accessible object ([6bae5d5](https://github.com/Szesnasty/ai-protector/commit/6bae5d526cd66ac09da4b5cf4bb61da0b161929d))
* agent detail – validation results, perm count, edit routing, delete button ([65e4574](https://github.com/Szesnasty/ai-protector/commit/65e4574ee63703821c22424d6d4ce18f6b0b5a43))
* **agent-demo:** align safe scenario prompts with ORD-xxx tool regex ([3007e8f](https://github.com/Szesnasty/ai-protector/commit/3007e8ff82349ba51f15208d2471e3e53d9ceac4))
* **agent:** double /v1/ in scan URL — firewall always returned ALLOW ([20bf766](https://github.com/Szesnasty/ai-protector/commit/20bf766d94b36f93e5c6b161458608339419716d))
* **agent:** extract order ID from '[#12345](https://github.com/Szesnasty/ai-protector/issues/12345)' format and show correct block reason ([ecd1bd9](https://github.com/Szesnasty/ai-protector/commit/ecd1bd9a9b07e57f9e25480bb0efa13667e2ab82))
* **agent:** route user message through proxy firewall in demo mode ([680b272](https://github.com/Szesnasty/ai-protector/commit/680b272238eab6e5fb68d6ac04e6a2cbf379497a))
* **agent:** two-phase LLM call for full tool context ([5fcc753](https://github.com/Szesnasty/ai-protector/commit/5fcc753d18d9cea8dda77fb314d5797191eb98cb))
* align presets and seed with actual test agent tools, add table actions ([0b0e29a](https://github.com/Szesnasty/ai-protector/commit/0b0e29ad5b3c6dbea12aec52f92e5215d931b814))
* **bench:** break CodeQL taint flow by separating model and key detection ([84af624](https://github.com/Szesnasty/ai-protector/commit/84af624dcb7b31c720d2d76cc8374079a7aff901))
* **bench:** separate model name from api_key to resolve CodeQL alerts ([3928346](https://github.com/Szesnasty/ai-protector/commit/3928346a97cdaf742c62e36dd4c9b1f0c9c74a9d))
* **bench:** show full CPU name in benchmark reports ([2fbef89](https://github.com/Szesnasty/ai-protector/commit/2fbef89980f34bbddb7082dcace2a7762a951d1c))
* **ci:** fix release-please — add version.txt, use generic updaters ([d902f3d](https://github.com/Szesnasty/ai-protector/commit/d902f3d40a82b103bfdffdbf89a5241ee9c0e2c1))
* **ci:** use npm ci with lockfile to resolve tinyexec ERR_MODULE_NOT_FOUND ([da00cf6](https://github.com/Szesnasty/ai-protector/commit/da00cf6114413382846940f87628cd1d4b1e1d0c))
* **ci:** use npm install instead of npm ci to avoid CI/Docker failures ([d2f2c3a](https://github.com/Szesnasty/ai-protector/commit/d2f2c3a076d0c3a7d9623f1a444ce8070b46d469))
* Compare playground + policy save in demo mode ([7b44e18](https://github.com/Szesnasty/ai-protector/commit/7b44e181b3c5f132bdf118543336e69b8042b802))
* **compare:** robust error handling, error display, CORS expose_headers ([7c97f5a](https://github.com/Szesnasty/ai-protector/commit/7c97f5a8063dc41831001aebd3fd3e8654671190))
* **compare:** validate API key before send, smarter auto-select ([897e855](https://github.com/Szesnasty/ai-protector/commit/897e855ba547824aea4db298e1cd7687a3b30f78))
* correct RAM estimates — include LLM Guard, NeMo, Presidio ML models ([06082fe](https://github.com/Szesnasty/ai-protector/commit/06082fe4580b34ecc4a7a76ba34b06731b458657))
* downgrade zod to v3 for vee-validate compatibility, use npm install in Dockerfile ([bff70ba](https://github.com/Szesnasty/ai-protector/commit/bff70babb27f8b1c0708efd7f2bd4759ba61a080))
* echarts renderer + MDI/Vuetify CSS loading ([76279c4](https://github.com/Szesnasty/ai-protector/commit/76279c4f4bb707146eae02a38072bdc82f1f52c4))
* eliminate FOUC — restore SSR CSS, strip 404 dupes via Nitro plugin ([c1fd723](https://github.com/Szesnasty/ai-protector/commit/c1fd723f8d6ce2e7deef19eaeaa144c6dae608ef))
* eliminate vuetify/MDI CSS 404s in dev SSR ([cb17d43](https://github.com/Szesnasty/ai-protector/commit/cb17d43077e2503a13952936152118c2221e3d09))
* ensure all requests are logged to Analytics/Request Log ([c835618](https://github.com/Szesnasty/ai-protector/commit/c8356188f5aa59e559bc8bd29eba33fe14a7acc6))
* ensure demo seeds policies by default ([d9d94bd](https://github.com/Szesnasty/ai-protector/commit/d9d94bd0b62924437531eddb3f7d68ee89ea226a))
* expand .gitignore, fix .output/x typo ([f159c35](https://github.com/Szesnasty/ai-protector/commit/f159c35ad51a698eeb941376b54c0bb86dbde9f5))
* expand model catalog with current IDs from all providers ([3978c4b](https://github.com/Szesnasty/ai-protector/commit/3978c4b54e7cbcc899a3782aed01888c6517fa9f))
* **frontend:** force 12px font on Quick Actions and Security Tests chips ([6d11262](https://github.com/Szesnasty/ai-protector/commit/6d11262cf142d39ef6219f93d501905415687b83))
* **frontend:** rename agent components to avoid double prefix ([fff4ed4](https://github.com/Szesnasty/ai-protector/commit/fff4ed4b5df562ae7ec81ca0c38a6febe0a67729))
* **frontend:** resolve Vuetify styles and MDI font CSS 404s ([cba719a](https://github.com/Szesnasty/ai-protector/commit/cba719aff4a52b3774006408b6554a55e10e3ed2))
* **frontend:** single nav drawer, remove no-gutters, fix policies endpoint ([7f2eecb](https://github.com/Szesnasty/ai-protector/commit/7f2eecb0998e4ed83e99d3038e190c5363fcfa1a))
* **frontend:** use correct Nuxt auto-import name for TestAgentChat component ([d7b8c5d](https://github.com/Szesnasty/ai-protector/commit/d7b8c5d73a461023c56ee05068fab2f37a2b22d5))
* include test agents in make demo/up, remove LLM Firewall subtitle ([2a84730](https://github.com/Szesnasty/ai-protector/commit/2a84730a53c2ed86b86d8e664dd14ecf089b98bb))
* **infra:** replace curl healthchecks with python urllib for test agents ([865e4c0](https://github.com/Szesnasty/ai-protector/commit/865e4c044c484c06df3efcb268fea89adadf7c56))
* **ISS-001:** hot-reload LLM Guard scanners on threshold change ([4a68908](https://github.com/Szesnasty/ai-protector/commit/4a68908e9a96300c54f84bf16a49cabf71404f47))
* **models:** make model availability reactive to API key changes ([2fd02ce](https://github.com/Szesnasty/ai-protector/commit/2fd02ce194b6a9581cd06c161cf990e1bf04e8af))
* **nemo:** add generic biographical safe patterns to prevent false positives ([8ae9039](https://github.com/Szesnasty/ai-protector/commit/8ae90393d10c827038a461277f2190d2000cc5b8))
* **nemo:** add safe coding examples to prevent false positives ([447851b](https://github.com/Szesnasty/ai-protector/commit/447851b39ac8d5d9ede08d85af9a291471f4e02f))
* **nemo:** eliminate LLM dependency and use proper fallback_intent API ([f36c189](https://github.com/Szesnasty/ai-protector/commit/f36c189a1235c5dfbcc03de424d21e33b1df5d8f))
* **nemo:** expand safe_input examples to prevent false positives ([e5279a5](https://github.com/Szesnasty/ai-protector/commit/e5279a5e8f7553738231804c6fc225f042e9ee8c))
* **nemo:** resolve supply_chain false positive on order-status queries ([ca8b051](https://github.com/Szesnasty/ai-protector/commit/ca8b05133039620bcf8c854ea76990848aa576de))
* persist last selected model in test agent chat (useRememberedModel) ([f9d5565](https://github.com/Szesnasty/ai-protector/commit/f9d55658bea38c873de04e8c56ace11c257f9e0c))
* **proxy:** eliminate false-positive blocking + add RBAC matrix UI ([9829801](https://github.com/Szesnasty/ai-protector/commit/98298014fede04db88834cb3f01dc7ddd4d63f38))
* push pending CI fixes, dockerignore files, ruff F541 lint ([1edcfe2](https://github.com/Szesnasty/ai-protector/commit/1edcfe2912751761c5de200a2fc4f5f1466a83a0))
* RBAC getUsers admin-only, rearrange controls layout, reorganize sidebar nav ([c252d6b](https://github.com/Szesnasty/ai-protector/commit/c252d6b25d292477d509d0d309aa8f0496e58b22))
* remove broken item.raw Vuetify slot + fix _keyVersion pattern ([49b7d8b](https://github.com/Szesnasty/ai-protector/commit/49b7d8b8dbe8265fa4fddd1c87e5377f28de93c5))
* remove gemini-2.0-flash-lite (unsupported) ([6f23981](https://github.com/Szesnasty/ai-protector/commit/6f2398161e1009621d1b7414c508b786bfdc12e5))
* **resilience:** add retry with exponential backoff to LLM calls ([d1d0a1b](https://github.com/Szesnasty/ai-protector/commit/d1d0a1bf3e25e3baf7bfaba2c8a94bfdafaaa398))
* restore versions to 0.1.9 and CHANGELOG from main ([0050941](https://github.com/Szesnasty/ai-protector/commit/0050941ac5691bcd092abd8a4d31ca9cfca59a15))
* route gemini-* models to Google instead of Ollama ([9f2af6e](https://github.com/Szesnasty/ai-protector/commit/9f2af6eb555e18127a252e7323f0fdb998f4a684))
* **security:** eliminate ReDoS risk in PII regex patterns (CodeQL high) ([77b2596](https://github.com/Szesnasty/ai-protector/commit/77b2596fe4c68f872286ce31d404a6fc42cdbc78))
* **security:** prevent credential leaks in logs, traces, and API responses ([da70efe](https://github.com/Szesnasty/ai-protector/commit/da70efe61835dde4d5b55a4f7dbc23bb7fcb1ec0))
* sidebar overflow, wizard reset, kit template bugs (RBAC test + LimitsService) ([8760de8](https://github.com/Szesnasty/ai-protector/commit/8760de8e3089597ebbdb1bf8750551b35d0885d0))
* **step-24:** add missing compare-panel.vue component ([61cfeae](https://github.com/Szesnasty/ai-protector/commit/61cfeaeff9bfa10effcfefab9ade1d96510dc368))
* streaming requests were not logged to DB — analytics blind spot ([fda8a4d](https://github.com/Szesnasty/ai-protector/commit/fda8a4de6bddad4e0edf3290577b99dd668bca46))
* switch useModels from useAsyncData to useQuery ([4be56a4](https://github.com/Szesnasty/ai-protector/commit/4be56a4e8d524d915fba71f9e13738940556e2e3))
* sync invisible_weight schema default to 0.8, fix test comments and nemo test values ([27812ad](https://github.com/Szesnasty/ai-protector/commit/27812adae9bd4d50b66c8d574ef5f93770ae5ee6))
* **test-agents:** pin exact package versions, fix module isolation, clarify protection.py role ([248d457](https://github.com/Szesnasty/ai-protector/commit/248d4572225e0497fd5f01765afa47e3cb3ff220))
* **test-agents:** render markdown in agent responses + improve text visibility ([8a60c44](https://github.com/Szesnasty/ai-protector/commit/8a60c4454c8dd55357af9a8324e0c1354446f06b))
* **test-agents:** two LLM-mode bugs in pure-python and langgraph agents ([cda99f7](https://github.com/Szesnasty/ai-protector/commit/cda99f78b17fab030bd791785822a7ea1c662cf3))
* **test-agents:** use /v1/scan for pre-scan, fix false positives ([c5f32a1](https://github.com/Szesnasty/ai-protector/commit/c5f32a1e8b74c3f4272d24253025c6fd2d2b7dcf))
* **test:** lower threshold in injection_balanced_block test ([054ffc4](https://github.com/Szesnasty/ai-protector/commit/054ffc47ded49a1fbac60866259229d712cbe771))
* **test:** revert injection_weight to 0.8, raise invisible_weight to 0.8, fix nemo/wizard test expectations ([895cb78](https://github.com/Szesnasty/ai-protector/commit/895cb78d0a9a155bca04dce2d6b224ba086117f7))
* **test:** sync all risk score expectations to injection_weight=0.5 default ([d6278a2](https://github.com/Szesnasty/ai-protector/commit/d6278a2765aff34444a7111a1b0e82f62fcac2c1))
* **test:** update injection risk score expectation to match 0.5 weight ([f3487a5](https://github.com/Szesnasty/ai-protector/commit/f3487a546dfbeffa139c26111281b2f9a1ffe5cd))
* **test:** use seed_wizard in test_seed_idempotent for CI compatibility ([5aba07c](https://github.com/Szesnasty/ai-protector/commit/5aba07c1353ad70b9fd9f7caf3f8485a6c12796a))
* timer cleanup, analytics background polling, model selection across all pages ([9dbde4e](https://github.com/Szesnasty/ai-protector/commit/9dbde4ea5e255771c2ce5dc91f31d4e16ebc3ea5))
* **traces:** surface firewall blocks in agent trace summary and UI ([d757ed1](https://github.com/Szesnasty/ai-protector/commit/d757ed117335ab15c0f17111561e3a51821d6dd7))
* **ui:** disable ML Judge and Canary chips with coming soon tooltip ([7fd4162](https://github.com/Szesnasty/ai-protector/commit/7fd4162a0baa6a6c1679449f16cb8e8fd4ba8a54))
* **ui:** fix node labels and block reason in Agent Traces ([5982b69](https://github.com/Szesnasty/ai-protector/commit/5982b695f8063aa1bcbaeb9d5182dc1bdbc26059))
* **ui:** make sidebar scrollable on all screen sizes ([26fecc5](https://github.com/Szesnasty/ai-protector/commit/26fecc534512dcd09e2a4bed0c2d2ff077d6cfc5))
* **ui:** use proper display names for scanner labels (LLM Guard, NeMo Guardrails, etc.) ([3b9ae24](https://github.com/Szesnasty/ai-protector/commit/3b9ae243b1a2d4d2e4b7e3f1d4d019b08b4356bd))
* update Anthropic model IDs to current versions ([164d683](https://github.com/Szesnasty/ai-protector/commit/164d683f9c0441c534cf40f3159714678c2fcb74))
* **wizard:** use UPPERCASE enum names in aw_006 migration ([7af0c69](https://github.com/Szesnasty/ai-protector/commit/7af0c696d5c3aafafa811bc407413f483ed97794))


### Performance Improvements

* fix CPU spike — stop defaulting to Ollama, reduce health polling ([a9f13f5](https://github.com/Szesnasty/ai-protector/commit/a9f13f5942a2a211b84b01be3832bb06a0a0940c))
* scan-only endpoint + parallel Compare execution ([6bb7dbf](https://github.com/Szesnasty/ai-protector/commit/6bb7dbf6f4add7f5b2059754b8442ec85abcbe4c))


### Reverts

* **frontend:** restore classic dark/light theme, remove cyberpunk palettes ([f6997a6](https://github.com/Szesnasty/ai-protector/commit/f6997a668ec3f79297bb045172cb73c535d643a0))

## [0.1.11](https://github.com/Szesnasty/ai-protector/compare/v0.1.10...v0.1.11) (2026-03-20)


### Features

* agent-demo auto-registers with wizard + centralized trace ingestion ([eb26f16](https://github.com/Szesnasty/ai-protector/commit/eb26f163c061d85e33cb8e40f4db1973dc71df4f))


### Bug Fixes

* persist last selected model in test agent chat (useRememberedModel) ([f9d5565](https://github.com/Szesnasty/ai-protector/commit/f9d55658bea38c873de04e8c56ace11c257f9e0c))

## [0.1.10](https://github.com/Szesnasty/ai-protector/compare/v0.1.9...v0.1.10) (2026-03-20)


### Features

* add integration guide page with links from Agents & Wizard ([327fc38](https://github.com/Szesnasty/ai-protector/commit/327fc384c676ed7cf2c55e2b44a8caed9d99d9c8))
* add tagline below wizard CTA in sidebar ([0272e0d](https://github.com/Szesnasty/ai-protector/commit/0272e0df0c7fd911982616737d13f2a9b5a70954))
* **agents:** pre-scan + security test buttons + highlighted source ([156014d](https://github.com/Szesnasty/ai-protector/commit/156014d07ff1fc97375d710cb57851c6fef889c1))
* **agents:** route LLM responses through proxy firewall (balanced) ([a453dbf](https://github.com/Szesnasty/ai-protector/commit/a453dbf666f0c95a85dc19b85ab51ba45d8028c9))
* differentiate no_match from security block in UX ([fd06ce5](https://github.com/Szesnasty/ai-protector/commit/fd06ce5c561266d78fe18a7c334571834266ecd6))
* **frontend:** add test agent pages with chat and gate log ([ec1c010](https://github.com/Szesnasty/ai-protector/commit/ec1c0108c6c106d0678db2c5e3e253b89f648ced))
* **frontend:** spec 33 — Agent Wizard UI with composables, stepper, 7 wizard steps, list page, detail page with 8 tabs ([ae50cf8](https://github.com/Szesnasty/ai-protector/commit/ae50cf8d73b747e61210d5bdf90be3834e2a72da))
* **infra:** add Docker profiles for test agents, update CSP and frontend config ([36e7429](https://github.com/Szesnasty/ai-protector/commit/36e7429488f8d716f1288172f130c72ba9d4b50b))
* **seed:** two fully-configured demo agents on first startup ([2b719a6](https://github.com/Szesnasty/ai-protector/commit/2b719a6036b0102f688e07692cb64f8014203aec))
* **source-viewer:** color-coded AI Protector highlight categories ([d605dfa](https://github.com/Szesnasty/ai-protector/commit/d605dfa463884ded424a676b91a1567fa051ccaf))
* **test-agents:** add LangGraph test agent with security graph ([878d4d3](https://github.com/Szesnasty/ai-protector/commit/878d4d318d91721f7fcb26e45388ead9b6d0fb0d))
* **test-agents:** add pure Python test agent with protection layer ([b3fbfb6](https://github.com/Szesnasty/ai-protector/commit/b3fbfb6a60eb16f41f72df182df9aeb4558bea4c))
* **test-agents:** add shared mock tools, tool definitions & 85 tests ([84048b8](https://github.com/Szesnasty/ai-protector/commit/84048b85d676ad4de4959e7865dfb8305d2f46de))
* **test-agents:** playground-style LLM/mock mode with provider picker ([d524ec5](https://github.com/Szesnasty/ai-protector/commit/d524ec53b455ffba0b4b5639b5eac7c1bfbd0b3c))
* **test-agents:** use shared model catalog + stored API keys from Settings ([9839422](https://github.com/Szesnasty/ai-protector/commit/983942276cbb3f2e65ad2168216fdbdb8c08f276))
* **ui:** highlight Agent Wizard nav item + fix policy pack display ([8350b61](https://github.com/Szesnasty/ai-protector/commit/8350b61b415539400bd7bb122179b422c724bd1e))
* wizard button 48px below Settings, add 81 kit variant tests ([e5fc454](https://github.com/Szesnasty/ai-protector/commit/e5fc45406abea7658b504824f12fdd930fec3ce2))
* **wizard:** add aw_006 migration for traces, incidents, gates, promotions ([05efa9d](https://github.com/Szesnasty/ai-protector/commit/05efa9db8241a9348bb8ff0ed2cf090777af9a73))
* **wizard:** add tool and role presets for quick-start users ([7aad2a3](https://github.com/Szesnasty/ai-protector/commit/7aad2a3769fd6da3d74f8d228c45cd0af5625ffc))
* **wizard:** implement spec 26 — Agent CRUD in self-contained src/wizard/ package ([cd207a9](https://github.com/Szesnasty/ai-protector/commit/cd207a94c0cebbc3c5263a305830be784d8620dc))
* **wizard:** spec 27 - Tools & Roles CRUD with permissions, 52 tests ([151da32](https://github.com/Szesnasty/ai-protector/commit/151da32fc4e9881f50b8c596e4f34d453e75c631))
* **wizard:** spec 28 — config generation (rbac/limits/policy YAML + policy packs + ZIP download) ([b926a7b](https://github.com/Szesnasty/ai-protector/commit/b926a7b9f8a87991046ffd46cb02d26e6e7feb3b))
* **wizard:** spec 29 — integration kit generator (7 Jinja2 templates + API + ZIP download) ([68863e1](https://github.com/Szesnasty/ai-protector/commit/68863e1451822fbb4a9f5b6aeffc03c836f4d296))
* **wizard:** spec 30 — validation runner (42/42 tests) ([6115e62](https://github.com/Szesnasty/ai-protector/commit/6115e6219b6a19913b66ff2db455ddb3b980ab60))
* **wizard:** spec 31 — rollout modes (observe/warn/enforce) with promotion flow (48/48 tests) ([c5239cb](https://github.com/Szesnasty/ai-protector/commit/c5239cb33841f447446501d6150c6f7a02bfc37d))
* **wizard:** spec 32 — agent traces & incidents persistence (50/50 tests) ([c900153](https://github.com/Szesnasty/ai-protector/commit/c900153fc3d27f3435686689bf944a7cb6c0777f))


### Bug Fixes

* agent detail – validation results, perm count, edit routing, delete button ([65e4574](https://github.com/Szesnasty/ai-protector/commit/65e4574ee63703821c22424d6d4ce18f6b0b5a43))
* align presets and seed with actual test agent tools, add table actions ([0b0e29a](https://github.com/Szesnasty/ai-protector/commit/0b0e29ad5b3c6dbea12aec52f92e5215d931b814))
* correct RAM estimates — include LLM Guard, NeMo, Presidio ML models ([06082fe](https://github.com/Szesnasty/ai-protector/commit/06082fe4580b34ecc4a7a76ba34b06731b458657))
* **frontend:** force 12px font on Quick Actions and Security Tests chips ([6d11262](https://github.com/Szesnasty/ai-protector/commit/6d11262cf142d39ef6219f93d501905415687b83))
* **frontend:** use correct Nuxt auto-import name for TestAgentChat component ([d7b8c5d](https://github.com/Szesnasty/ai-protector/commit/d7b8c5d73a461023c56ee05068fab2f37a2b22d5))
* include test agents in make demo/up, remove LLM Firewall subtitle ([2a84730](https://github.com/Szesnasty/ai-protector/commit/2a84730a53c2ed86b86d8e664dd14ecf089b98bb))
* **infra:** replace curl healthchecks with python urllib for test agents ([865e4c0](https://github.com/Szesnasty/ai-protector/commit/865e4c044c484c06df3efcb268fea89adadf7c56))
* **proxy:** eliminate false-positive blocking + add RBAC matrix UI ([9829801](https://github.com/Szesnasty/ai-protector/commit/98298014fede04db88834cb3f01dc7ddd4d63f38))
* RBAC getUsers admin-only, rearrange controls layout, reorganize sidebar nav ([c252d6b](https://github.com/Szesnasty/ai-protector/commit/c252d6b25d292477d509d0d309aa8f0496e58b22))
* **resilience:** add retry with exponential backoff to LLM calls ([d1d0a1b](https://github.com/Szesnasty/ai-protector/commit/d1d0a1bf3e25e3baf7bfaba2c8a94bfdafaaa398))
* restore versions to 0.1.9 and CHANGELOG from main ([0050941](https://github.com/Szesnasty/ai-protector/commit/0050941ac5691bcd092abd8a4d31ca9cfca59a15))
* **security:** eliminate ReDoS risk in PII regex patterns (CodeQL high) ([77b2596](https://github.com/Szesnasty/ai-protector/commit/77b2596fe4c68f872286ce31d404a6fc42cdbc78))
* sidebar overflow, wizard reset, kit template bugs (RBAC test + LimitsService) ([8760de8](https://github.com/Szesnasty/ai-protector/commit/8760de8e3089597ebbdb1bf8750551b35d0885d0))
* sync invisible_weight schema default to 0.8, fix test comments and nemo test values ([27812ad](https://github.com/Szesnasty/ai-protector/commit/27812adae9bd4d50b66c8d574ef5f93770ae5ee6))
* **test-agents:** pin exact package versions, fix module isolation, clarify protection.py role ([248d457](https://github.com/Szesnasty/ai-protector/commit/248d4572225e0497fd5f01765afa47e3cb3ff220))
* **test-agents:** render markdown in agent responses + improve text visibility ([8a60c44](https://github.com/Szesnasty/ai-protector/commit/8a60c4454c8dd55357af9a8324e0c1354446f06b))
* **test-agents:** two LLM-mode bugs in pure-python and langgraph agents ([cda99f7](https://github.com/Szesnasty/ai-protector/commit/cda99f78b17fab030bd791785822a7ea1c662cf3))
* **test-agents:** use /v1/scan for pre-scan, fix false positives ([c5f32a1](https://github.com/Szesnasty/ai-protector/commit/c5f32a1e8b74c3f4272d24253025c6fd2d2b7dcf))
* **test:** lower threshold in injection_balanced_block test ([054ffc4](https://github.com/Szesnasty/ai-protector/commit/054ffc47ded49a1fbac60866259229d712cbe771))
* **test:** revert injection_weight to 0.8, raise invisible_weight to 0.8, fix nemo/wizard test expectations ([895cb78](https://github.com/Szesnasty/ai-protector/commit/895cb78d0a9a155bca04dce2d6b224ba086117f7))
* **test:** sync all risk score expectations to injection_weight=0.5 default ([d6278a2](https://github.com/Szesnasty/ai-protector/commit/d6278a2765aff34444a7111a1b0e82f62fcac2c1))
* **test:** update injection risk score expectation to match 0.5 weight ([f3487a5](https://github.com/Szesnasty/ai-protector/commit/f3487a546dfbeffa139c26111281b2f9a1ffe5cd))
* **test:** use seed_wizard in test_seed_idempotent for CI compatibility ([5aba07c](https://github.com/Szesnasty/ai-protector/commit/5aba07c1353ad70b9fd9f7caf3f8485a6c12796a))
* **wizard:** use UPPERCASE enum names in aw_006 migration ([7af0c69](https://github.com/Szesnasty/ai-protector/commit/7af0c696d5c3aafafa811bc407413f483ed97794))

## [0.1.9](https://github.com/Szesnasty/ai-protector/compare/v0.1.8...v0.1.9) (2026-03-16)


### Bug Fixes

* **nemo:** add generic biographical safe patterns to prevent false positives ([8ae9039](https://github.com/Szesnasty/ai-protector/commit/8ae90393d10c827038a461277f2190d2000cc5b8))

## [0.1.8](https://github.com/Szesnasty/ai-protector/compare/v0.1.7...v0.1.8) (2026-03-16)


### Bug Fixes

* **nemo:** resolve supply_chain false positive on order-status queries ([ca8b051](https://github.com/Szesnasty/ai-protector/commit/ca8b05133039620bcf8c854ea76990848aa576de))

## [0.1.7](https://github.com/Szesnasty/ai-protector/compare/v0.1.6...v0.1.7) (2026-03-16)


### Bug Fixes

* **agent-demo:** align safe scenario prompts with ORD-xxx tool regex ([3007e8f](https://github.com/Szesnasty/ai-protector/commit/3007e8ff82349ba51f15208d2471e3e53d9ceac4))

## [0.1.6](https://github.com/Szesnasty/ai-protector/compare/v0.1.5...v0.1.6) (2026-03-16)


### Features

* add benchmark suite + JailbreakBench external validation ([2131a4a](https://github.com/Szesnasty/ai-protector/commit/2131a4a5023c5fc593282dabf29ac3833e0b03bc))


### Bug Fixes

* **bench:** break CodeQL taint flow by separating model and key detection ([84af624](https://github.com/Szesnasty/ai-protector/commit/84af624dcb7b31c720d2d76cc8374079a7aff901))
* **bench:** separate model name from api_key to resolve CodeQL alerts ([3928346](https://github.com/Szesnasty/ai-protector/commit/3928346a97cdaf742c62e36dd4c9b1f0c9c74a9d))
* **bench:** show full CPU name in benchmark reports ([2fbef89](https://github.com/Szesnasty/ai-protector/commit/2fbef89980f34bbddb7082dcace2a7762a951d1c))
* **nemo:** add safe coding examples to prevent false positives ([447851b](https://github.com/Szesnasty/ai-protector/commit/447851b39ac8d5d9ede08d85af9a291471f4e02f))
* **nemo:** expand safe_input examples to prevent false positives ([e5279a5](https://github.com/Szesnasty/ai-protector/commit/e5279a5e8f7553738231804c6fc225f042e9ee8c))
* **security:** prevent credential leaks in logs, traces, and API responses ([da70efe](https://github.com/Szesnasty/ai-protector/commit/da70efe61835dde4d5b55a4f7dbc23bb7fcb1ec0))

## [0.1.5](https://github.com/Szesnasty/ai-protector/compare/v0.1.4...v0.1.5) (2026-03-16)


### Bug Fixes

* **ci:** use npm ci with lockfile to resolve tinyexec ERR_MODULE_NOT_FOUND ([da00cf6](https://github.com/Szesnasty/ai-protector/commit/da00cf6114413382846940f87628cd1d4b1e1d0c))
* **ci:** use npm install instead of npm ci to avoid CI/Docker failures ([d2f2c3a](https://github.com/Szesnasty/ai-protector/commit/d2f2c3a076d0c3a7d9623f1a444ce8070b46d469))

## [0.1.4](https://github.com/Szesnasty/ai-protector/compare/v0.1.3...v0.1.4) (2026-03-12)


### Bug Fixes

* ensure demo seeds policies by default ([d9d94bd](https://github.com/Szesnasty/ai-protector/commit/d9d94bd0b62924437531eddb3f7d68ee89ea226a))

## [0.1.3](https://github.com/Szesnasty/ai-protector/compare/v0.1.2...v0.1.3) (2026-03-10)


### Bug Fixes

* **agent:** double /v1/ in scan URL — firewall always returned ALLOW ([20bf766](https://github.com/Szesnasty/ai-protector/commit/20bf766d94b36f93e5c6b161458608339419716d))

## [0.1.2](https://github.com/Szesnasty/ai-protector/compare/v0.1.1...v0.1.2) (2026-03-10)


### Performance Improvements

* scan-only endpoint + parallel Compare execution ([6bb7dbf](https://github.com/Szesnasty/ai-protector/commit/6bb7dbf6f4add7f5b2059754b8442ec85abcbe4c))

## [0.1.1](https://github.com/Szesnasty/ai-protector/compare/v0.1.0...v0.1.1) (2026-03-09)


### Features

* **01:** mock provider + MODE routing ([db89a6e](https://github.com/Szesnasty/ai-protector/commit/db89a6e118690124561f80a3d93f18c910023d47))
* **02:** Docker profiles + Makefile targets ([714ee0f](https://github.com/Szesnasty/ai-protector/commit/714ee0fe4d8726a5fac804c2ffea9c25e77a2e8f))
* **03:** CSP & security headers + CORS hardening ([c0dceac](https://github.com/Szesnasty/ai-protector/commit/c0dceacf44c4429b80557bb2820e4503c40df179))
* **04:** UI demo mode ([30744a1](https://github.com/Szesnasty/ai-protector/commit/30744a198f857205fb29a9da36dc4d4224862567))
* **05:** seed demo data script ([a28cb67](https://github.com/Szesnasty/ai-protector/commit/a28cb67c39fd7b7c31ccf389816c76ad3faf787e))
* **06d:** wire pipeline into chat router, graph integration tests ([bf804e5](https://github.com/Szesnasty/ai-protector/commit/bf804e5dc746bd7ca51f10e2f45131cc1da51620))
* **06:** README rewrite for GitHub landing page ([8ce7522](https://github.com/Szesnasty/ai-protector/commit/8ce7522876e18c2e05c6549721ff4d9fd3c14e52))
* **07a:** LLM Guard scanner node with 5 input scanners ([60159df](https://github.com/Szesnasty/ai-protector/commit/60159df82ae7ac5525f5816d7a4fcfe8b9bd9307))
* **07b:** Presidio PII detection & anonymization node ([3ccf876](https://github.com/Szesnasty/ai-protector/commit/3ccf8765545a2f8769fb6d819ffc991717be1b8b))
* **07c:** parallel scanner execution & pipeline integration ([69b433f](https://github.com/Szesnasty/ai-protector/commit/69b433f0ec875e707a248371ac918a56b0e9e663))
* **07:** enable CI workflows + release prep ([76a8078](https://github.com/Szesnasty/ai-protector/commit/76a8078477a640c8fd9602e975d04644b8b1dcec))
* **08a:** policies CRUD router — 5 endpoints with Redis invalidation ([8f24dfc](https://github.com/Szesnasty/ai-protector/commit/8f24dfcec1347236112efbacaad12fd1659151da))
* **08b:** policy config validation + seed data alignment ([9799f5e](https://github.com/Szesnasty/ai-protector/commit/9799f5e0a8bf5f8bdd4034c53c9c03ca87cfbc68))
* **08c:** policy-aware decision node with configurable weights ([decd51a](https://github.com/Szesnasty/ai-protector/commit/decd51ad7e95b898388ade845ef1a82e32444a09))
* **09a:** output filter node — PII, secrets & system prompt leak redaction ([7458e1f](https://github.com/Szesnasty/ai-protector/commit/7458e1fd1b00d5fe24955aacfa427c3bcb1e6f7f))
* **09b:** memory hygiene — conversation sanitization utility ([c1bd388](https://github.com/Szesnasty/ai-protector/commit/c1bd3881856e45a099c95d1af3a824e651d2a956))
* **09c:** logging node — Postgres audit + Langfuse tracing ([9bfc966](https://github.com/Szesnasty/ai-protector/commit/9bfc966317cf864c8c8cb09ccb0db8f85ef14226))
* **09d:** graph integration — output_filter + logging wired into pipeline ([4926ef3](https://github.com/Szesnasty/ai-protector/commit/4926ef3f4a34fad91d2262a1103b47b8d14eaa3b))
* add pentest E2E runner + scenario IDs + disable CI workflows ([a5cc03e](https://github.com/Szesnasty/ai-protector/commit/a5cc03e9f9b640779c2bfc9d8696768c0ba7d0a9))
* **agent-demo:** implement Step 11 — Customer Support Copilot ([56383cb](https://github.com/Szesnasty/ai-protector/commit/56383cb7d77be749ad8eec6cf8bfd91e481155d4))
* **agent-demo:** Step 12 — Agent ↔ Firewall Integration ([8b2198b](https://github.com/Szesnasty/ai-protector/commit/8b2198be92cf59405ce4cae0ca51b358eb651f75))
* **agent:** implement pre-tool enforcement gate (spec 01) ([c99c3be](https://github.com/Szesnasty/ai-protector/commit/c99c3be6134f0201ccbfcabab5203dcdfaee9568))
* **agent:** implement spec 02 — RBAC + Tool Allowlist ([300f109](https://github.com/Szesnasty/ai-protector/commit/300f109cf799463e782e60ca92506f34bd79e0d1))
* **agent:** implement spec 03 — Post-tool Enforcement Gate ([608109e](https://github.com/Szesnasty/ai-protector/commit/608109e058d7cf495ee1d76dc801c4ddd7644b32))
* **agent:** implement spec 04 — Argument Validation & Schema Enforcement ([6bb8040](https://github.com/Szesnasty/ai-protector/commit/6bb8040e0404a145ef74139658f9da2cb3aeecce))
* agents wizard docs - spec alignment + README pre-publish ([6751ea1](https://github.com/Szesnasty/ai-protector/commit/6751ea146b9f857b1697296023eaf01ceae9d9db))
* **agent:** spec 07 — Agent Trace Phase 1 (in-memory trace + API response) ([a995751](https://github.com/Szesnasty/ai-protector/commit/a9957512e5b595f516d09eef238637339a45f0bd))
* **agent:** spec 07 Phase 2+3 — trace store, REST API, Langfuse, export ([f5d643c](https://github.com/Szesnasty/ai-protector/commit/f5d643cbb99c3518b46a965722782d54c191e10e))
* **agents:** spec 05 — message role separation & anti-spoofing ([01ac16a](https://github.com/Szesnasty/ai-protector/commit/01ac16a6bc2a881a5119b36e282729ab1c3f881f))
* **agents:** spec 06 — limits, rate limiting, iteration caps, budget caps ([c0acb8b](https://github.com/Szesnasty/ai-protector/commit/c0acb8bb50360b15a9fedb5d780aa54c46dc9eac))
* **compare:** add dedicated attack scenarios panel for Compare Playground ([4ae154e](https://github.com/Szesnasty/ai-protector/commit/4ae154eddbb7bcbe3781c26979056b9a1c70fffe))
* **compare:** direct browser to provider API for right panel ([8afe771](https://github.com/Szesnasty/ai-protector/commit/8afe77118428e5dfaf3a311a000d2058de2eb880))
* **compare:** two-mode compare system with semantic color logic ([20a19bc](https://github.com/Szesnasty/ai-protector/commit/20a19bc616555b10a1da9cf4410c5af54e5df293))
* expand attack scenarios to 157 playground + 103 agent (from 57+48), panels collapsed by default ([83ecc2a](https://github.com/Szesnasty/ai-protector/commit/83ecc2a59463ee2bbbe0c78a82b3c5ba2da6dd34))
* expand attack scenarios with OWASP LLM Top 10 2025 research (+98 items, +14 groups) ([424aea2](https://github.com/Szesnasty/ai-protector/commit/424aea24b252846fe68c08a262bef1cd24f96f32))
* **frontend:** add visible tooltip icons to chips and improve info styling ([ff318b6](https://github.com/Szesnasty/ai-protector/commit/ff318b6603451c177cf25ffd056032290778f3e6))
* **frontend:** Agent Traces page — browse, filter, expand, export traces ([09a09c7](https://github.com/Szesnasty/ai-protector/commit/09a09c77c5f201468e29563cc27d02e32fb9e46d))
* **frontend:** fresh data, alphabetical scenarios, autocomplete filter, policy ordering ([7ffc6a5](https://github.com/Szesnasty/ai-protector/commit/7ffc6a5d8d94ca314be3f0ce4f99a2641c411c94))
* **frontend:** implement Step 05 — Frontend Foundation ([fdd419b](https://github.com/Szesnasty/ai-protector/commit/fdd419b789c687549cb32e27bf77c227cb9e2c8f))
* **frontend:** inline pipeline decision in chat messages, update MVP-PLAN ([4170aa4](https://github.com/Szesnasty/ai-protector/commit/4170aa416bc79dc552ff255c70cb0f0df384037b))
* **frontend:** remember last selected model per view in localStorage ([db6e320](https://github.com/Szesnasty/ai-protector/commit/db6e320629cc5ff843646f0dee1f9052d3780418))
* **frontend:** Step 13 — Agent Demo UI ([d4a6f39](https://github.com/Szesnasty/ai-protector/commit/d4a6f399dc83e2d78ae23c75416a70af8c31261b))
* **frontend:** unified semantic color system, request log UX, settings security info ([23cb871](https://github.com/Szesnasty/ai-protector/commit/23cb871f13659115c3419931851493e2348fc506))
* near-realtime analytics — sub-minute polling, 5m/15m ranges ([7fef20d](https://github.com/Szesnasty/ai-protector/commit/7fef20d20a923be19f1bfc43306c71bbefd22c6a))
* **nemo:** add NeMo Guardrails to policy editor UI + backend validation ([0ccd62a](https://github.com/Szesnasty/ai-protector/commit/0ccd62adee8382e9f3c95e42d167ec6226ec747c))
* **policies:** make built-in policies read-only ([7d162b6](https://github.com/Szesnasty/ai-protector/commit/7d162b6ef7fbbfb42d5d1c17d90b6f2b8b173b78))
* pre-commit hooks, coverage badge, session-scoped DB fixture ([07f0275](https://github.com/Szesnasty/ai-protector/commit/07f027568f17cae724386de416bd98c7d3ee40f4))
* preload ML models on startup + add known issues tracker ([2434ec2](https://github.com/Szesnasty/ai-protector/commit/2434ec28e4450673212e2fa124d061c72ef5e633))
* real-time system metrics in health popover (RAM, CPU, disk, uptime, threads, requests) ([1be0958](https://github.com/Szesnasty/ai-protector/commit/1be0958c566eff54717e1430efcd0ab4c091f746))
* show only available models + move API URLs to env vars ([5f1348c](https://github.com/Szesnasty/ai-protector/commit/5f1348c36a5bd18d877a163d634a3887829f9e1c))
* skull FAB button + expanded scenarios (57 Playground, 48 Agent) ([2a938e1](https://github.com/Szesnasty/ai-protector/commit/2a938e192be72ec2931ef8bf4d555e266c9783fe))
* step 01 — project scaffolding ([a0cd268](https://github.com/Szesnasty/ai-protector/commit/a0cd268484b157bdfbdf9a62cfcc31377a4652b7))
* step 02 — infrastructure (Docker Compose) ([5fb8ef9](https://github.com/Szesnasty/ai-protector/commit/5fb8ef9a3d8613539407350aa0e0c7debb69e2df))
* Step 20 — Attack Scenarios Panel with 40 attack prompts for live demos ([9e3c0e0](https://github.com/Szesnasty/ai-protector/commit/9e3c0e04b1011738678a53934d193c93ecbea73f))
* **step-03:** proxy service foundation ([829979e](https://github.com/Szesnasty/ai-protector/commit/829979e1b2b830a3dcba00f2dbdd5fa4161cfc2e))
* **step-04a:** LiteLLM client, chat schemas, LLM exceptions ([6a5797c](https://github.com/Szesnasty/ai-protector/commit/6a5797c37222d62250d820587459cfbf7c758315))
* **step-04b:** chat completions endpoint with SSE streaming ([1dcdeaf](https://github.com/Szesnasty/ai-protector/commit/1dcdeafbc3afe5bb413f08bbf58ebefdd282b246))
* **step-04c:** request logger, 27 tests, spec checkboxes updated ([a17a863](https://github.com/Szesnasty/ai-protector/commit/a17a863651c9a197c2e0aecf4e304ea1ce3d1187))
* **step-06a:** PipelineState, timed_node decorator, ParseNode ([93d637f](https://github.com/Szesnasty/ai-protector/commit/93d637fe37838ee86242bc1d8d1da88949ce4403))
* **step-06b:** IntentNode, RulesNode, denylist service, seed phrases ([47d6f1f](https://github.com/Szesnasty/ai-protector/commit/47d6f1f2e562303b98b3748a3e2acf17132bcad6))
* **step-06c:** DecisionNode, TransformNode, LLMCallNode, StateGraph pipeline ([8585bd1](https://github.com/Szesnasty/ai-protector/commit/8585bd1c6f341f090d25ed80f37d8d9b2afbd73e))
* **step-14:** custom security rules — model, CRUD API, pipeline integration, frontend editor ([988e111](https://github.com/Szesnasty/ai-protector/commit/988e111fa9cf494c1c3e0a31526f041650cca4b1))
* **step-15:** policies CRUD UI, request log API & UI ([0c124ea](https://github.com/Szesnasty/ai-protector/commit/0c124eae719cd4feb6cc0e88d9299d11751dd077))
* **step-16:** analytics API & dashboard UI ([fb4024d](https://github.com/Szesnasty/ai-protector/commit/fb4024d7baf0c5c1db48eb5d47723afe0936cc5b))
* **step-22:** implement NeMo Guardrails + agent security hardening ([a3410b4](https://github.com/Szesnasty/ai-protector/commit/a3410b4092931e9d596929fafe088427cd014684))
* **step-23:** external LLM providers with SessionStorage API keys ([cce3719](https://github.com/Szesnasty/ai-protector/commit/cce3719e54f09a8327b6e52a8d07c889595242e9))
* **step-24:** compare playground — proxy vs direct side-by-side ([ba2c43a](https://github.com/Szesnasty/ai-protector/commit/ba2c43a4473c795e14bd2711d25bce61e2034cda))
* **step-24:** refactor Compare — external-only, sequential requests ([ce03457](https://github.com/Szesnasty/ai-protector/commit/ce03457026f3ad29fb805e916a95832380faeac1))
* **ui:** comprehensive UI overhaul ([b46fc25](https://github.com/Szesnasty/ai-protector/commit/b46fc254f049b7f16dd28cc66056ad0c1914800e))
* update UI components, attack scenarios panel, and logo assets ([0e53ada](https://github.com/Szesnasty/ai-protector/commit/0e53ada6392ed97bc8bc0bfb50c1c674c85643d8))


### Bug Fixes

* **01:** mock_completion returns attr-accessible object ([6bae5d5](https://github.com/Szesnasty/ai-protector/commit/6bae5d526cd66ac09da4b5cf4bb61da0b161929d))
* **agent:** extract order ID from '[#12345](https://github.com/Szesnasty/ai-protector/issues/12345)' format and show correct block reason ([ecd1bd9](https://github.com/Szesnasty/ai-protector/commit/ecd1bd9a9b07e57f9e25480bb0efa13667e2ab82))
* **agent:** route user message through proxy firewall in demo mode ([680b272](https://github.com/Szesnasty/ai-protector/commit/680b272238eab6e5fb68d6ac04e6a2cbf379497a))
* **agent:** two-phase LLM call for full tool context ([5fcc753](https://github.com/Szesnasty/ai-protector/commit/5fcc753d18d9cea8dda77fb314d5797191eb98cb))
* **ci:** fix release-please — add version.txt, use generic updaters ([d902f3d](https://github.com/Szesnasty/ai-protector/commit/d902f3d40a82b103bfdffdbf89a5241ee9c0e2c1))
* Compare playground + policy save in demo mode ([7b44e18](https://github.com/Szesnasty/ai-protector/commit/7b44e181b3c5f132bdf118543336e69b8042b802))
* **compare:** robust error handling, error display, CORS expose_headers ([7c97f5a](https://github.com/Szesnasty/ai-protector/commit/7c97f5a8063dc41831001aebd3fd3e8654671190))
* **compare:** validate API key before send, smarter auto-select ([897e855](https://github.com/Szesnasty/ai-protector/commit/897e855ba547824aea4db298e1cd7687a3b30f78))
* downgrade zod to v3 for vee-validate compatibility, use npm install in Dockerfile ([bff70ba](https://github.com/Szesnasty/ai-protector/commit/bff70babb27f8b1c0708efd7f2bd4759ba61a080))
* echarts renderer + MDI/Vuetify CSS loading ([76279c4](https://github.com/Szesnasty/ai-protector/commit/76279c4f4bb707146eae02a38072bdc82f1f52c4))
* eliminate FOUC — restore SSR CSS, strip 404 dupes via Nitro plugin ([c1fd723](https://github.com/Szesnasty/ai-protector/commit/c1fd723f8d6ce2e7deef19eaeaa144c6dae608ef))
* eliminate vuetify/MDI CSS 404s in dev SSR ([cb17d43](https://github.com/Szesnasty/ai-protector/commit/cb17d43077e2503a13952936152118c2221e3d09))
* ensure all requests are logged to Analytics/Request Log ([c835618](https://github.com/Szesnasty/ai-protector/commit/c8356188f5aa59e559bc8bd29eba33fe14a7acc6))
* expand .gitignore, fix .output/x typo ([f159c35](https://github.com/Szesnasty/ai-protector/commit/f159c35ad51a698eeb941376b54c0bb86dbde9f5))
* expand model catalog with current IDs from all providers ([3978c4b](https://github.com/Szesnasty/ai-protector/commit/3978c4b54e7cbcc899a3782aed01888c6517fa9f))
* **frontend:** rename agent components to avoid double prefix ([fff4ed4](https://github.com/Szesnasty/ai-protector/commit/fff4ed4b5df562ae7ec81ca0c38a6febe0a67729))
* **frontend:** resolve Vuetify styles and MDI font CSS 404s ([cba719a](https://github.com/Szesnasty/ai-protector/commit/cba719aff4a52b3774006408b6554a55e10e3ed2))
* **frontend:** single nav drawer, remove no-gutters, fix policies endpoint ([7f2eecb](https://github.com/Szesnasty/ai-protector/commit/7f2eecb0998e4ed83e99d3038e190c5363fcfa1a))
* **ISS-001:** hot-reload LLM Guard scanners on threshold change ([4a68908](https://github.com/Szesnasty/ai-protector/commit/4a68908e9a96300c54f84bf16a49cabf71404f47))
* **models:** make model availability reactive to API key changes ([2fd02ce](https://github.com/Szesnasty/ai-protector/commit/2fd02ce194b6a9581cd06c161cf990e1bf04e8af))
* **nemo:** eliminate LLM dependency and use proper fallback_intent API ([f36c189](https://github.com/Szesnasty/ai-protector/commit/f36c189a1235c5dfbcc03de424d21e33b1df5d8f))
* push pending CI fixes, dockerignore files, ruff F541 lint ([1edcfe2](https://github.com/Szesnasty/ai-protector/commit/1edcfe2912751761c5de200a2fc4f5f1466a83a0))
* remove broken item.raw Vuetify slot + fix _keyVersion pattern ([49b7d8b](https://github.com/Szesnasty/ai-protector/commit/49b7d8b8dbe8265fa4fddd1c87e5377f28de93c5))
* remove gemini-2.0-flash-lite (unsupported) ([6f23981](https://github.com/Szesnasty/ai-protector/commit/6f2398161e1009621d1b7414c508b786bfdc12e5))
* route gemini-* models to Google instead of Ollama ([9f2af6e](https://github.com/Szesnasty/ai-protector/commit/9f2af6eb555e18127a252e7323f0fdb998f4a684))
* **step-24:** add missing compare-panel.vue component ([61cfeae](https://github.com/Szesnasty/ai-protector/commit/61cfeaeff9bfa10effcfefab9ade1d96510dc368))
* streaming requests were not logged to DB — analytics blind spot ([fda8a4d](https://github.com/Szesnasty/ai-protector/commit/fda8a4de6bddad4e0edf3290577b99dd668bca46))
* switch useModels from useAsyncData to useQuery ([4be56a4](https://github.com/Szesnasty/ai-protector/commit/4be56a4e8d524d915fba71f9e13738940556e2e3))
* timer cleanup, analytics background polling, model selection across all pages ([9dbde4e](https://github.com/Szesnasty/ai-protector/commit/9dbde4ea5e255771c2ce5dc91f31d4e16ebc3ea5))
* **traces:** surface firewall blocks in agent trace summary and UI ([d757ed1](https://github.com/Szesnasty/ai-protector/commit/d757ed117335ab15c0f17111561e3a51821d6dd7))
* **ui:** disable ML Judge and Canary chips with coming soon tooltip ([7fd4162](https://github.com/Szesnasty/ai-protector/commit/7fd4162a0baa6a6c1679449f16cb8e8fd4ba8a54))
* **ui:** fix node labels and block reason in Agent Traces ([5982b69](https://github.com/Szesnasty/ai-protector/commit/5982b695f8063aa1bcbaeb9d5182dc1bdbc26059))
* **ui:** make sidebar scrollable on all screen sizes ([26fecc5](https://github.com/Szesnasty/ai-protector/commit/26fecc534512dcd09e2a4bed0c2d2ff077d6cfc5))
* **ui:** use proper display names for scanner labels (LLM Guard, NeMo Guardrails, etc.) ([3b9ae24](https://github.com/Szesnasty/ai-protector/commit/3b9ae243b1a2d4d2e4b7e3f1d4d019b08b4356bd))
* update Anthropic model IDs to current versions ([164d683](https://github.com/Szesnasty/ai-protector/commit/164d683f9c0441c534cf40f3159714678c2fcb74))


### Performance Improvements

* fix CPU spike — stop defaulting to Ollama, reduce health polling ([a9f13f5](https://github.com/Szesnasty/ai-protector/commit/a9f13f5942a2a211b84b01be3832bb06a0a0940c))


### Reverts

* **frontend:** restore classic dark/light theme, remove cyberpunk palettes ([f6997a6](https://github.com/Szesnasty/ai-protector/commit/f6997a668ec3f79297bb045172cb73c535d643a0))
