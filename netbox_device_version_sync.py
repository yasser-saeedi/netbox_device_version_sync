from typing import Dict
import re
import argparse
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from pprint import pprint
from netmiko import (
    ConnectHandler,
    NetMikoAuthenticationException,
    NetMikoTimeoutException,
)
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# A dictionary to store device IP addresses and their software versions
net_devices_dict = {}

#A set of device types that are supported by Netmiko
netmiko_device_type_list = {
    "cisco_ios",
    "cisco_nxos",
    "cisco_asa",
    "aruba_os",
    "paloalto_panos",
}

# A lock for thread synchronization
lock = threading.Lock()

def get_active_devices_for_noc_tenant(netbox_token: str, netbox_url: str) -> dict:
    """
    Retrieve a list of devices in NetBox that have a status of 'active' and a
    tenant of 'noc'. Devices are retrieved in groups of 300 and a dictionary of
    their primary IP addresses, platforms, and software versions (if available)
    is returned.

    :param netbox_token: The authentication token for accessing the NetBox API.
    :type netbox_token: str
    :param netbox_url: The URL of the NetBox instance.
    :type netbox_url: str
    :raises requests.exceptions.RequestException: If there is an error while
    communicating with the NetBox API.
    :return: A dictionary containing the primary IP address, platform, and
    software version information (if available) for each device.
    :rtype: dict
    """
    try:
        headers = {"Authorization": f"Token {netbox_token}"}
        params = {"status": "active", "tenant": "noc", "limit": 300, "offset": 0}
        devices_url = f"{netbox_url}/api/dcim/devices/"
        nb_devices_list = []
        while devices_url:
            response = requests.get(devices_url, headers=headers, params=params)
            response.raise_for_status()
            devices_data = response.json()

            for device in devices_data["results"]:
                if device["primary_ip"]:
                    nb_devices_list.append(device)
            devices_url = devices_data["next"]
            if devices_url:
                params["offset"] += params["limit"]
        return nb_devices_list
    except requests.exceptions.RequestException as err:
        logger.error(f"Error communicating with NetBox API: {err}")
        raise


def get_version_from_devices(device, device_username, device_password):
    """
    Connect to a network device using Netmiko and retrieve the software version.

    :param device: A dictionary containing the device information, including
    primary IP address and platform slug.
    :type device: dict
    :param device_username: The username for accessing the device.
    :type device_username: str
    :param device_password: The password for accessing the device.
    :type device_password: str
    :return: The software version of the device.
    :rtype: str
    """
    device_ip = device["primary_ip"]["address"].split("/")[0]
    device_platform = device["platform"]["slug"]
    device = {
        "device_type": device_platform,
        "ip": device_ip,
        "username": device_username,
        "password": device_password,
    }

    try:
        lock.acquire()
        if device_platform in netmiko_device_type_list:
            with ConnectHandler(
                **device, global_delay_factor=3, timeout=15, conn_timeout=15
            ) as net_connect:
                if device_platform == "cisco_ios":
                    output = net_connect.send_command("show version | include Version")
                    match = re.search(r"Version\s+([\w\.]+[\w\(\)]+)", output)
                    if match:
                        net_devices_dict[device_ip] = match.group(1)
                elif device_platform == "cisco_nxos":
                    output = net_connect.send_command(
                        'show version | include "NXOS: version" '
                    )
                    match = re.search(r"NXOS.*version\s+(\S+)", output)
                    if match:
                        net_devices_dict[device_ip] = match.group(1)
                elif device_platform == "cisco_asa":
                    output = net_connect.send_command("show version | include Version")
                    match = re.search(r"Version\s+(\S+)", output)
                    if match:
                        net_devices_dict[device_ip] = match.group(1)
                elif device_platform == "paloalto_panos":
                    output = net_connect.send_command(
                        "show system info | match sw-version"
                    )
                    match = re.search(r"sw-version:\s*(.*)", output)
                    if match:
                        net_devices_dict[device_ip] = match.group(1)
                elif device_platform == "aruba_os":
                    output = net_connect.send_command("show version | include Version ")
                    match = re.search(r"Version\s+:\s+([\w\.]+)", output)
                    if match:
                        net_devices_dict[device_ip] = match.group(1)
                else:
                    raise ValueError(f"Unsupported device_platform: {device_platform}")
        else:
            pass
    except Exception as e:
        logger.error(f"Error connecting to device {device['ip']}: {e}")
        raise
    finally:
        lock.release()


