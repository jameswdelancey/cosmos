import random
import subprocess
import logging
import os
import socket
import sys

logging.basicConfig(level="INFO")

version = "0.1.0"
lib = os.path.dirname(os.path.realpath(__file__))
lock_file = lib + ".lock"
pause_file = lib + ".pause"
data_dir = lib + "/data"
status_file = data_dir + "/status"

force = ""
command = ""
command_arg = ""
no_fetch = ""
local_inventory = ""
caller_path = ""

inventory_git_url = ""  # check me
valid_name = r"^[a-z0-9_\-]+$"
HOSTNAME = socket.gethostname()


class Config:
    global inventory_git_url, cosmos_root, inventory_dir
    inventory_git_url = "https://assess-token@github.com/organization/cosmos-inventory"
    cosmos_root = "/var/lib/cosmos"
    inventory_dir = cosmos_root + "/inventory"


class Variables:
    @staticmethod
    def run():
        global caller_path
        # read global variables
        if os.path.exists(inventory_dir + "/variables"):
            with open(inventory_dir + "/variables") as f:
                payload = f.read()
            exec(payload)  # checkme: place holder wont work

        # read caller variables form the module
        caller_variables = os.path.dirname(caller_path) + "/variables"
        if os.path.exists(caller_variables):
            with open(caller_variables) as f:
                payload = f.read()
            exec(payload)  # checkme: place holder wont work

        # read host variables
        machine_variables = "inventory/hosts/" + socket.gethostname() + "/variables"
        if os.path.exists(machine_variables):
            with open(machine_variables) as f:
                payload = f.read()
            exec(payload)  # checkme: place holder wont work


class EntryPoints:
    @staticmethod
    def install():
        VERSION = "0.1.0"
        INSTALL_PATH = "/var/lib"
        AV_PATH = INSTALL_PATH + "/cosmos/cosmo"
        RELEASE_URL = (
            "https://gitlab.com/jameswdelancey/cosmos/-/archive/"
            + VERSION
            + "/cosmos-"
            + VERSION
            + ".tar"
        )
        INVENTORY_GIT_URL = sys.argv[1] if len(sys.argv > 1) else ""
        CONFIG_FILE = INSTALL_PATH + "/cosmos/config"
        try:
            subprocess.check_output(["/usr/bin/which", "git"], stdout=subprocess.PIPE)
        except Exception as e:
            logging.exception(
                "cannot find git with error %s. please install git and try again.",
                repr(e),
            )
        if not INVENTORY_GIT_URL:
            logging.warning(
                "installing with no inventory git url; set later in %s", CONFIG_FILE
            )
        if os.path.exists("/var/lib/cosmos"):
            logging.critical("found existing installation at %s; exiting", INSTALL_PATH)
            raise RuntimeError("exiting due to finding existing installation")
        logging.info("installing to %s", INSTALL_PATH)
        os.makedirs(INSTALL_PATH + "/cosmos")
        subprocess.check_output(
            "curl -s "
            + RELEASE_URL
            + " | tar --strip-components=1 -C "
            + INSTALL_PATH
            + "/cosmos -xz",
            shell=True,
        )
        subprocess.check_output(
            "ln -sf /var/lib/cosmos/cosmos /usr/bin/cosmos", shell=True
        )
        os.makedirs(INSTALL_PATH + "/cosmos/inventory")

        if INVENTORY_GIT_URL:
            with open(CONFIG_FILE, "a") as f:
                f.write("inventory_git_url='%s'\n" % INVENTORY_GIT_URL)

        logging.info("adding entry to /etc/crontab...")
        with open("/etc/crontab") as f:
            _payload = f.read()
        _payloadlines = [x for x in _payload.splitlines() if AV_PATH not in x]
        _payloadlines.append(
            "* * * * * root "
            + AV_PATH
            + " directive >> /var/log/cosmos-directive.log 2>&1"
        )
        _payloadlines.append(
            str(random.randint(0, 59))
            + " * * * * root "
            + AV_PATH
            + " active >> /var/log/cosmos-apply.log 2>&1"
        )
        with open("/etc/crontab", "w") as f:
            f.write("\n".join(_payloadlines))
        logging.info("done")

    @staticmethod
    def usage():
        logging.info(
            """
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
"""
        )

    @staticmethod
    def version():
        logging.info(version)

    @staticmethod
    def apply_module(module):
        logging.info("applying module %s", module)
        try:
            with open(inventory_dir + "/modules/" + module + "/apply") as f:
                _payload = f.read()
            exec(_payload)
        except Exception as e:
            logging.exception("error in apply_module with error %s", repr(e))
        os.makedirs(data_dir + "/applied_modules")
        with open(data_dir + "/applied_modules/" + module) as f:
            f.write("OK\n")

    @staticmethod
    def test_module(module):
        if not os.path.exists(inventory_dir + "/modules/" + module + "/test"):
            return
        logging.info("testing module %s", module)
        try:
            with open(inventory_dir + "/modules/" + module + "/test") as f:
                _payload = f.read()
            exec(_payload)
        except Exception as e:
            logging.exception("error in test_module with error %s", repr(e))

    @staticmethod
    def drop_module(module):
        logging.info("dropping module %s", module)
        try:
            with open(inventory_dir + "/modules/" + module + "/drop") as f:
                _payload = f.read()
            exec(_payload)
        except Exception as e:
            logging.exception("error in drop_module with error %s", repr(e))
        os.unlink(data_dir + "/applied_modules/" + module)


