import pytest
from unittest.mock import patch
import netbox_device_version_sync


@pytest.fixture
def device():
    return {"device_type": "cisco_ios", "ip": "192.0.2.1"}


@pytest.fixture
def username():
    return "test_user"


@pytest.fixture
def password():
    return "test_password"


def test_get_version_from_devices(device, username, password):
    with patch(
        "netbox_device_version_sync.get_version_from_devices", return_value=None
    ) as mock_get_version:
        result = netbox_device_version_sync.get_version_from_devices(
            device, username, password
        )

    mock_get_version.assert_called_with(device, username, password)
    assert result is None


def test_update_device_version_on_netbox():
    nb_devices_list = [{"device_type": "cisco_ios", "ip": "192.0.2.1"}]
    net_devices_dict = {}
    netbox_token = "test_token"
    netbox_url = "http://test-netbox-url.com"

    with patch(
        "netbox_device_version_sync.update_device_version_on_netbox",
        return_value=None,
    ) as mock_update:
        result = netbox_device_version_sync.update_device_version_on_netbox(
            nb_devices_list, net_devices_dict, netbox_token, netbox_url
        )

    mock_update.assert_called_with(
        nb_devices_list, net_devices_dict, netbox_token, netbox_url
    )
    assert result is None


def test_get_active_devices_for_noc_tenant():
    netbox_token = "test_token"
    netbox_url = "http://test-netbox-url.com"

    with patch("netbox_device_version_sync.requests.get") as mock_get:
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "primary_ip": {"address": "192.0.2.1/24"},
                    "platform": {"slug": "cisco_ios"},
                    "custom_fields": {"sw_version": "1.0"},
                },
                {
                    "primary_ip": {"address": "192.0.2.2/24"},
                    "platform": {"slug": "aruba_os"},
                    "custom_fields": {"sw_version": "2.0"},
                },
            ],
            "next": None,
        }

        devices = netbox_device_version_sync.get_active_devices_for_noc_tenant(
            netbox_token, netbox_url
        )

    mock_get.assert_called_with(
        f"{netbox_url}/api/dcim/devices/",
        headers={"Authorization": f"Token {netbox_token}"},
        params={"status": "active", "tenant": "noc", "limit": 300, "offset": 0},
    )
    assert len(devices) == 2
    assert devices[0]["primary_ip"]["address"] == "192.0.2.1/24"
    assert devices[1]["platform"]["slug"] == "aruba_os"
