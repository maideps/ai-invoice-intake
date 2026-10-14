"""Generate the synthetic invoice samples.

From the repository root: ``npm run samples`` (seed 42, 12 invoices, into ``samples/invoices``).
Directly, from ``repositories/backend/``:
``python tools/generate_samples.py --seed 7 --count 30 --out DIR``.
"""

import argparse
import sys
from pathlib import Path

from samplegen.generate import DEFAULT_COUNT, DEFAULT_SEED, generate

REPO_SAMPLES = Path(__file__).resolve().parents[3] / "samples" / "invoices"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--out", type=Path, default=REPO_SAMPLES)
    args = parser.parse_args(argv)

    written = generate(args.out, seed=args.seed, count=args.count)
    print(f"Wrote {len(written) // 2} invoices (seed {args.seed}) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
