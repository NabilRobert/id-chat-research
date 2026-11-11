"""The NER half of the anonymiser (R1): local models for names and addresses.

Optional: it needs the `ner` extra (torch, transformers, onnxruntime,
gliner) and model weights fetched by `id-chat fetch-models`. The rules
(R0) never import it, so the anonymiser works without either (ADR-004).
"""
