import argparse
import os
import json
import sys

import localpaths

from six import iteritems
from browserutils import virtualenv


here = os.path.dirname(__file__)
wpt_root = os.path.abspath(os.path.join(here, "..", ".."))


def load_commands():
    rv = {}
    with open(os.path.join(here, "paths"), "r") as f:
        paths = [item.strip().replace("/", os.path.sep) for item in f if item.strip()]
    for path in paths:
        abs_path = os.path.join(wpt_root, path, "commands.json")
        base_dir = os.path.dirname(abs_path)
        with open(abs_path, "r") as f:
            data = json.load(f)
            for command, props in iteritems(data):
                assert "path" in props
                assert "script" in props
                rv[command] = {
                    "path": os.path.join(base_dir, props["path"]),
                    "script": props["script"],
                    "parser": props.get("parser"),
                    "help": props.get("help"),
                    "virtualenv": props.get("virtualenv", True),
                    "install": props.get("install", []),
                    "requirements": [os.path.join(base_dir, item)
                                     for item in props.get("requirements", [])]
                }
    return rv


def parse_args(commands):
    parser = argparse.ArgumentParser()
    parser.add_argument("--venv", action="store", help="Path to an existing virtualenv to use")
    parser.add_argument("--debug", action="store_true", help="Run the debugger in case of an exception")
    subparsers = parser.add_subparsers(dest="command")
    for command, props in iteritems(commands):
        sub_parser = subparsers.add_parser(command, add_help=False)

    args, extra = parser.parse_known_args()

    return args, extra


def import_command(command, props):
    # This currently requires the path to be a module,
    # which probably isn't ideal but it means that relative
    # imports inside the script work
    rel_path = os.path.relpath(props["path"], wpt_root)

    parts = os.path.splitext(rel_path)[0].split(os.path.sep)

    mod_name = ".".join(parts)

    mod = __import__(mod_name)
    for part in parts[1:]:
        mod = getattr(mod, part)

    script = getattr(mod, props["script"])
    if props["parser"] is not None:
        parser = getattr(mod, props["parser"])
    else:
        parser = None

    return script, parser


def setup_virtualenv(path, props):
    if path is None:
        path = os.path.join(wpt_root, "_venv")
    venv = virtualenv.Virtualenv(path)
    venv.start()
    for name in props["install"]:
        venv.install(name)
    for path in props["requirements"]:
        venv.install_requirements(path)
    return venv


def main():
    commands = load_commands()

    main_args, command_args = parse_args(commands)

    if len(sys.argv) > 1 and sys.argv[1] in commands:
        command = main_args.command
        props = commands[command]
        script, parser = import_command(command, props)
        kwargs = vars(parser().parse_args(command_args))
    else:
        return

    if props["virtualenv"]:
        args = (setup_virtualenv(main_args.venv, props),)
    else:
        args = ()

    if script:
        try:
            rv = script(*args, **kwargs)
            if rv is not None:
                sys.exit(int(rv))
        except Exception:
            if main_args.debug:
                import pdb
                pdb.post_mortem()
            else:
                raise


if __name__ == "__main__":
    main()