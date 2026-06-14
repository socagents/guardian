# mitre-attack-mobile — MITRE ATT&CK (Mobile (Android/iOS)) knowledge base

The complete MITRE ATT&CK **Mobile** matrix as a semantically-searchable reference
corpus, one doc per technique/sub-technique. Generated deterministically from the
official ATT&CK STIX bundle by [`../_tools/gen_mitre.py`](../_tools/gen_mitre.py)
(`--domain mobile`); embeddings pre-computed (boots with zero Vertex calls).

Sibling of `mitre-attack-enterprise`. Each doc carries the technique's
description, tactics, platforms, detection, and mitigations.
`framework_version` pins the source.

## Regenerate / re-bake
```bash
cd bundles/spark/kbs/_tools
python gen_mitre.py --domain mobile --out ../mitre-attack-mobile/entries
python kb_embed.py ../mitre-attack-mobile --embedder vertex-rest --project <gcp-project>
```

## Attribution
See [`NOTICE.txt`](NOTICE.txt). ATT&CK® is © The MITRE Corporation, reproduced
under the ATT&CK Terms of Use; Guardian is not endorsed or certified by MITRE.
