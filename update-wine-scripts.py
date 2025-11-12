#!/usr/bin/env python

import argparse
import json
import os
import pathlib
import platform
import re
import shutil
import stat
import textwrap


RE_MSVC_VERSION = re.compile(r"msvc([0-9]+)[^0-9]*([0-9]+)?\S*")

def msvc_sort_key(v: str) -> (int, int):
    m = RE_MSVC_VERSION.match(v)
    if not m:
        raise ValueError(f"{m} has unsupported version")
    return (int(m.group(1)), int(m.group(2) or 0))


ROOT = pathlib.Path(__file__).resolve().parent
TOOLCHAINS = [p.stem for p in (ROOT / "envs").iterdir() if p.suffix == ".json"]
TOOLCHAINS.sort(key=msvc_sort_key)

def copy_shell_script(src: pathlib.Path, dst: pathlib.Path):
    shutil.copy(src, dst)
    dst.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

def create_msvc_arch_name(host_arch: str, target_arch:str) -> str:
    if host_arch == target_arch:
        return host_arch
    return f"{host_arch}_{target_arch}"

def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--toolchain", choices=TOOLCHAINS, required=True, help="MSVC toolchain version")
    parser.add_argument("--real-mt", action="store_true", dest="real_mt", help="Use real MT.EXE (only for MSVC8+)")
    parser.add_argument("location", type=pathlib.Path, default=pathlib.Path.cwd(), nargs="?",help="Directory")
    args = parser.parse_args()

    if platform.system() in ("Windows", "Java"):
        parser.error(f"Unsupported platform ({platform.system()})")
        return 1

    with (ROOT / "envs" / f"{args.toolchain}.json").open("r") as f:
        toolchain_json = json.load(f)

    available_wrappers = list(p.stem.lower() for p in (ROOT / "wrappers/bin").iterdir() if p.is_file())
    available_wrappers.sort()

    archs = [(host_arch, target_arch) for host_arch in toolchain_json["compiler-paths"]["host"].keys() for target_arch in toolchain_json["compiler-paths"]["host"][host_arch]["target"]]

    set_available_wrappers = set(available_wrappers)
    msvc_bins = {}
    for host_arch, target_arch in archs:
        bin_relpaths = toolchain_json["compiler-paths"]["host"][host_arch]["target"][target_arch].get("path", [])
        compiler_paths = msvc_bins.setdefault(host_arch, {}).setdefault(target_arch, {})
        if host_arch == target_arch:
            bin_relpaths += toolchain_json["sdk-paths"]["target"][target_arch].get("path", [])
        for bin_relpath in bin_relpaths:
            bin_path = args.location / bin_relpath
            for bin in bin_path.iterdir():
                if bin.suffix.lower() != ".exe":
                    continue
                bin_stem = bin.stem.lower()
                if bin_stem in set_available_wrappers and bin_stem not in compiler_paths:
                    compiler_paths[bin_stem] = bin

    shutil.rmtree(args.location / "wine", ignore_errors=True)

    for host_arch, target_arch in archs:
        msvc_arch_name = create_msvc_arch_name(host_arch=host_arch, target_arch=target_arch)
        wine_bin_path = args.location / f"wine/{msvc_arch_name}"
        wine_bin_path.mkdir(parents=True)
        copy_shell_script(ROOT / f"wrappers/wine-msvc.sh", wine_bin_path / "wine-msvc.sh")
        for wrapper_stem, exe_path in msvc_bins[host_arch][target_arch].items():
            copy_shell_script(ROOT / f"wrappers/bin/{wrapper_stem}", wine_bin_path / wrapper_stem)
            os.symlink(wrapper_stem, wine_bin_path / f"{wrapper_stem}.exe")

        with (wine_bin_path / "msvcenv.sh").open("w", newline="\n") as f_env:
            wine_paths = toolchain_json["compiler-paths"]["host"][host_arch]["target"][target_arch].get("path", [])
            if host_arch == target_arch:
                wine_paths += toolchain_json["sdk-paths"]["target"][target_arch].get("path", [])

            def create_env_content(paths):
                return ";".join("${MSVC_ROOT}\\\\" + p.replace("/", "\\\\") for p in paths)

            env_winepath = create_env_content(wine_paths)
            env_include = create_env_content(toolchain_json["sdk-paths"]["target"][target_arch].get("include", []))
            env_lib = create_env_content(toolchain_json["sdk-paths"]["target"][target_arch]["lib"])
            f_env.write(textwrap.dedent(f"""
                #!/usr/bin/env bash
                #
                # Copyright (c) 2018 Martin Storsjo
                # Copyright (c) 2025 archaic-msvc developers
                #
                # Permission to use, copy, modify, and/or distribute this software for any
                # purpose with or without fee is hereby granted, provided that the above
                # copyright notice and this permission notice appear in all copies.
                #
                # THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
                # WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
                # MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
                # ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
                # WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
                # ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
                # OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
                
                set -e
                
                # This file is autogenerated. Changes will be lost.
                
                MSVC_ROOT="$(cd -- "$(dirname -- "$0")/../.." && printf '%s\\n' "$(pwd)")"
                MSVC_ROOT=${{MSVC_ROOT//\\//\\\\}}
                export INCLUDE="{env_include}"
                export LIB="{env_lib}"
                export LIBPATH="$LIB"
                export WINEPATH="{env_winepath}"
            """))
            f_env.write("\n")
            for wrapper_stem, exe_path in msvc_bins[host_arch][target_arch].items():
                relative_location = str(exe_path.relative_to(args.location)).replace("/", "\\\\")
                f_env.write(f"MSVC_{wrapper_stem.upper()}_BIN=\"${{MSVC_ROOT}}\\\\{relative_location}\"\n")


        if args.real_mt and "mt" in msvc_bins[host_arch][target_arch]:
            dst_mt = wine_bin_path / "mt"
            dst_mt.unlink()
            copy_shell_script(ROOT / "wrappers/misc/mt", dst_mt)

        with (args.location / f"activate_{msvc_arch_name}").open("w", newline="\n") as f_activate:
            f_activate.write(textwrap.dedent(f"""
                # This file must be used with "source bin/activate" *from bash*
                # You cannot run it directly

                # This file is autogenerated. Changes will be lost.
                
                # Activate {msvc_arch_name}

                if test "x$BASH_SOURCE" = x; then
                    echo "Unsupported shell" >2
                    exit 1
                fi

                export PATH="$(cd -- "$(dirname -- "$BASH_SOURCE")" && printf '%s\\n' "$(pwd)")/wine/{msvc_arch_name}:$PATH"

                echo "{args.toolchain} is now available"
            """))


if __name__ == "__main__":
    raise SystemExit(main())
