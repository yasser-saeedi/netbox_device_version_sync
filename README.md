# NetBox Device Version Sync

NetBox Device Version Sync is a Python script that retrieves software version information from network devices in NetBox and updates a custom field with the retrieved version. It uses Netmiko to connect to supported network devices, obtain their software version, and update the corresponding custom field in NetBox if the version has changed.

## Setup

Make sure you have pre-installed Python 3.6 or later.

Clone this repository:

```bash
git clone https://github.com/yasser-saeedi/netbox_device_version_sync
```

Go to the NetBox_Device_Version_sync directory:

```bash
cd ./netbox_device_version_sync
```

Create a virtual environment to run the script:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install required libraries from the requirements.txt file:

```bash
pip install -r requirements.txt 
```

## How To Run

Command-line arguments:

- --netbox-url: URL of the NetBox
- --netbox-token: NetBox API token
- --device-username: Username to use when connecting to devices
- --device-password: Password to use when connecting to devices

Example:

```bash
python3 netbox_device_version_sync.py --netbox-url https://netbox.example.com --netbox-token 1234567890abcdef --device-username admin --device-password mypassword
```

## Process Overview of The Script

The script uses three seprate functions as following:

- Fist function "get_active_devices_for_noc_tenant" retrieves a list of active devices for the NOC tenant in NetBox. Devices are retrieved in groups of 300 and a dictionary of
    their primary IP addresses, platforms, and software versions (if available).
- Second function "get_version_from_devices" connects to a network device using Netmiko ConnectHandler and retrieve the software version of the device.
- Third function "update_device_version_on_netbox" updates the custom field "sw version" in NetBox for devices with a different software version than that of the corresponding device in           net_devices_dict.

## Supported Device Types

The script currently supports the following device types:

- Cisco IOS (cisco_ios)
- Cisco NX-OS (cisco_nxos)
- Cisco ASA (cisco_asa)
- Aruba OS (aruba_os)
- Palo Alto PAN-OS (paloalto_panos)

## Possible Customization

- The script assumes that the custom field in NetBox for storing the software version is named sw_version. If your custom field has a different name, you'll need to update the script accordingly.
- The script only updates devices that have a status of "active" and a tenant of "noc". If you need to update devices with different statuses or tenants, you'll need to modify the script accordingly.
