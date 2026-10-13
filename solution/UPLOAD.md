# Upload guide

## Selected deliverable

- Use **V1**, fully evaluated at **9/12**. Exact matching source/Dockerfile:
  [submission/fixer/](submission/fixer/). Current `fixer/` is experimental V2,
  not the selected runtime.
- Selected image: `c3-fixer-prototype:v1-final`, also `:best-verified`.
- Preserved image tar: [prototype-v1-final.tar](../results/prototype-v1-final.tar).
- [Final write-up](WRITEUP.md): at most 450 words.
- [Selection/hashes](benchmarks/selected-version.json),
  [complete V1 scorecard](benchmarks/v1-final-evaluation.json),
  [V1 build chats](../evidence/build-chats/manifest.json), and
  [later development chats](evidence/build-chats-r4-final/manifest.json).
- [Future work](<future work.md>) records incomplete evaluations and V3 plans.

## Ready-to-upload archive

Run from repository root:

```sh
python3 -B solution/package_submission.py
```

Output: `solution/upload/c3-submission-v1.tar.gz` and its SHA-256 file.
The package contains the selected image/source, concise documentation, test
helpers, sanitized scorecards, retained run summaries/logs/patches and public
redacted chat snapshots. Experimental V2 code is clearly separate.

The packager verifies the selected image hash, V1 source hashes, document word
limits, chat hashes, path containment and every archived member's hash. It rejects
symlinks/credential filenames and checks text for common real credential formats.
Three exact synthetic credentials in redaction fixtures are allowlisted; files are
not exempted from scanning.
It never reads `.env`. These checks reduce exposure risk but are not a formal
guarantee that arbitrary prose contains no sensitive information.

Excluded: `.git`, `.env`, replay traces, scratch workspaces, caches, runner proxy
state, redundant chat checkpoints, experimental image tarballs and generated
upload archives. Original assessment corpus/cases/grader are not duplicated in
the submission package; use the provided assessment repository to rerun grading.

## Git upload versus file upload

- Git tracks source, tests, docs and scorecards. Ignored image/log/chat artifacts
  are **not** included in a normal push; send the generated archive for the full
  assessment handoff.
- `.env` remains locally available and ignored. Do not upload the entire working
  directory or force-add ignored files. No key was read for packaging.
- No push, registry publication or external submission has been performed.

## Cleanup and evidence limits

- Bulky replay/scratch/cache data was moved outside the repository, not destroyed;
  [cleanup manifest](cleanup-manifest.json) records the recovery location.
- Nineteen detailed controller reports were retained under
  `solution/evidence/runtime-reports/`; result/eval JSON, patches, fixer logs,
  selected image and required chats remain intact.
- Recovery is temporary: the operating system may eventually clean `/private/tmp`.
- All authored write-ups are ≤3,000 words; `WRITEUP.md` is ≤450. Supplied
  `v2_architecture.md`/`v3_architecture.md` are preserved unchanged, not rewritten.
- Chat exports have explicit cutoffs; the latest snapshot may predate final
  bookkeeping/cleanup. No complete V2 or unseen-case success is claimed.