def update_device_version_on_netbox(
    nb_devices_list, net_devices_dict, netbox_token, netbox_url
):
    """
    Update software version for devices in NetBox based on the versions
    retrieved using Netmiko.

    :param nb_devices_list: List of devices in NetBox to update.
    :type nb_devices_list: list
    :param net_devices_dict: Dictionary of devices and their versions
    retrieved using Netmiko.
    :type net_devices_dict: dict
    :param netbox_token: NetBox API token for authentication.
    :type netbox_token: str
    :param netbox_url: URL of the NetBox instance.
    :type netbox_url: str
    :return: None
    """
    headers = {"Authorization": f"Token {netbox_token}"}
    for device in nb_devices_list:
        nb_version = device["custom_fields"]["sw_version"]
        nb_ip = device["primary_ip"]["address"].split("/")[0]
        if net_devices_dict[nb_ip] != nb_version:
            d_version = net_devices_dict[nb_ip]
            print(
                "device version is:",
                net_devices_dict[nb_ip],
                "netbox_version is",
                nb_version,
                "needs to update to",
                d_version,
            )
            # Create a JSON payload with the updated value of the custom field
            payload = {"custom_fields": {"sw_version": d_version}}
            # Send a PATCH request to update the device in NetBox
            url = f"{netbox_url}/api/dcim/devices/{device['id']}/"
            response = requests.patch(url, headers=headers, json=payload)
            # Check the response status code
            if response.status_code == 200:
                logger.info(f"Successfully updated device {device['display']}")
            else:
                logger.error(
                    f"Failed to update device {device['display']}. "
                    f"Status code: {response.status_code}"
                )
        else:
            print(
                "device version is:",
                net_devices_dict[nb_ip],
                "netbox_version is",
                nb_version,
            )


if __name__ == "__main__":
    """
    Retrieves software version information from devices in NetBox and
    updates a custom field.

    Command-line arguments:
    --nb-url: URL of the NetBox API endpoint
    --nb-token: NetBox API token
    --device-username: Username to use when connecting to devices
    --device-password: Password to use when connecting to devices

    Steps:
    1. Parse command-line arguments.
    2. Retrieve a list of active devices for the NOC tenant in NetBox.
    3. Create a thread for each device in the list and start them.
    4. Wait for all the threads to finish.
    5. Update the custom field in NetBox for devices with a different software
    version than that of the corresponding device in net_devices_dict.
    """

    parser = argparse.ArgumentParser(
        description="Retrieves software version information from devices in NetBox "
        "and updates a custom field."
    )
    parser.add_argument("--netbox-url", required=True)
    parser.add_argument("--netbox-token", required=True)
    parser.add_argument("--device-username", required=True)
    parser.add_argument("--device-password", required=True)
    args = parser.parse_args()

    netbox_url = args.netbox_url
    netbox_token = args.netbox_token
    device_username = args.device_username
    device_password = args.device_password

    nb_devices_list = get_active_devices_for_noc_tenant(netbox_token, netbox_url)

    with ThreadPoolExecutor(max_workers=10) as executor:
        for device in nb_devices_list:
            executor.submit(
                get_version_from_devices, device, device_username, device_password
            )

    update_device_version_on_netbox(
        nb_devices_list, net_devices_dict, netbox_token, netbox_url
    )
