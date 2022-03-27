import datetime
import io
import logging
import os
import pathlib
import random
import re
import shutil
import socket
import subprocess
import sys
import time


version = "0.1.0"

force = ""
command = ""
command_arg = ""
no_fetch = ""
local_inventory = ""
caller_path = ""

valid_name = r"^[a-z0-9_\-]+$"
HOSTNAME = socket.gethostname()


class Config:
    inventory_git_url = (
        "https://jameswdelancey:"
        + os.environ.get("ACCESS_TOKEN")
        + "@github.com/jameswdelancey/cosmos_inventory_example"
    )
    cosmos_root = "/var/lib/cosmos" if os.name != "nt" else "c:/cosmos"
    inventory_dir = cosmos_root + "/inventory"
    INSTALL_PATH = "/var/lib" if os.name != "nt" else "c:/"
    PYTHON_BIN = (
        "/usr/bin/python3"
        if os.name != "nt"
        else "C:\\Users\\jd\\AppData\\Local\\Programs\\Python\\Python39\\python.exe"
    )


os.makedirs(Config.cosmos_root + "/log", exist_ok=True)
if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] != "reset"):
    logging.basicConfig(
        level="DEBUG", filename=Config.cosmos_root + "/log/%d.log" % time.time()
    )
# set up logging to console
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
# set a format which is simpler for console use
formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger("").addHandler(console)

threads = []
thread_stop = []
tmsrp = os.environ.get("TIMESERIES_SERVER_REPO_PATH")
if tmsrp and os.path.exists(tmsrp+"/timeseries_server/timeseries_client.py"):
    with open(tmsrp+"/timeseries_server/timeseries_client.py") as f:
        exec(f.read())
    log_queue = queue.Queue()
    root_logger = logging.getLogger()
    root_logger.addHandler(logging.handlers.QueueHandler(log_queue))
    log_to_timeseries_server(threads, thread_stop, log_queue)

# lib = os.path.dirname(os.path.realpath(__file__))
lib = Config.cosmos_root
lock_file = lib + "/.lock"
pause_file = lib + "/.pause"
data_dir = lib + "/data"
status_file = data_dir + "/status"


def set_variables(module):
    # read global variables.py
    if os.path.exists(Config.inventory_dir + "/variables.py"):
        logging.debug("reading global vars")
        with open(Config.inventory_dir + "/variables.py") as f:
            payload = f.read()
        exec(payload)

    # read module variables.py
    if os.path.exists(Config.inventory_dir + "/modules/" + module + "/variables.py"):
        logging.debug("reading modules vars")
        with open(Config.inventory_dir + "/modules/" + module + "/variables.py") as f:
            payload = f.read()
        exec(payload)

    # read host variables.py
    machine_variables = (
        Config.inventory_dir + "/hosts/" + socket.gethostname() + "/variables.py"
    )
    if os.path.exists(machine_variables):
        logging.debug("reading host vars")
        with open(machine_variables) as f:
            payload = f.read()
        exec(payload)


