# Third-party software

The runtime dependencies, with the licences their packages declare
(checked from the installed metadata: 2026-11-09 for the core, 2026-11-10
for the `ner` group). All allow use in this MIT repo (ADR-013).

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

**Optional `ner` group** (R1, `uv sync --group ner`):

| Package | Version | Licence | Used for |
|---|---|---|---|
| torch | 2.14.1 | BSD-3-Clause, with bundled Apache-2.0, MIT and others | Running NusaBert and GLiNER on CPU |
| transformers | 5.16.1 | Apache-2.0 | Loading NusaBert |
| onnxruntime | 1.31.1 | MIT | Running Horizon's ONNX export |
| gliner | 0.2.29 | Apache-2.0 | Running GLiNER |
| tokenizers | 0.23.3 | Apache-2.0 | Tokenising for the token classifiers |
| huggingface-hub | 1.33.0 | Apache-2.0 | `fetch-models`, and finding models in the cache |
| sentencepiece | 0.2.2 | Apache-2.0 | GLiNER's tokenizer |
| numpy | 2.4.6 | BSD-3-Clause and others | Softmax over model outputs |

**Model weights** (downloaded by `id-chat fetch-models` into the Hugging
Face cache, never committed or redistributed):

| Model | Commit | Licence | Note |
|---|---|---|---|
| `cahya/NusaBert-ner-v1.3` | `befa872` | MIT (model card) | Trained on NERGrit, whose original repo is gone (ADR-004) |
| `Horizon-Labs/pii-redactor-base` (int8 ONNX) | `ef0eff8` | Apache-2.0 | Trained on CC-BY-4.0 data: attribution is owed upstream |
| `urchade/gliner_multi-v2.1` | `443d26d` | Apache-2.0 | |
| `microsoft/mdeberta-v3-base` (tokenizer and config only) | `a048466` | MIT | Needed by GLiNER |

Dev tools (not shipped): ruff (MIT), pyright (MIT), pytest (MIT),
gitleaks (MIT, in CI).
