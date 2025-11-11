#!/usr/bin/env python

import argparse
import itertools
import pathlib

def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("path", default=pathlib.Path.cwd(), type=pathlib.Path, help="Working directory")
    args = parser.parse_args()

    for path, dirnames, filenames in args.path.walk():
        for dirname in itertools.chain(dirnames, filenames):
            if dirname.upper() == dirname:
                src = path / dirname
                dst = path / dirname.lower()
                print(f"\"{src}\" -> \"{dst}\"")
                src.rename(dst)


if __name__ == "__main__":
    raise SystemExit(main())
