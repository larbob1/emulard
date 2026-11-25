#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

if [[ $# -lt 2 ]]; then
    printf 'Usage: WINEPREFIX=/path/to/initialized-prefix %s /path/to/victory.exe /path/to/title.exe [Victory run options]\n' "$0" >&2
    exit 2
fi

: "${WINEPREFIX:?Set WINEPREFIX to a dedicated, initialized Wine prefix}"
runtime=$(realpath -e -- "$1")
title=$(realpath -e -- "$2")
shift 2
if [[ ! -f "$runtime" || ! -f "$title" ]]; then
    printf 'Both arguments must be executable files.\n' >&2
    exit 2
fi

package=$(dirname -- "$title")
prefix=$(realpath -e -- "$WINEPREFIX")
export WINEPREFIX="$prefix"
mapping="$prefix/dosdevices/g:"
if [[ ! -d "$prefix/dosdevices" ]]; then
    printf 'Initialize the Wine prefix before launching.\n' >&2
    exit 2
fi

# Root-relative paths use the process's current drive, including calls that
# go directly to Windows instead of through Victory's virtual drive shims.
if [[ ! -e "$mapping" && ! -L "$mapping" ]]; then
    ln -s -- "$package" "$mapping"
elif [[ ! -L "$mapping" || "$(realpath -e -- "$mapping")" != "$package" ]]; then
    printf 'Drive G: already has a different mapping in this Wine prefix.\n' >&2
    exit 2
fi

cd -- "$package"
exec "${WINE:-wine}" "$runtime" run --execute "G:\\$(basename -- "$title")" "$@"
