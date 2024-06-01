# Cosmos

Cosmos is a minimal distributed service binary/configuration management tool written in Python. It serves as a Python port of [Aviary.sh](https://github.com/frameable/aviary.sh), offering support for both Windows and Linux environments. With Cosmos, all the methods for applying or removing roles are implemented in Python, providing flexibility and ease of use.

## Features

- **Cross-Platform Support**: Works seamlessly on both Windows and Linux systems.
- **Python Implementation**: Now written entirely in Python for improved maintainability and extensibility.
- **Agent-Based**: Operates using an agent-based architecture, offering efficiency and scalability.
- **Lightweight Alternative**: Offers a lightweight alternative to more complex configuration management tools like Ansible, Salt, Puppet, and Chef.

## Example Inventory

To get started with Cosmos, check out the example repository for the inventory format it uses: [Cosmos Inventory Example](https://github.com/jameswdelancey/cosmos_inventory_example).

## Installation

To install Cosmos, follow these simple steps:

1. Download the main.py file from the [Cosmos GitHub repository](https://github.com/jameswdelancey/cosmos/main/cosmos/main.py).
2. Run the following command in Python 3:

```bash
su -l
apt update && apt -y upgrade && apt install -y git python3 python3-pip sudo curl
nano /etc/environment  # Configure your environment variables here
curl -sSf "https://raw.githubusercontent.com/jameswdelancey/cosmos/main/cosmos/main.py" | sudo -E python3 -
```

## Discussion

Cosmos is designed to provide a simple and efficient solution for managing service binaries and configurations. It leverages `/etc/crontab` or `schdtask.exe` for execution timing, ensuring near-realtime configuration updates while allowing for gradual code upgrades. This approach enables easy rollback options and ensures smooth operation even in complex environments.
