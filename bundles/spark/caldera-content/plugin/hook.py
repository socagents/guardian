"""Minimal Caldera plugin shell for Phantom-shipped content.

v0.5.65 (issue #44) — wraps Phantom's curated abilities + adversaries
as a proper Caldera plugin so their content lives at
plugins/phantom/data/... (NOT volume-mounted; image-baked content
persists across container recreates).

Pre-v0.5.65 these YAMLs were copied to /usr/src/app/data/abilities/
which sits on the caldera_data named volume — content was shadowed
at runtime on every fresh install. The plugin-pattern fix lets
Caldera's data_svc.py find the YAMLs at startup as it scans
plugins/*/data/ alongside data/.

This plugin has no Python code beyond this shell, no GUI tab, no
executor, no obfuscator. Caldera's plugin loader registers the
plugin metadata + triggers data_svc to scan plugins/phantom/data/
on startup; that's all we need.
"""


name = "Phantom"
description = (
    "Phantom-shipped curated Caldera content: kill-chain abilities "
    "(v0.5.57 expanded 20-step ATT&CK chain), lab-safe lookalikes "
    "(v0.5.64), and adversary profiles wired against them. Image-"
    "baked at plugins/phantom/data/; survives volume-preserving "
    "container recreates because plugins/ is NOT volume-mounted."
)
# Empty address means no GUI tab. The plugin loader still registers
# the plugin + triggers data_svc to scan plugins/phantom/data/*.
address = ""


async def enable(services):
    """No-op enable hook.

    Caldera's app_svc calls this after loading the plugin. Pure-content
    plugins have nothing to do here — data_svc already scanned our
    abilities + adversaries at startup. No HTTP routes to register,
    no obfuscator to install, no executor to wire.
    """
    return None