class EntryPoints:
    @staticmethod
    def uninstall():
        AV_PATH = Config.INSTALL_PATH + "/cosmos/cosmos.py"
        if os.name != "nt":
            logging.info("adding entry to /etc/crontab...")
            with open("/etc/crontab") as f:
                _payload = f.read()
            _payloadlines = [x for x in _payload.splitlines() if AV_PATH not in x]
            with open("/etc/crontab", "w") as f:
                f.write("\n".join(_payloadlines))
        else:
            schtasks_output = ""
            try:
                schtasks_output = subprocess.check_output(
                    ["schtasks.exe", "/delete", "/tn", "cosmos_directive", "/F"]
                )
                logging.debug("schtasks_delete_directive: %s", schtasks_output.decode())
            except Exception as e:
                logging.info(
                    "schtask cosmos_directive not removed with error %s", repr(e)
                )
            try:
                schtasks_output = subprocess.check_output(
                    ["schtasks.exe", "/delete", "/tn", "cosmos_apply", "/F"]
                )
                logging.debug("schtasks_delete_apply: %s", schtasks_output.decode())
            except Exception as e:
                logging.info("schtask cosmos_apply not removed with error %s", repr(e))
            shutil.rmtree(Config.inventory_dir) if os.name != "nt" else subprocess.run(
                [
                    "cmd",
                    "/c",
                    "rmdir",
                    "/S",
                    "/Q",
                    Config.cosmos_root.replace("/", "\\"),
                ]
            )
            logging.info("done")

    @staticmethod
    def install():
        VERSION = "0.1.0"
        AV_PATH = Config.INSTALL_PATH + "/cosmos/cosmos.py"
        RELEASE_URL = "https://raw.githubusercontent.com/jameswdelancey/cosmos/main/cosmos/main.py"
        INVENTORY_GIT_URL = sys.argv[1] if len(sys.argv) > 1 else ""
        CONFIG_FILE = Config.INSTALL_PATH + "/cosmos/config"
        try:
            subprocess.check_output(["git", "--version"])
        except Exception as e:
            logging.exception(
                "cannot find git with error %s. please install git and try again.",
                repr(e),
            )
            raise
        if not INVENTORY_GIT_URL:
            logging.warning(
                "installing with no inventory git url; set later in %s", CONFIG_FILE
            )
        if os.path.exists(Config.inventory_dir):
            logging.critical(
                "found existing installation at %s; exiting", Config.INSTALL_PATH
            )
            raise RuntimeError("exiting due to finding existing installation")
        logging.info("installing to %s", Config.INSTALL_PATH)
        logging.debug("creating directory: %s", Config.INSTALL_PATH + "/cosmos")
        try:
            os.makedirs(Config.INSTALL_PATH + "/cosmos", exist_ok=True)
        except FileExistsError:
            pass
        curl_output = subprocess.check_output(["curl", "-s", RELEASE_URL])
        logging.debug("curl_output: %s", curl_output.decode())
        with open(Config.INSTALL_PATH + "/cosmos/cosmos.py", "wb") as f:
            f.write(curl_output)
        # subprocess.check_output(
        #     "ln -sf /var/lib/cosmos/cosmos /usr/bin/cosmos", shell=True
        # )
        os.makedirs(Config.INSTALL_PATH + "/cosmos/inventory", exist_ok=True)

        if os.name != "nt":
            logging.info("adding entry to /etc/crontab...")
            with open("/etc/crontab") as f:
                _payload = f.read()
            _payloadlines = [x for x in _payload.splitlines() if AV_PATH not in x]
            _payloadlines.append(
                "0 * * * * root "
                + Config.PYTHON_BIN
                + " "
                + AV_PATH
                + " directive >> /var/log/cosmos-directive.log 2>&1"
            )
            _payloadlines.append(
                str(random.randint(0, 59))
                + " * * * * root "
                + Config.PYTHON_BIN
                + " "
                + AV_PATH
                + " apply >> /var/log/cosmos-apply.log 2>&1"
            )
            with open("/etc/crontab", "w") as f:
                f.write("\n".join(_payloadlines))
        else:
            schtasks_output = ""
            try:
                schtasks_output = subprocess.check_output(
                    ["schtasks.exe", "/delete", "/tn", "cosmos_directive", "/F"]
                )
                logging.debug("schtasks_delete_directive: %s", schtasks_output.decode())
            except Exception as e:
                logging.info(
                    "schtask cosmos_directive not removed with error %s", repr(e)
                )
            try:
                schtasks_output = subprocess.check_output(
                    ["schtasks.exe", "/delete", "/tn", "cosmos_apply", "/F"]
                )
                logging.debug("schtasks_delete_apply: %s", schtasks_output.decode())
            except Exception as e:
                logging.info("schtask cosmos_apply not removed with error %s", repr(e))
            try:
                schtasks_output = subprocess.check_output(
                    [
                        "schtasks.exe",
                        "/create",
                        "/tn",
                        "cosmos_directive",
                        "/sc",
                        "hourly",
                        "/st",
                        "00:00",
                        "/tr",
                        Config.PYTHON_BIN + " c:\\cosmos\\cosmos.py directive",
                    ]
                )
                logging.debug("schtasks_create_directive: %s", schtasks_output.decode())
            except Exception as e:
                logging.info(
                    "schtask cosmos_directive not created with error %s", repr(e)
                )
            try:
                schtasks_output = subprocess.check_output(
                    [
                        "schtasks.exe",
                        "/create",
                        "/tn",
                        "cosmos_apply",
                        "/sc",
                        "hourly",
                        "/st",
                        "00:%02d" % random.randint(0, 59),
                        "/tr",
                        Config.PYTHON_BIN + " c:\\cosmos\\cosmos.py apply",
                    ]
                )
                logging.debug("schtasks_create_apply: %s", schtasks_output.decode())
            except Exception as e:
                logging.info("schtask cosmos_apply not created with error %s", repr(e))
            Utilities.fetch_inventory()
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
  --log-level <level>           Set the log level (debug, info, warning, critical) [default: info]
  --inventory <path>            Use a local inventory at the specified path
  --no-fetch                    Don't fetch the inventory before running the command
  --force                       Run even if a pause or runlock is set
  --quiet|-q                    Suppress log messages

