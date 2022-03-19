# cosmos
Minimal distributed service binary/configuration management in python

This is a python port of https://github.com/frameable/aviary.sh.
 - Windows and Linux supported
 - Now written in python
 - All the methods to apply or remove roles are written in python

Example repository for the inventory format that this version of cosmos uses:
 - https://github.com/jameswdelancey/cosmos_inventory_example

Install like this:
 - Download: "https://raw.githubusercontent.com/jameswdelancey/cosmos/main/cosmos/main.py"
 - Run this in python3

Discussion:
 - This is a lightweight alternative to Ansible, Salt, Puppet, Chef.
 - This is agent based.
 - This uses /etc/crontab or schdtask.exe for execution timing, at two tempos:
     - Typically the directives timer will run every minute for near-realtime configuration updates
     - The apply timer will run hourly at a random minute, so code upgrades happen more gradually and can be rolled back early if needed.
