"""Write a set of samples (PDF plus ground-truth JSON per invoice) to a directory."""

from pathlib import Path

from .builder import build_sample
from .ground_truth import dumps
from .render import render_pdf

DEFAULT_SEED = 42
DEFAULT_COUNT = 12
SAMPLE_GLOBS = ("invoice-*.pdf", "invoice-*.json")


def generate(out_dir: Path, seed: int = DEFAULT_SEED, count: int = DEFAULT_COUNT) -> list[Path]:
    """Replace the samples in ``out_dir`` with ``count`` new ones; return the files written.

    Only files named like samples are removed, so anything else in the directory is kept.
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    out_dir.mkdir(parents=True, exist_ok=True)
    for pattern in SAMPLE_GLOBS:
        for stale in out_dir.glob(pattern):
            stale.unlink()

    written: list[Path] = []
    for index in range(count):
        sample = build_sample(seed, index)
        pdf_path, json_path = out_dir / sample.pdf_name, out_dir / sample.json_name
        pdf_path.write_bytes(render_pdf(sample))
        json_path.write_bytes(dumps(sample))
        written += [pdf_path, json_path]
    return written
