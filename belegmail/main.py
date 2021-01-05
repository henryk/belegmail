#!/usr/bin/env python3
import argparse
import logging
import multiprocessing
import pprint

from .config import ConfigurationManager
from .mail import ImapReceiver

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True
logging.getLogger("chardet.charsetprober").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--mode",
        choices=["daemon", "run_once", "dump_config"],
        default="daemon",
        help="Execution mode",
    )
    parser.add_argument(
        "config_yaml",
        nargs="+",
        type=argparse.FileType("r"),
        help="Configuration file(s) in YAML format",
    )

    args = parser.parse_args()

    c = ConfigurationManager()
    for fp in args.config_yaml:
        c.load(fp)

    if args.mode == "daemon":
        subprocesses = []
        for configuration in c.configurations():
            i = ImapReceiver(configuration)
            subprocesses.append(
                multiprocessing.Process(
                    target=i.run, name="Worker-{0}".format(configuration.name)
                )
            )

        for p in subprocesses:
            p.start()

        for p in subprocesses:
            p.join()

    elif args.mode == "run_once":
        for configuration in c.configurations():
            i = ImapReceiver(configuration)

            i.run_once()

    else:
        pprint.pprint(c.configs)
