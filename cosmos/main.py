import shutil
import datetime
import pathlib
import re
import time
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
    def status(text):
        os.makedirs(os.path.dirname(status_file))
        with open(status_file, "w") as f:
            f.write(str(datetime.datetime.now()) + " STATUS " + text + "\n")

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

    @staticmethod
    def check_inventory():
        assert inventory_git_url, "no inventory_git_url configured in %s/config" % lib
        assert os.path.exists(inventory_dir), (
            "couldn't fin inventroy at %s" % inventory_dir
        )

    @staticmethod
    def execute_directive():
        _path = inventory_dir + "/directives"
        now = time.time()
        if os.path.isdir(_path):
            # find directives from within the last day which have not been executed
            inventory_directives = [
                f
                for f in os.listdir(_path)
                if os.stat(_path + "/" + f).st_mtime < now - 86400
            ]
            os.makedirs(data_dir + "/executed_directives")
            for directive in inventory_directives:
                mtime = os.stat(_path + "/" + directive).st_mtime
                with open(data_dir + "/executed_directives/" + directive) as f:
                    _payload = f.read()
                if mtime not in _payload:
                    with open(data_dir + "/executed_directives/" + directive) as f:
                        f.write("%d\n" % mtime)
                    with open(data_dir + "/directives/" + directive) as f:
                        _payload = f.read()
                    exec(_payload)

    @staticmethod
    def fetch_inventory():
        if local_inventory:
            logging.info("using local inventory %s", local_inventory)
        elif no_fetch:
            logging.info("not fetching inventory")
        else:
            Utilities.check_inventory()
            logging.info("fetching inventory")
            if os.path.exists(inventory_dir + "/.git"):
                completed_process = subprocess.run(
                    ["git", "-C", inventory_dir, "status", "--porcelain"],
                    stdout=subprocess.PIPE,
                )
                assert (
                    completed_process.returncode != 0
                ), "local inventory checkout is dirty; try --no-fetch or reset"
                subprocess.check_output(
                    ["git", "-C", inventory_dir, "reset", "--hard"],
                    stdout=subprocess.PIPE,
                )
                subprocess.check_output(
                    ["git", "-C", inventory_dir, "-fd"], stdout=subprocess.PIPE
                )
                completed_process = subprocess.run(
                    ["git", "-C", inventory_dir, "pull"], stdout=subprocess.PIPE
                )
                if not completed_process.returncode == 0:
                    subprocess.check_output(
                        ["git", "clone", inventory_git_url, inventory_dir],
                        stdout=subprocess.PIPE,
                    )

    @staticmethod
    def host_entry(host):
        with open(inventory_dir + "/hosts/" + host + "/variables") as f:
            _payload = f.read()
        variables = [v for v in _payload.splitlines() if "=" in v]
        with open(inventory_dir + "/hosts/" + host + "/roles") as f:
            _payload = f.read()
        roles = ["role=%s" % v for v in _payload.splitlines()]
        modules = ["module=%s" % m for m in Utilities.host_modules(host)]
        entries = ["host=%s" % host] + roles + modules + variables
        return entries  # checkme

    @staticmethod
    def host_remove_module(host, module):
        modules_file = inventory_dir + "/hosts/" + host + "/modules"
        with open(modules_file) as f:
            _payload = f.read()
        modules = _payload.splitlines()
        modules = [m for m in modules if m != module]
        with open(modules_file, "w") as f:
            f.write("\n".join(modules) + "\n")

    @staticmethod
    def host_add_module(host, module):
        assert module in os.listdir(inventory_dir + "/modules"), (
            "couldn't find module %s" % module
        )
        modules_file = inventory_dir + "/hosts/" + host + "/modules"
        os.makedirs(inventory_dir + "/hosts/" + host)
        Utilities.host_remove_module(host, module)
        with open(modules_file, "a") as f:
            f.write(module + "\n")

    @staticmethod
    def host_remove_role(host, role):
        roles_file = inventory_dir + "/hosts/" + host + "/roles"
        with open(roles_file) as f:
            _payload = f.read()
        roles = _payload.splitlines()
        roles = [m for m in roles if m != role]
        with open(roles_file, "w") as f:
            f.write("\n".join(roles) + "\n")

    @staticmethod
    def host_add_role(host, role):
        assert role in os.listdir(inventory_dir + "/roles"), (
            "couldn't find role %s" % role
        )
        roles_file = inventory_dir + "/hosts/" + host + "/modules"
        os.makedirs(inventory_dir + "/hosts/" + host)
        Utilities.host_remove_role(host, role)
        with open(roles_file, "a") as f:
            f.write(role + "\n")

    @staticmethod
    def check_roles():
        for role in os.listdir(inventory_dir + "/roles"):
            assert os.path.exists(inventory_dir + "/roles/" + role + "/modules"), (
                "no modules file for role `%s`" % role
            )
            with open(inventory_dir + "/roles/" + role + "/modules") as f:
                _payload = f.read()
            modules = _payload.splitlines()
            malformed_modules = [m for m in modules if not re.match(valid_name, m)]
            assert not malformed_modules, (
                "malformed role modules: %s" % malformed_modules
            )
            for module in modules:
                assert os.path.exists(
                    inventory_dir + "/modules/" + module
                ), "role %s module %s does not exist" % (role, module)

    @staticmethod
    def check_modules():
        for module in os.listdir(inventory_dir + "/modules"):
            assert os.path.exists(inventory_dir + "/modules/" + module + "/apply"), (
                "no apply script for module %s" % module
            )

    @staticmethod
    def check_hosts():
        for host in os.listdir(inventory_dir + "/hosts"):
            # checkme below is there always the modules folder?
            assert os.listdir(
                inventory_dir + "/hosts/" + host + "/modules"
            ) + os.listdir(inventory_dir + "/hosts/" + host + "/roles"), (
                "no roles for host %s" % host
            )


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

        if command == "version":
            logging.info(version())
        elif command == "apply":
            Utilities.fetch_inventory()
            Utilities.identify()
            # consult pause file
            assert (
                not os.path.exists(pause_file) or force
            ), "bailing for pause lock file; try `cosmos resume`"
            # set up our lock file
            assert (
                not os.path.exists(lock_file) or force
            ), "mailing for run lock file; try `cosmos recover`"
            pathlib.Path(lock_file).touch()
            # apply modules
            logging.info("running apply")
            for module in modules:
                EntryPoints.apply_module(module)
                EntryPoints.test_module(module)
            # drop obsolete modules
            for droppable_module in droppable_modules:
                EntryPoints.drop_module(droppable_module)
            os.unlink(lock_file)
            EntryPoints.status("OK")
            logging.info("done")

        elif command == "status":
            status_payload = ""
            # list out what we would do
            Utilities.fetch_inventory()
            Utilities.identify()

            if os.path.exists(status_file):
                with open(status_file) as f:
                    status_payload = f.read()
            logging.info(
                """\
using inventory %s

hostname: %s
roles: %s
modules: %s

%s

"""
                % (
                    inventory_dir,
                    HOSTNAME,
                    roles or "<none>",
                    modules or "<none>",
                    status_payload or "STATUS UNKNOWN",
                )
            )
            if os.path.exists(lock_file):
                logging.info("-- run lock is set; clear with `cosmos recover` --")
            if os.path.exists(pause_file):
                logging.info("-- pause lock is set; clear with `cosmos resume` --")
        elif command == "directive":
            Utilities.fetch_inventory()
            Utilities.identify()

        elif command == "list-hosts":
            filters = command_arg
            Utilities.fetch_inventory()
            entries = ""
            hosts = os.listdir(inventory_dir + "/hosts")
            for host in hosts:
                host_entry = Utilities.host_entry(host)
                entries += host + "\t" + host_entry + "\n"

            logging.debug("\n%s", entries)
            for filter in filters:
                entries = [e for e in entries if re.match(filter, e)]

            logging.info([e.split()[0] for e in entries.splitlines() if e])

        elif command == "list-modules":
            Utilities.fetch_inventory()
            logging.info(os.listdir(inventory_dir + "/modules"))

        elif command == "list-roles":
            Utilities.fetch_inventory()
            logging.info(os.listdir(inventory_dir + "/roles"))

        elif command == "check":
            Utilities.check_modules()
            Utilities.check_roles()
            Utilities.check_hosts()

        elif command == "inventory":
            subcommand = command_arg
            # subcommand_arg = argv[3]
            if subcommand == "diff":
                subprocess.check_output(["git", "-C", inventory_dir, "diff"])
            elif subcommand == "push":
                subprocess.check_output(["git", "-C", inventory_dir, "push"])
        elif command == "host":
            host = command_arg
            subcommand = argv[3]
            subcommand_arg = argv[4]
            if subcommand == "add":
                os.makedirs(inventory_dir + "/hosts/" + host)
                pathlib.Path(inventory_dir + "/hosts/" + host + "/.gitkeep").touch()
            elif subcommand == "remove":
                shutil.rmtree(inventory_dir + "/hosts/" + host)
            elif subcommand == "add-module":
                Utilities.host_add_module(host, subcommand_arg)
            elif subcommand == "remove-module":
                Utilities.host_remove_module(host, subcommand_arg)
            elif subcommand == "add-role":
                Utilities.host_add_role(host, subcommand_arg)
            elif subcommand == "remove-role":
                Utilities.host_remove_role(host, subcommand_arg)
            else:
                for host in argv[2:]:
                    entry = Utilities.host_entry(host)
                    logging.info(entry)
        elif command == "fetch":
            # get our repo updated
            Utilities.fetch_inventory()
        elif command == "recover":
            # get our repo updated
            os.unlink(lock_file)
        elif command == "resume":
            # get our repo updated
            os.unlink(pause_file)
        elif command == "pause":
            pathlib.Path(pause_file).touch()
        else:
            assert False, "unknown command %s" % command

    except (KeyboardInterrupt, SystemExit) as e:
        logging.info("exiting due to interruption: %s", repr(e))
    except Exception as e:
        logging.exception("exiting abnormally with error %s", repr(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
