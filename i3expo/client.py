#!/usr/bin/env python3

import argparse
import os
import signal

parser = argparse.ArgumentParser(description="Interact with the i3expo daemon")
parser.add_argument("-u", "--update-config",
                    help="Update config from file", action="store_true")
parser.add_argument("-s", "--show", help="Show expo UI", action="store_true")
args = parser.parse_args()


def get_pid():
    uid = os.getuid()
    with open(f"/var/run/user/{uid}/i3expo.pid", "r") as f:
        pid = f.readline()
        return int(pid)


def main():
    try:
        pid = get_pid()
        if args.show:
            print("Requesting UI")
            os.kill(pid, signal.SIGUSR1)
        elif args.update_config:
            print("Requesting config update")
            os.kill(pid, signal.SIGHUP)
    except:
        print("Failed to send signal")


if __name__ == "__main__":
    main()
