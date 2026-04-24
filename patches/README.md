# vLLM patches

Unified-diff patches applied on top of the base image in `../Dockerfile`.
Applied in filename order at build time.

## Rules

- Diffs are `-p1` rooted at `/`, so paths start with
  `usr/local/lib/python3.12/dist-packages/...`
- Each patch is one reviewable change with a prefixed number
  (`NNNN-short-slug.patch`)
- Each patch includes an in-code comment citing the upstream issue/PR so
  a future reader knows when it can be retired after a base-image bump

## Adding a patch

```bash
F=vllm/v1/core/sched/scheduler.py      # file to patch (relative to vllm/)
BASE=$(sed -n 's/^ARG VLLM_BASE_IMAGE=//p' ../Dockerfile)

docker run --rm "$BASE" cat "/usr/local/lib/python3.12/dist-packages/$F" > orig
cp orig patched && $EDITOR patched
diff -u --label "a/usr/local/lib/python3.12/dist-packages/$F" \
        --label "b/usr/local/lib/python3.12/dist-packages/$F" \
        orig patched > NNNN-slug.patch
docker build ..                        # must succeed
```