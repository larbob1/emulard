# SPDX-License-Identifier: GPL-3.0-or-later
"""Install reviewed test-only postimage in disposable prepared checkout."""
import argparse
from pathlib import Path
from preview_hle_native_suite import preview, load_fixtures

def install(checkout):
    path = checkout / "crates/victory-hle/src/modules/xasync.rs"
    updated = preview(path.read_bytes(), load_fixtures())
    path.write_bytes(updated)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    install(parser.parse_args().checkout)
