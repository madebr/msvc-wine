#!/usr/bin/env python

import argparse
import itertools
import json
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parent
TOOLCHAINS = [p.stem for p in (ROOT / "envs").iterdir() if p.suffix == ".json"]

def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("root", default=pathlib.Path.cwd(), type=pathlib.Path, nargs="?", help="Location where to extract all toolchains")
    args = parser.parse_args()

    if not args.root.exists():
        args.root.mkdir(parents=True)
    elif not args.root.is_dir():
        parser.error(f"\"{args.root}\" is not a directory")

    toolchains_bad = set()

    for toolchain in TOOLCHAINS:
        ok = True
        toolchain_root = args.root / toolchain
        print(f"- Verifying {toolchain}")
        if toolchain_root.is_dir():
            print(f"   Resetting git")
            subprocess.check_call(["git", "reset", "--hard", "HEAD"], cwd=toolchain_root, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            print(f"   Fetching last version")
            subprocess.check_call(["git", "fetch", "origin"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            print(f"   Checking out last version")
            subprocess.check_call(["git", "checkout", "origin/master"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        else:
            repo_url = f"https://github.com/archaic-msvc/{toolchain}.git"
            print(f"   Cloning repo ({repo_url})")
            subprocess.check_call(["git", "clone", repo_url], cwd=toolchain_root.parent, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        with (ROOT / f"envs/{toolchain}.json").open("r") as f_json:
            toolchain_json = json.load(f_json)
        print("   Checking paths...")
        for path_reldir in itertools.chain(toolchain_json["include"], toolchain_json["lib"], toolchain_json["winepath"]):
            path_abs = toolchain_root / path_reldir
            if not path_abs.is_dir():
                ok = False
                print(f"*** ERROR: \"{path_reldir}\" does not exist ***")
        if not ok:
            toolchains_bad.add(toolchain)

    if toolchains_bad:
        print(f"Problems detected with followint toolchains: {' '.join(toolchains_bad)}")
    else:
        print("All toolchains ok!")




if __name__ == "__main__":
    raise SystemExit(main())
