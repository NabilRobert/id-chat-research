# Third-party software

The runtime dependencies, with the licences their packages declare
(checked 2026-11-09 from the installed metadata). All allow use in this
MIT repo (ADR-013). No model weights or datasets are used yet.

| Package | Version | Licence | Used for |
|---|---|---|---|
| presidio-analyzer | 2.2.366 | MIT | Recogniser framework and phone recogniser |
| spaCy | 3.8.18 | MIT | Tokeniser for Presidio (blank Indonesian pipeline, no model) |
| phonenumbers | 9.0.43 | Apache-2.0 | Phone parsing, via Presidio |
| regex | 2026.9.29 | Apache-2.0 | Pattern matching, via Presidio |
| tldextract | 5.4.0 | BSD-3-Clause | Installed by Presidio; not called (its email check fetches over the network) |
| Faker | 40.44.0 | MIT | Names, streets and emails for synthetic chats |
| Pydantic | 2.14.3 | MIT | The chat record and labelled-chat models |
| PyYAML | 6.0.3 | MIT | Reading templates |
| Typer | 0.27.3 | MIT | The `id-chat` CLI |

Dev tools (not shipped): ruff (MIT), pyright (MIT), pytest (MIT),
gitleaks (MIT, in CI).