Commands:
  status                        Report the status fo the last run [default]
  host <host> <action>          Perform actions specific to a given host
  apply                         Apply roles and their associated modules on this host
  fetch                         Update local database by fetching from upstream
  directive                     Run any outstanding directives from the inventory
  recover                       Reset run lock file after a failure
  pause                         Set the pause lock to avoid periodic runs while debugging
  resume                        Resume periodic runs after a pause
  list-hosts [filter]           List hosts with an optional filter (e.g. role=[^=]*web)
  list-modules                  List all avaliable modules
  list-roles                    List all avaliable roles
  uninstall                     Uninstall cron/scheduled tasks and delete cosmos install directory
  check                         Check configuration a bit. Useful before a commit.
  reset                         Remove the cosmos program, reclone inventory repo, and reinstall cron/schedtasks

Inventory repository actions:
  inventory diff                            Check to see what's changed in the local repo
  inventory push                            Update inventory repo with current commit
  inventory commit                          Create a commit in the local inventory repo
  inventory skeleton                        Bootstrap the local inventory repo; useful for new installs

Host actions:
  host <host> [host...]                     Show attributes for the host(s)
  host <host> add                           Add the host to the inventory
  host <host> remove                        Remove the host from the inventory
  host <host> add-module <module>           Add the module to the host in the inventory
  host <host> remove-module <module>        Remove the module from the host in the inventory
  host <host> add-role <role>               Add the role to the host in the inventory
  host <host> remove-role <role>            Remove the role from the host in the inventory

Role actions:
  role <role> add                           Add a skeleton for a new role by name
  role <role> remove                        Remove a role by name

Directive actions:
  directive <directive> add                 Add a directive skeleton by name
  directive <directive> remove              Remove a directive by name
  directive                                 Execute all unexecuted directives less than 24h old

Module actions:
  module <module> add                       Add a skeleton for a new module by name
  module <module> remove                    Remove a module by name

