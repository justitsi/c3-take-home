# Selected submission: V1

This directory contains the exact V1 source from finalized commit `96e06b2`,
not the experimental V2 tree at `../fixer/`.

- Runtime/build context: [fixer/](fixer/).
- Final explanation: [WRITEUP.md](../WRITEUP.md), at most 450 words.
- Evidence: [V1 scorecard](../benchmarks/v1-final-evaluation.json), **9/12** across six cases.
- Existing image: `c3-fixer-prototype:v1-final`, also `:best-verified`.
- Image tar: [prototype-v1-final.tar](../../results/prototype-v1-final.tar).
- Packaging instructions: [UPLOAD.md](../UPLOAD.md).

The Dockerfile's historical example comment names another tag; build from this
directory using the command below. Its bytes are deliberately unchanged.

```sh
# From repository root; use a new tag, preserving the graded image.
docker build --platform linux/amd64 -t c3-fixer-prototype:upload-rebuild solution/submission/fixer
```

A rebuild is not automatically the previously graded image. Prefer the preserved
tar for submission; any replacement image needs its own verification.

`tests/`, `benchmark.py` and `export_build_chats.py` are the original V1 offline
verification helpers. They are outside the runtime image context. Run without
network/model calls:

```sh
docker run --rm --network none --cpus 2 --memory 1g \
  --mount "type=bind,source=$PWD/solution/submission,target=/solution,readonly" \
  --entrypoint python c3-fixer-prototype:v1-final \
  -m pytest -q -p no:cacheprovider /solution/tests
```

V1 does not include V2's later rollback/trace/probe features. The finite practice
result is not a guarantee for unseen services.
