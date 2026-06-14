#!/usr/bin/env python3
"""kb_embed — bake pre-computed embeddings into a knowledge-base directory.

WHY (v0.2.17 keystone): `kb_loader` embeds every doc synchronously at boot,
one Vertex round-trip (~200ms) per doc. A large KB (full ATT&CK Enterprise is
~691 docs; the whole expansion arc ~5k) is then 16+ minutes on a fresh-volume
install, plus a Vertex bill every time. This authoring tool embeds a KB dir's
docs ONCE at build time and writes the vector back into each doc's front-matter
(markdown) or object (JSON), as:

    embedding:        <base64 little-endian float32[dims]>
    embedding_model:  <model id, e.g. text-embedding-004>

At boot, `kb_loader._extract_precomputed_embedding` + `kb_store.upsert` trust
that vector when its `embedding_model` matches the runtime embedder's
`model_id` and its length matches `dims` — skipping the Vertex call entirely.
Any mismatch falls back to embed-on-boot, so a stale bake is self-healing.

USAGE
  # Deterministic stub (no creds — for CI / round-trip tests / demos):
  python kb_embed.py <kb_dir> --embedder stub

  # Real Vertex bake (authoring time; needs a service-account JSON):
  python kb_embed.py <kb_dir> --embedder vertex \\
      --sa-json /path/sa.json --project my-proj --region us-central1

  # Preview without writing:
  python kb_embed.py <kb_dir> --embedder stub --dry-run

The tool reuses `kb_loader`'s parsing so the content it embeds is byte-for-byte
what the loader will store. It does NOT touch docs that already carry a matching
`embedding_model` unless --force is given (idempotent re-runs are cheap).
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
from pathlib import Path
from typing import Any

# Make the embedded-MCP source importable (kb_loader, embedders).
# __file__ = bundles/spark/kbs/_tools/kb_embed.py → parents[2] = bundles/spark
_MCP_SRC = Path(__file__).resolve().parents[2] / "mcp" / "src"
sys.path.insert(0, str(_MCP_SRC))

import yaml  # noqa: E402

from usecase import kb_loader  # noqa: E402
from usecase.memory_store import TextHashEmbedder  # noqa: E402


def _encode(vec: list[float]) -> str:
    """Pack a float vector as base64 little-endian float32 — matches the
    decode in kb_loader._extract_precomputed_embedding."""
    return base64.b64encode(struct.pack(f"<{len(vec)}f", *vec)).decode("ascii")


class _RestVertexEmbedder:
    """Authoring-time embedder that calls Vertex text-embedding-* over REST
    with a bearer access token — no SecretStore / ProviderStore needed.

    Mirrors `providers/vertex/src/provider.embed` EXACTLY (body
    `{"instances":[{"content": text}]}`, regional endpoint, model id) so the
    baked DOC vectors live in the SAME space the runtime embeds QUERIES into.
    `model_id` is reported as the bare model (e.g. text-embedding-004) so it
    matches the runtime embedder's `model_id` and the loader trusts the bake.
    """

    def __init__(self, token: str, project: str, region: str, model: str, dims: int) -> None:
        self._token = token
        self._project = project
        self._region = region if region and region != "global" else "us-central1"
        self.model_id = model
        self.dims = dims

    def embed(self, text: str) -> list[float]:
        import urllib.request

        if not text.strip():
            return [0.0] * self.dims
        url = (
            f"https://{self._region}-aiplatform.googleapis.com/v1/projects/"
            f"{self._project}/locations/{self._region}/publishers/google/"
            f"models/{self.model_id}:predict"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps({"instances": [{"content": text}]}).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 — trusted GCP host
            data = json.loads(r.read().decode("utf-8"))
        return data["predictions"][0]["embeddings"]["values"]


def _build_embedder(args: argparse.Namespace) -> Any:
    if args.embedder == "stub":
        return TextHashEmbedder(dims=args.dims)
    if args.embedder == "vertex-rest":
        # Bearer-token REST path — simplest authoring bake (e.g. a developer's
        # `gcloud auth print-access-token`). No SA JSON file needed.
        import subprocess

        token = args.access_token
        if not token:
            token = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        if not args.project:
            sys.exit("--embedder vertex-rest requires --project (and a token)")
        return _RestVertexEmbedder(token, args.project, args.region, args.model, args.dims)
    # vertex — construct a standalone provider straight from a service-account
    # JSON (NOT via the runtime SecretStore/ProviderStore), mirroring how
    # main.py wires the VertexEmbedder.
    if not args.sa_json or not args.project:
        sys.exit("--embedder vertex requires --sa-json and --project")
    from providers.vertex.src.provider import Provider as VertexProvider
    from usecase.vertex_embedder import VertexEmbedder

    provider = VertexProvider(
        config={"project_id": args.project, "region": args.region},
        secrets={"serviceAccountJson": Path(args.sa_json).read_text("utf-8")},
    )
    return VertexEmbedder(provider=provider, model_id=args.model, dims=args.dims)


def _embed_markdown(path: Path, embedder: Any, force: bool) -> str:
    text = path.read_text("utf-8")
    meta, body = kb_loader._parse_frontmatter(text)
    if not isinstance(meta, dict) or not meta:
        return "skip-no-frontmatter"
    if meta.get("embedding_model") == embedder.model_id and not force:
        return "unchanged"
    if not body.strip():
        return "skip-empty"
    vec = embedder.embed(body.strip())
    meta = {k: v for k, v in meta.items() if k not in ("embedding", "embedding_model")}
    meta["embedding_model"] = embedder.model_id
    meta["embedding"] = _encode(vec)
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=10**9)
    path.write_text(f"---\n{fm}---\n{body.lstrip(chr(10))}", "utf-8")
    return "embedded"


def _embed_json(path: Path, embedder: Any, force: bool) -> str:
    import json

    obj = json.loads(path.read_text("utf-8"))
    if not isinstance(obj, dict):
        return "skip-not-object"
    if obj.get("embedding_model") == embedder.model_id and not force:
        return "unchanged"
    body = obj.get("content")
    body = body.strip() if isinstance(body, str) and body.strip() else json.dumps(
        {k: v for k, v in obj.items() if k not in ("embedding", "embedding_model")},
        ensure_ascii=False,
    )
    vec = embedder.embed(body)
    obj.pop("embedding", None)
    obj["embedding_model"] = embedder.model_id
    obj["embedding"] = _encode(vec)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return "embedded"


def main() -> int:
    ap = argparse.ArgumentParser(description="Bake pre-computed embeddings into a KB dir.")
    ap.add_argument("kb_dir", type=Path, help="KB directory (its entries/ are walked)")
    ap.add_argument("--embedder", choices=("stub", "vertex", "vertex-rest"), default="stub")
    ap.add_argument("--model", default="text-embedding-004", help="model id (vertex)")
    ap.add_argument("--dims", type=int, default=768)
    ap.add_argument("--access-token", help="bearer token (vertex-rest); default: gcloud")
    ap.add_argument("--sa-json", help="service-account JSON path (vertex)")
    ap.add_argument("--project", help="GCP project id (vertex)")
    ap.add_argument("--region", default="us-central1")
    ap.add_argument("--force", action="store_true", help="re-embed even if model matches")
    ap.add_argument("--dry-run", action="store_true", help="report, don't write")
    args = ap.parse_args()

    root = args.kb_dir
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")
    embedder = _build_embedder(args)

    counts: dict[str, int] = {}
    for f in kb_loader._iter_kb_files(root):
        suffix = f.suffix.lower()
        try:
            if args.dry_run:
                action = "would-embed"
            elif suffix in (".md", ".markdown"):
                action = _embed_markdown(f, embedder, args.force)
            elif suffix == ".json":
                action = _embed_json(f, embedder, args.force)
            else:
                action = "skip-unsupported"
        except Exception as exc:  # noqa: BLE001 — report + continue
            action = f"error:{type(exc).__name__}"
            print(f"  ! {f.name}: {exc}", file=sys.stderr)
        counts[action] = counts.get(action, 0) + 1

    print(f"kb_embed[{args.embedder}/{embedder.model_id}] {root}: " + " ".join(
        f"{k}={v}" for k, v in sorted(counts.items())
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
