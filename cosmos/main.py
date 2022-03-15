import logging
import os
import sys

logging.basicConfig(level="INFO")

version = "0.1.0"
lib = os.path.dirname(os.path.realpath(__file__))
lock_file = lib+".lock"
pause_file = lib+".pause"
data_dir = lib+"/data"
status_file = data_dir+"/status"

force=""
command=""
command_arg =""
no_fetch=""
local_inventory=""

inventory_git_url=""#check me
valid_name = r"^[a-z0-9_\-]+$"

def usage():
    logging.info("""\
cosmos - manage configuration for your hosts

Usage:
  cosmos [options] [command] [command-args]

Options:
  --help                        Show this help message
  --version                     Show version

Commands:
  status                        Report the status fo the last run [default]
  host <host> <action>          Perform actions specific to a given host

Host actions:
  host <host> [host...]                     Show attributes for the host(s)
""")

def version():
    logging.info(version)

def main(argv):
    try:
        ...
    except (KeyboardInterrupt, SystemExit) as e:
        logging.info("exiting due to interruption: %s", repr(e))
    except Exception as e:
        logging.exception("exiting abnormally with error %s", repr(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))