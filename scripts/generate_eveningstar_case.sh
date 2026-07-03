#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

export HOME="${FREECAD_HOME:-/tmp/freecad-home}"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_CACHE_HOME="$HOME/.cache"

cd "$repo_root"
FreeCADCmd -c "import runpy; runpy.run_path('scripts/generate_eveningstar_case.py', run_name='__main__')"
