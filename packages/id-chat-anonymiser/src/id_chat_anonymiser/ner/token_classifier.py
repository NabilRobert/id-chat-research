"""Running a BIO token classifier (NusaBert, Horizon) over one text.

The tokenizer is the `tokenizers` library's, read from the model's
tokenizer.json, so both runtimes share it and its character offsets. Long
texts are cut into overlapping windows rather than truncated: a truncated
message would leave its tail unchecked, which fails open. Spans found
twice in an overlap are merged later with everything else.

Only the logits step differs: PyTorch for NusaBert, which ships no ONNX
export, and ONNX Runtime for Horizon's int8 export (ADR-004).
"""

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from id_chat_anonymiser.ner.models import ModelSpec, Runtime
from id_chat_anonymiser.ner.spans import NerSpan, TokenPrediction, decode_bio

MAX_TOKENS = 512
# Spans whose mean word probability is lower are dropped: the default in
# Horizon's own redact.py, and GLiNER's threshold, so all three compare alike.
MIN_SPAN_SCORE = 0.5
WINDOW_OVERLAP_TOKENS = 64
# Leaves cores free for other work on the laptop; the benchmark reports speed at this setting.
CPU_THREADS = 4

Logits = NDArray[np.float32]
LogitsFunction = Callable[[Sequence[int], Sequence[int]], Logits]


def predictions(
    logits: Logits, offsets: Sequence[tuple[int, int]], id_to_label: Mapping[int, str]
) -> list[TokenPrediction]:
    """Each token's most likely label and its softmax probability."""
    shifted = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probabilities = shifted / shifted.sum(axis=-1, keepdims=True)
    best = probabilities.argmax(axis=-1)
    return [
        TokenPrediction(
            label=id_to_label[int(best[position])],
            score=float(probabilities[position, best[position]]),
            start=start,
            end=end,
        )
        for position, (start, end) in enumerate(offsets)
    ]


class TokenClassifier:
    def __init__(self, spec: ModelSpec, folder: Path) -> None:
        from tokenizers import Tokenizer

        config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        self._id_to_label = {int(index): label for index, label in config["id2label"].items()}
        self._labels = spec.labels
        self._tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tokenizer.no_padding()
        self._tokenizer.enable_truncation(  # pyright: ignore[reportUnknownMemberType]
            MAX_TOKENS, stride=WINDOW_OVERLAP_TOKENS
        )
        if spec.runtime is Runtime.ONNX:
            self._logits = _onnx_logits(folder / spec.weights)
        else:
            self._logits = _torch_logits(folder)

    def find(self, text: str) -> list[NerSpan]:
        encoding = self._tokenizer.encode(text)
        spans: list[NerSpan] = []
        for window in [encoding, *encoding.overflowing]:
            logits = self._logits(window.ids, window.attention_mask)
            tokens = predictions(logits, window.offsets, self._id_to_label)
            spans.extend(decode_bio(tokens, self._labels, text))
        return [span for span in spans if span.score >= MIN_SPAN_SCORE]


def _torch_logits(folder: Path) -> LogitsFunction:
    import torch
    from transformers import AutoModelForTokenClassification

    torch.set_num_threads(CPU_THREADS)
    model = cast(Any, AutoModelForTokenClassification).from_pretrained(
        folder, local_files_only=True
    )
    model.eval()

    def run(ids: Sequence[int], mask: Sequence[int]) -> Logits:
        with torch.inference_mode():
            output = model(input_ids=torch.tensor([ids]), attention_mask=torch.tensor([mask]))
        return cast(Logits, output.logits[0].float().numpy())

    return run


def _onnx_logits(weights: Path) -> LogitsFunction:
    import onnxruntime as untyped_onnxruntime  # pyright: ignore[reportMissingTypeStubs]

    # onnxruntime ships no type stubs; it is used through `Any`, typed at the edges.
    onnxruntime = cast(Any, untyped_onnxruntime)
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = CPU_THREADS
    session = onnxruntime.InferenceSession(
        str(weights), sess_options=options, providers=["CPUExecutionProvider"]
    )
    input_names = {str(model_input.name) for model_input in session.get_inputs()}

    def run(ids: Sequence[int], mask: Sequence[int]) -> Logits:
        feeds = {
            "input_ids": np.array([ids], dtype=np.int64),
            "attention_mask": np.array([mask], dtype=np.int64),
        }
        used_feeds = {name: value for name, value in feeds.items() if name in input_names}
        outputs = session.run(None, used_feeds)
        return cast(Logits, np.asarray(outputs[0])[0])

    return run
