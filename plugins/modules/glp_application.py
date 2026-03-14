#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: glp_application
short_description: Assign a GLP application to a device
description:
  - Assigns an application (e.g. HPE Aruba Networking Central) to a device
    in the GLP workspace via C(PATCH /devices/v1/devices?id=<device_id>).
  - Waits for the async operation to complete.
version_added: "1.0.0"
author:
  - HPE Aruba Central Ansible Community
options:
  base_url:
    description: GLP API base URL.
    type: str
    required: false
    default: "https://global.api.greenlake.hpe.com"
  client_id:
    description: GLP OAuth2 client ID.
    type: str
    required: true
  client_secret:
    description: GLP OAuth2 client secret. Use Ansible Vault.
    type: str
    required: true
    no_log: true
  device_id:
    description: GLP UUID of the device (from glp_device module).
    type: str
    required: true
  serial_number:
    description: Device serial number (used for display/logging only).
    type: str
    required: true
  application_id:
    description: GLP application/service manager ID to assign.
    type: str
    required: true
  region:
    description: GLP region for the application assignment.
    type: str
    required: true
  retries:
    description: Number of retries when polling async operation status.
    type: int
    required: false
    default: 10
  delay:
    description: Seconds between retries when polling async operation status.
    type: int
    required: false
    default: 5
"""

EXAMPLES = r"""
- name: Assign Central application to device
  workflow.aruba_central.glp_application:
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    device_id: "{{ device_uuid_map[item.serial_number] }}"
    serial_number: "{{ item.serial_number }}"
    application_id: "{{ glp_central_sm_id }}"
    region: "{{ item.glp.region }}"
"""

RETURN = r"""
serial_number:
  description: Device serial number.
  type: str
  returned: always
device_id:
  description: GLP device UUID.
  type: str
  returned: always
status:
  description: Final async operation status (SUCCEEDED or FAILED).
  type: str
  returned: always
msg:
  description: Human-readable status message.
  type: str
  returned: always
"""

import json
import time

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.workflow.aruba_central.plugins.module_utils.central_auth import (
    get_central_token,
)


def api_request(module, url, token, method="GET", payload=None):
    """Generic HTTP request helper for GLP API."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=body, headers={
        "Authorization": "Bearer {0}".format(token),
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    req.get_method = lambda: method
    try:
        with urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw}
    except HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}
    except URLError as e:
        module.fail_json(msg="Connection error: {0}".format(str(e)))


def assign_application(module, base_url, token, device_id, application_id, region, tags=None):
    """
    PATCH /devices/v1/devices?id=<device_id>
    Assigns or unassigns an application from a device.
    Pass application_id=None and region=None to unassign.
    tags dict can be combined with application assignment (device operations).
    NOTE: tags cannot be combined with subscription operation per API spec.
    """
    url = "{0}/devices/v1/devices?id={1}".format(base_url.rstrip("/"), device_id)
    payload = {
        "application": {"id": application_id},
        "region": region,
    }
    if tags:
        payload["tags"] = tags
    return api_request(module, url, token, method="PATCH", payload=payload)


def poll_async(module, base_url, token, transaction_id, retries, delay):
    """
    GET /devices/v1/async-operations/<transaction_id>
    Polls until status is SUCCEEDED or FAILED, or retries exhausted.
    """
    url = "{0}/devices/v1/async-operations/{1}".format(
        base_url.rstrip("/"), transaction_id
    )
    for attempt in range(retries):
        status, body = api_request(module, url, token)
        if status != 200:
            module.fail_json(
                msg="Failed to poll async operation {0}: HTTP {1} - {2}".format(
                    transaction_id, status, body)
            )
        op_status = body.get("status", "")
        if op_status in ("SUCCEEDED", "FAILED"):
            return op_status, body
        time.sleep(delay)
    return "TIMEOUT", {}


def main():
    module_args = dict(
        base_url=dict(type="str", required=False, default="https://global.api.greenlake.hpe.com"),
        client_id=dict(type="str", required=True),
        client_secret=dict(type="str", required=True, no_log=True),
        state=dict(type="str", required=True, choices=["query", "present", "absent"]),
        device_id=dict(type="str", required=True),
        serial_number=dict(type="str", required=True),
        application_id=dict(type="str", required=True),
        region=dict(type="str", required=True),
        tags=dict(type="dict", required=False, default=None),
        retries=dict(type="int", required=False, default=10),
        delay=dict(type="int", required=False, default=5),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)
    p = module.params

    # Authenticate via GLP SSO

    token = get_central_token(module, p["client_id"], p["client_secret"])

    # ── Query ─────────────────────────────────────────────────────────────────
    if p["state"] == "query":
        url = "{0}/devices/v1/devices/{1}".format(
            p["base_url"].rstrip("/"), p["device_id"]
        )
        status, body = api_request(module, url, token)
        if status != 200:
            module.fail_json(
                msg="Failed to query device {0}: HTTP {1} - {2}".format(
                    p["serial_number"], status, body)
            )
        app = body.get("application") or {}
        module.exit_json(
            changed=False,
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            application_id=app.get("id"),
            region=body.get("region"),
            msg="{0}: application={1}, region={2}".format(
                p["serial_number"], app.get("id"), body.get("region")
            ),
        )

    # ── Absent (unassign application) ─────────────────────────────────────────
    if p["state"] == "absent":
        status, resp = assign_application(
            module, p["base_url"], token, p["device_id"],
            application_id=None, region=None
        )
        if status not in (200, 202):
            module.fail_json(
                msg="Failed to unassign application from device {0}: HTTP {1} - {2}".format(
                    p["serial_number"], status, resp),
                serial_number=p["serial_number"],
                device_id=p["device_id"],
            )
        transaction_id = resp.get("transactionId")
        if transaction_id:
            op_status, op_body = poll_async(
                module, p["base_url"], token, transaction_id, p["retries"], p["delay"]
            )
            if op_status == "FAILED":
                module.fail_json(
                    msg="Application unassignment for device {0} failed: {1}".format(
                        p["serial_number"], op_body),
                    serial_number=p["serial_number"],
                    device_id=p["device_id"],
                )
        module.exit_json(
            changed=True,
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            status="SUCCEEDED",
            msg="Application unassigned from device {0}.".format(p["serial_number"]),
        )

    # ── Present (assign application) ──────────────────────────────────────────
    # Assign application
    status, resp = assign_application(
        module, p["base_url"], token, p["device_id"], p["application_id"], p["region"]
    )
    if status not in (200, 202):
        module.fail_json(
            msg="Failed to assign application to device {0}: HTTP {1} - {2}".format(
                p["serial_number"], status, resp),
            serial_number=p["serial_number"],
            device_id=p["device_id"],
        )

    # Poll async operation
    transaction_id = resp.get("transactionId")
    if not transaction_id:
        # Some devices return 200 synchronously without transactionId
        module.exit_json(
            changed=True,
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            status="SUCCEEDED",
            msg="Application assigned to device {0} (synchronous).".format(p["serial_number"]),
        )

    op_status, op_body = poll_async(
        module, p["base_url"], token, transaction_id, p["retries"], p["delay"]
    )

    if op_status != "SUCCEEDED":
        module.fail_json(
            msg="Application assignment for device {0} {1}: {2}".format(
                p["serial_number"], op_status, op_body),
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            status=op_status,
        )

    module.exit_json(
        changed=True,
        serial_number=p["serial_number"],
        device_id=p["device_id"],
        status=op_status,
        msg="Application assigned to device {0}: {1}.".format(
            p["serial_number"], op_status),
    )


if __name__ == "__main__":
    main()