class Utilities:
    @staticmethod
    def host_roles(host=HOSTNAME):
        # identify our roles
        with open(inventory_dir + "/hosts/" + host + "/roles") as f:
            _payload = f.read()
        roles = _payload.splitlines()
        return roles

    @staticmethod
    def host_modules(host=HOSTNAME):
        roles = Utilities.host_roles(host)
        modules = []
        with open(inventory_dir + "/hosts/" + host + "/modules") as f:
            _payload = f.read()
        modules.extend(_payload.splitlines())
        for role in roles:
            with open(inventory_dir + "/roles/" + role + "/modules") as f:
                _payload = f.read()
            modules.extend(_payload.splitlines())
        return modules

    @staticmethod
    def identify():
        global applied_modules, droppable_modules, roles, modules
        assert os.path.isdir(inventory_dir + "/hosts/" + HOSTNAME), (
            "couldn't find host %s in inventory" % HOSTNAME
        )
        # identify our roles and modules
        roles = Utilities.host_roles()
        modules = Utilities.host_modules()

        # find applied modules no longer in the inventory
        os.makedirs(data_dir + "/applied_modules")
        applied_modules = [
            f
            for f in os.listdir(data_dir + "/applied_modules")
            if os.path.isfile(os.path.join(data_dir + "/applied_modules/" + f))
        ]
        droppable_modules = [m for m in applied_modules if m not in modules]



def log_level(arg):
    assert arg.upper() in [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ], "logging level invalid"
    logging.basicConfig(level=arg.upper())


def log_quiet():
    log_level("CRITICAL")


def main(argv):
    global force, no_fetch, local_inventory
    args = argv.copy()
    try:
        while len(args) > 0:
            arg = args[0]
            if "--force" == arg:
                force = 1
            elif "--no-fetch" == arg:
                no_fetch = 1
            elif arg in ["--quiet", "-q"]:
                log_quiet()
            elif "--help" == arg:
                EntryPoints.usage()
                return
            elif "--version" == arg:
                EntryPoints.version()
                return
            elif "--log-level" == arg:
                args.pop(0)
                arg = args[0]
                log_level(arg)
            elif "--inventory" == arg:
                args.pop(0)
                arg = args[0]
                local_inventory = arg
            else:
                if not command:
                    command = arg
                elif not command_arg:
                    command_arg = arg
            args.pop(0)
        os.chdir(cosmos_root)
        if local_inventory:
            inventory_dir = local_inventory
        if not command:
            command = "status"

    except (KeyboardInterrupt, SystemExit) as e:
        logging.info("exiting due to interruption: %s", repr(e))
    except Exception as e:
        logging.exception("exiting abnormally with error %s", repr(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