"""
        )

    @staticmethod
    def version():
        logging.info(version)

    @staticmethod
    def status(text):
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        with open(status_file, "w") as f:
            f.write(str(datetime.datetime.now()) + " STATUS " + text + "\n")

    @staticmethod
    def apply_module(module):
        logging.info("applying module %s", module)
        os.makedirs(data_dir + "/applied_modules", exist_ok=True)
        try:
            with open(Config.inventory_dir + "/modules/" + module + "/apply.py") as f:
                _payload = f.read()
            exec(_payload)
            with open(data_dir + "/applied_modules/" + module, "a") as f:
                f.write("OK\n")
        except Exception as e:
            logging.exception("error in apply_module with error %s", repr(e))
            logging.critical("exiting with lock enabled")
            with open(data_dir + "/applied_modules/" + module, "a") as f:
                f.write("FAILED APPLY\n")
            raise

    @staticmethod
    def test_module(module):
        if not os.path.exists(Config.inventory_dir + "/modules/" + module + "/test.py"):
            return
        logging.info("testing module %s", module)
        try:
            with open(Config.inventory_dir + "/modules/" + module + "/test.py") as f:
                _payload = f.read()
            exec(_payload)
        except Exception as e:
            logging.exception("error in test_module with error %s", repr(e))
            logging.critical("exiting with lock enabled")
            with open(data_dir + "/applied_modules/" + module, "a") as f:
                f.write("FAILED TEST\n")
            raise

    @staticmethod
    def drop_module(module):
        logging.info("dropping module %s", module)
        try:
            with open(Config.inventory_dir + "/modules/" + module + "/drop.py") as f:
                _payload = f.read()
            exec(_payload)
        except Exception as e:
            logging.exception("error in drop_module with error %s", repr(e))
        os.unlink(data_dir + "/applied_modules/" + module)


class Utilities:
    @staticmethod
    def host_roles(host=HOSTNAME):
        # identify our roles
        with open(Config.inventory_dir + "/hosts/" + host + "/roles") as f:
            _payload = f.read()
        roles = [x for x in _payload.splitlines() if x]
        return roles

    @staticmethod
    def host_modules(host=HOSTNAME):
        roles = Utilities.host_roles(host)
        modules = []
        with open(Config.inventory_dir + "/hosts/" + host + "/modules") as f:
            _payload = f.read()
        modules.extend([x for x in _payload.splitlines() if x])
        for role in roles:
            with open(Config.inventory_dir + "/roles/" + role + "/modules") as f:
                _payload = f.read()
            modules.extend([x for x in _payload.splitlines() if x])
        return modules

    @staticmethod
    def identify():
        global applied_modules, droppable_modules, roles, modules
        assert os.path.isdir(Config.inventory_dir + "/hosts/" + HOSTNAME), (
            "couldn't find host %s in inventory" % HOSTNAME
        )
        # identify our roles and modules
        roles = Utilities.host_roles()
        modules = Utilities.host_modules()

        # find applied modules no longer in the inventory
        os.makedirs(data_dir + "/applied_modules", exist_ok=True)
        applied_modules = [
            f
            for f in os.listdir(data_dir + "/applied_modules")
            if os.path.isfile(os.path.join(data_dir + "/applied_modules/" + f))
        ]
        droppable_modules = [m for m in applied_modules if m not in modules]
        logging.debug("droppable modules are: %s", droppable_modules)

    @staticmethod
    def check_inventory():
        assert Config.inventory_git_url, (
            "no inventory_git_url configured in %s/config" % lib
        )
        assert os.path.exists(Config.inventory_dir), (
            "couldn't fin inventroy at %s" % Config.inventory_dir
        )

    @staticmethod
    def execute_directives():
        _path = Config.inventory_dir + "/directives"
        now = time.time()
        if os.path.isdir(_path):
            # find directives from within the last day which have not been executed
            inventory_directives = [
                f
                for f in os.listdir(_path)
                if os.stat(_path + "/" + f).st_mtime > now - 86400
            ]
            os.makedirs(data_dir + "/executed_directives", exist_ok=True)
            for directive in inventory_directives:
                mtime = os.stat(_path + "/" + directive).st_mtime
                _payload = ""
                if os.path.exists(data_dir + "/executed_directives/" + directive):
                    with open(data_dir + "/executed_directives/" + directive) as f:
                        _payload = f.read()
                if "%d" % mtime not in _payload:
                    with open(data_dir + "/executed_directives/" + directive, "a") as f:
                        f.write("%d\n" % mtime)
                    directive_file = Config.inventory_dir + "/directives/" + directive
                    try:
                        with open(directive_file) as f:
                            _payload = f.read()
                        exec(_payload)
                    except Exception as e:
                        logging.exception(
                            "error running directive %s with error %s",
                            directive,
                            repr(e),
                        )
                        logging.critical(
                            "lock not set, will run again at scheduled time even though failed"
                        )

    @staticmethod
    def fetch_inventory():
        if local_inventory:
            logging.info("using local inventory %s", local_inventory)
        elif no_fetch:
            logging.info("not fetching inventory")
        else:
            Utilities.check_inventory()
            logging.info("fetching inventory")
            if os.path.exists(Config.inventory_dir + "/.git"):
                try:
                    git_output = subprocess.check_output(
                        ["git", "-C", Config.inventory_dir, "status", "--porcelain"]
                    )
                    logging.debug("git porcelain output: %s", git_output.decode())
                except Exception as e:
                    logging.exception(
                        "error in fetch_inventory with error: %s. local inventory checkout is dirty; try --no-fetch or reset",
                        repr(e),
                    )
                try:
                    git_output = subprocess.check_output(
                        ["git", "-C", Config.inventory_dir, "reset", "--hard"],
                    )
                    logging.debug("git porcelain output: %s", git_output.decode())
                    git_output = subprocess.check_output(
                        ["git", "-C", Config.inventory_dir, "clean", "-fd"]
                    )
                    logging.debug("git clean output: %s", git_output.decode())
                    git_output = subprocess.check_output(
                        ["git", "-C", Config.inventory_dir, "pull"]
                    )
                    logging.debug("git pull output: %s", git_output.decode())
                except Exception as e:
                    shutil.rmtree(
                        Config.inventory_dir
                    ) if os.name != "nt" else subprocess.run(
                        [
                            "cmd",
                            "/c",
                            "rmdir",
                            "/S",
                            "/Q",
                            Config.inventory_dir.replace("/", "\\"),
                        ]
                    )
                    git_output = subprocess.check_output(
                        [
                            "git",
                            "clone",
                            Config.inventory_git_url,
                            Config.inventory_dir,
                        ]
                    )
                    logging.debug("git clone output: %s", git_output.decode())

            else:
                if os.path.exists(Config.inventory_dir):
                    shutil.rmtree(Config.inventory_dir)
                subprocess.check_output(
                    ["git", "clone", Config.inventory_git_url, Config.inventory_dir]
                )

    @staticmethod
    def host_entry(host):
        with open(Config.inventory_dir + "/hosts/" + host + "/variables.py") as f:
            _payload = f.read()
        variables = [v for v in _payload.splitlines() if "=" in v]
        with open(Config.inventory_dir + "/hosts/" + host + "/roles") as f:
            _payload = f.read()
        roles = ["role=%s" % v for v in _payload.splitlines()]
        modules = ["module=%s" % m for m in Utilities.host_modules(host)]
        entries = ["host=%s" % host] + roles + modules + variables
        return entries  # checkme

    @staticmethod
    def host_remove_module(host, module):
        modules_file = Config.inventory_dir + "/hosts/" + host + "/modules"
        with open(modules_file) as f:
            _payload = f.read()
        modules = _payload.splitlines()
        modules = [m for m in modules if m != module]
        with open(modules_file, "w") as f:
            f.write("\n".join(modules) + "\n")

    @staticmethod
    def host_add_module(host, module):
        assert module in os.listdir(Config.inventory_dir + "/modules"), (
            "couldn't find module %s" % module
        )
        modules_file = Config.inventory_dir + "/hosts/" + host + "/modules"
        os.makedirs(Config.inventory_dir + "/hosts/" + host, exist_ok=True)
        Utilities.host_remove_module(host, module)
        with open(modules_file, "a") as f:
            f.write(module + "\n")

    @staticmethod
    def host_remove_role(host, role):
        roles_file = Config.inventory_dir + "/hosts/" + host + "/roles"
        with open(roles_file) as f:
            _payload = f.read()
        roles = _payload.splitlines()
        roles = [m for m in roles if m != role]
        with open(roles_file, "w") as f:
            f.write("\n".join(roles) + "\n")

    @staticmethod
    def host_add_role(host, role):
        assert role in os.listdir(Config.inventory_dir + "/roles"), (
            "couldn't find role %s" % role
        )
        roles_file = Config.inventory_dir + "/hosts/" + host + "/roles"
        os.makedirs(Config.inventory_dir + "/hosts/" + host, exist_ok=True)
        Utilities.host_remove_role(host, role)
        with open(roles_file, "a") as f:
            f.write(role + "\n")

    @staticmethod
    def check_roles():
        for role in [
            x
            for x in os.listdir(Config.inventory_dir + "/roles")
            if not x.startswith(".")
        ]:
            assert os.path.exists(
                Config.inventory_dir + "/roles/" + role + "/modules"
            ), ("no modules file for role `%s`" % role)
            with open(Config.inventory_dir + "/roles/" + role + "/modules") as f:
                _payload = f.read()
            modules = _payload.splitlines()
            malformed_modules = [m for m in modules if not re.match(valid_name, m)]
            assert not malformed_modules, (
                "malformed role modules: %s" % malformed_modules
            )
            for module in modules:
                assert os.path.exists(
                    Config.inventory_dir + "/modules/" + module
                ), "role %s module %s does not exist" % (role, module)

    @staticmethod
    def check_modules():
        for module in [
            x
            for x in os.listdir(Config.inventory_dir + "/modules")
            if not x.startswith(".")
        ]:
            assert os.path.exists(
                Config.inventory_dir + "/modules/" + module + "/apply.py"
            ), ("no apply script for module %s" % module)

    @staticmethod
    def check_hosts():
        for host in [
            x
            for x in os.listdir(Config.inventory_dir + "/hosts")
            if not x.startswith(".")
        ]:
            # checkme below is there always the modules folder?
            assert os.path.exists(
                Config.inventory_dir + "/hosts/" + host + "/modules"
            ) and os.path.exists(Config.inventory_dir + "/hosts/" + host + "/roles"), (
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
    args = argv[1:]
    command = args[0] if len(args) > 0 else ""
    command_arg = args[1] if len(args) > 1 else ""
    logging.debug("args: %s", args)
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
        if not os.path.exists(Config.inventory_dir):
            logging.error(
                "cosmos root does not exist at %s; running the install function",
                Config.cosmos_root,
            )
            EntryPoints.install()
            logging.info("installer finished")
            return
        os.chdir(Config.cosmos_root)
        if local_inventory:
            Config.inventory_dir = local_inventory
        if not command:
            command = "status"
        logging.debug("command: %s", command)
        if command == "uninstall":
            EntryPoints.uninstall()
        elif command == "apply":
            # update cosmos.py before setting lock file
            if datetime.datetime.now().hour == 1:
                RELEASE_URL = "https://raw.githubusercontent.com/jameswdelancey/cosmos/main/cosmos/main.py"
                curl_output = subprocess.check_output(["curl", "-s", RELEASE_URL])
                logging.debug("curl_output: %s", curl_output.decode())
                with open(Config.INSTALL_PATH + "/cosmos/cosmos.py", "wb") as f:
                    f.write(curl_output)
            # prevent a scheduler from running both apply and directive at the same
            # time and causing git to crash.
            time.sleep(10)
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
                set_variables(module)
                EntryPoints.apply_module(module)
                EntryPoints.test_module(module)
            # drop obsolete modules
            for droppable_module in droppable_modules:
                set_variables(droppable_module)
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
                    Config.inventory_dir,
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

        elif command == "list-hosts":
            filters = command_arg
            Utilities.fetch_inventory()
            entries = ""
            hosts = [
                x
                for x in os.listdir(Config.inventory_dir + "/hosts")
                if not x.startswith(".")
            ]
            for host in hosts:
                host_entry = Utilities.host_entry(host)
                entries += host + "\t" + str(host_entry) + "\n"

            logging.debug("\n%s", entries)
            for filter in filters:
                entries = [e for e in entries if re.match(filter, e)]

            logging.info([e.split()[0] for e in entries])

        elif command == "list-modules":
            Utilities.fetch_inventory()
            logging.info(
                [
                    x
                    for x in os.listdir(Config.inventory_dir + "/modules")
                    if not x.startswith(".")
                ]
            )

        elif command == "list-roles":
            Utilities.fetch_inventory()
            logging.info(
                [
                    x
                    for x in os.listdir(Config.inventory_dir + "/roles")
                    if not x.startswith(".")
                ]
            )

        elif command == "check":
            Utilities.check_modules()
            Utilities.check_roles()
            Utilities.check_hosts()

        elif command == "inventory":
            subcommand = command_arg
            # subcommand_arg = argv[3]
            if subcommand == "diff":
                git_output = subprocess.check_output(
                    ["git", "-C", Config.inventory_dir, "diff"]
                )
                logging.info(git_output.decode())
            elif subcommand == "push":
                git_output = subprocess.check_output(
                    ["git", "-C", Config.inventory_dir, "push"]
                )
                logging.info(git_output.decode())
            elif subcommand == "commit":
                git_output = subprocess.check_output(
                    ["git", "-C", Config.inventory_dir, "add", "."]
                )
                git_output = subprocess.check_output(
                    ["git", "-C", Config.inventory_dir, "commit", "-m", "auto commit"]
                )
                logging.info(git_output.decode())
            elif subcommand == "skeleton":
                os.makedirs(Config.inventory_dir + "/roles", exist_ok=True)
                os.makedirs(Config.inventory_dir + "/modules", exist_ok=True)
                os.makedirs(Config.inventory_dir + "/hosts", exist_ok=True)
                os.makedirs(Config.inventory_dir + "/directives", exist_ok=True)
                pathlib.Path(Config.inventory_dir + "/variables.py").touch()
        elif command == "role":
            role = command_arg
            subcommand = argv[3] if len(argv) > 3 else ""
            subcommand_arg = argv[4] if len(argv) > 4 else ""
            if subcommand == "add":
                os.makedirs(Config.inventory_dir + "/roles/" + role, exist_ok=True)
                pathlib.Path(
                    Config.inventory_dir + "/roles/" + role + "/modules"
                ).touch()
            elif subcommand == "remove":
                shutil.rmtree(Config.inventory_dir + "/roles/" + role)

        elif command == "directive":
            directive = command_arg
            subcommand = argv[3] if len(argv) > 3 else ""
            subcommand_arg = argv[4] if len(argv) > 4 else ""
            if subcommand == "add":
                pathlib.Path(
                    Config.inventory_dir + "/directives/" + directive + ".py"
                ).touch()
            elif subcommand == "remove":
                shutil.rmtree(Config.inventory_dir + "/directives/" + directive)
            else:
                Utilities.fetch_inventory()
                logging.debug("executing directives")
                Utilities.execute_directives()
        elif command == "module":
            module = command_arg
            subcommand = argv[3] if len(argv) > 3 else ""
            subcommand_arg = argv[4] if len(argv) > 4 else ""
            if subcommand == "add":
                os.makedirs(Config.inventory_dir + "/modules/" + module, exist_ok=True)
                pathlib.Path(
                    Config.inventory_dir + "/modules/" + module + "/apply.py"
                ).touch()
                pathlib.Path(
                    Config.inventory_dir + "/modules/" + module + "/test.py"
                ).touch()
                pathlib.Path(
                    Config.inventory_dir + "/modules/" + module + "/drop.py"
                ).touch()
                pathlib.Path(
                    Config.inventory_dir + "/modules/" + module + "/variables.py"
                ).touch()
            elif subcommand == "remove":
                shutil.rmtree(Config.inventory_dir + "/modules/" + module)

        elif command == "host":
            host = command_arg
            subcommand = argv[3] if len(argv) > 3 else ""
            subcommand_arg = argv[4] if len(argv) > 4 else ""
            if subcommand == "add":
                os.makedirs(Config.inventory_dir + "/hosts/" + host, exist_ok=True)
                pathlib.Path(
                    Config.inventory_dir + "/hosts/" + host + "/variables.py"
                ).touch()
                pathlib.Path(Config.inventory_dir + "/hosts/" + host + "/roles").touch()
                pathlib.Path(
                    Config.inventory_dir + "/hosts/" + host + "/modules"
                ).touch()
            elif subcommand == "remove":
                shutil.rmtree(Config.inventory_dir + "/hosts/" + host)
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
        elif command == "reset":
            shutil.rmtree(Config.cosmos_root) if os.name != "nt" else subprocess.run(
                [
                    "cmd",
                    "/c",
                    "rmdir",
                    "/S",
                    "/Q",
                    Config.cosmos_root.replace("/", "\\"),
                ]
            )
            EntryPoints.install()

        else:
            assert False, "unknown command %s" % command

    except (KeyboardInterrupt, SystemExit) as e:
        logging.info("exiting due to interruption: %s", repr(e))
    except Exception as e:
        logging.exception("exiting abnormally with error %s", repr(e))
        return 1
    finally:
        thread_stop.append(None)
        [t.join() for t in threads]
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
