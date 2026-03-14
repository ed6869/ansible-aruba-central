#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: glp_device
short_description: Manage devices in HPE GreenLake workspace
description:
  - Check if a device exists in the GLP workspace (state=query).
  - Add a device to the GLP workspace if missing (state=present, idempotent).
  - The POST /devices/v1/devices API is asynchronous (202 Accepted).
    The module polls the async operation until SUCCEEDED or FAILED.
  - Note: devices must be valid HPE devices registered in the GLP catalog.
    Devices belonging to another workspace cannot be added.
  - API endpoints C(GET|POST /devices/v1/devices),
    C(GET /devices/v1/async-operations/{id}).
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
  state:
    description:
      - C(query) - check if device exists and return its UUID.
      - C(present) - add device to workspace if not already present.
    type: str
    required: true
    choices: [query, present, absent]
  serial_number:
    description: Device serial number.
    type: str
    required: true
  mac_address:
    description: Device MAC address. Required for state=present.
    type: str
    required: false
  retries:
    description: Number of retries when polling async operation status.
    type: int
    required: false
    default: 12
  delay:
    description: Seconds between retries when polling async operation status.
    type: int
    required: false
    default: 5
"""

EXAMPLES = r"""
- name: Check if device exists in GLP workspace
  workflow.aruba_central.glp_device:
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    state: query
    serial_number: "SG03KW500G"

- name: Add device to GLP workspace
  workflow.aruba_central.glp_device:
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    state: present
    serial_number: "SG03KW500G"
    mac_address: "b8:d4:e7:0d:52:40"
"""

RETURN = r"""
device_id:
  description: GLP UUID of the device.
  type: str
  returned: always
serial_number:
  description: Device serial number.
  type: str
  returned: always
exists:
  description: Whether the device already existed in the workspace.
  type: bool
  returned: always
application_id:
  description: GLP application UUID assigned to the device (if any).
  type: str
  returned: state=query
subscription_key:
  description: Subscription key assigned to the device (if any).
  type: str
  returned: state=query
region:
  description: Region the device is provisioned in (if any).
  type: str
  returned: state=query
archived:
  description: Whether the device is archived.
  type: bool
  returned: state=query
tags:
  description: Tags applied to the device.
  type: dict
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
    from urllib.parse import quote
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError
    from urllib import quote

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


def get_device(module, base_url, token, serial_number):
    """
    GET /devices/v1/devices?filter=serialNumber eq 'SERIAL'
    Returns (device_id, exists, device_detail) tuple.
    device_detail contains full device info (application, subscription, region, archived).
    """
    url = "{0}/devices/v1/devices?filter=serialNumber%20eq%20'{1}'".format(
        base_url.rstrip("/"), quote(serial_number, safe="")
    )
    status, body = api_request(module, url, token)
    if status != 200:
        module.fail_json(
            msg="Failed to query device {0}: HTTP {1} - {2}".format(
                serial_number, status, body)
        )
    if body.get("total", 0) > 0:
        item = body["items"][0]
        return item["id"], True, item
    return None, False, {}


def add_device(module, base_url, token, serial_number, mac_address):
    """
    POST /devices/v1/devices
    Adds a network device to the GLP workspace.
    Returns (status, body) — body contains transactionId for async polling.
    Note: device must be a valid HPE device registered in the GLP catalog.
    """
    url = "{0}/devices/v1/devices".format(base_url.rstrip("/"))
    payload = {
        "network": [{"serialNumber": serial_number, "macAddress": mac_address}],
        "compute": [],
        "storage": [],
    }
    return api_request(module, url, token, method="POST", payload=payload)


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
            # async-operations endpoint may return 404 if operation expired
            return "UNKNOWN", body
        op_status = body.get("status", "")
        if op_status in ("SUCCEEDED", "FAILED"):
            return op_status, body
        time.sleep(delay)
    return "TIMEOUT", {}



def _patch_device_tags(module, base_url, token, device_id, tags, serial_number):
    """
    PATCH /devices/v1/devices?id=<device_id> with tags dict.
    Tags with null value will be removed on the device.
    """
    url = "{0}/devices/v1/devices?id={1}".format(base_url.rstrip("/"), device_id)
    status, resp = api_request(module, url, token, method="PATCH", payload={"tags": tags})
    if status not in (200, 202):
        module.fail_json(
            msg="Failed to apply tags to device {0}: HTTP {1} - {2}".format(
                serial_number, status, resp),
            serial_number=serial_number,
        )
    # Tags PATCH is synchronous (200) or async (202) — poll if needed
    if status == 202:
        transaction_id = resp.get("transactionId")
        if transaction_id:
            op_status, op_body = poll_async(
                module, base_url, token, transaction_id,
                retries=10, delay=3
            )
            if op_status == "FAILED":
                module.fail_json(
                    msg="Tag application for device {0} failed: {1}".format(
                        serial_number, op_body),
                    serial_number=serial_number,
                )

def main():
    module_args = dict(
        base_url=dict(type="str", required=False, default="https://global.api.greenlake.hpe.com"),
        client_id=dict(type="str", required=True),
        client_secret=dict(type="str", required=True, no_log=True),
        state=dict(type="str", required=True, choices=["query", "present", "absent"]),
        serial_number=dict(type="str", required=True),
        mac_address=dict(type="str", required=False),
        tags=dict(type="dict", required=False, default=None),
        retries=dict(type="int", required=False, default=12),
        delay=dict(type="int", required=False, default=5),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)
    p = module.params

    if p["state"] == "present" and not p["mac_address"]:
        module.fail_json(msg="'mac_address' is required for state=present")

    # Authenticate via GLP SSO
    token = get_central_token(module, p["client_id"], p["client_secret"])

    # ── Query ─────────────────────────────────────────────────────────────────
    if p["state"] == "query":
        device_id, exists, device_detail = get_device(module, p["base_url"], token, p["serial_number"])
        app = device_detail.get("application") or {}
        subs = device_detail.get("subscription") or []
        sub_key = subs[0].get("key") if subs else None
        module.exit_json(
            changed=False,
            device_id=device_id,
            serial_number=p["serial_number"],
            exists=exists,
            application_id=app.get("id"),
            subscription_key=sub_key,
            region=device_detail.get("region"),
            archived=device_detail.get("archived", False),
            msg="{0}: {1}".format(
                p["serial_number"],
                "found in GLP workspace (id={0}, app={1}, sub={2}, archived={3})".format(
                    device_id, app.get("id"), sub_key, device_detail.get("archived", False)
                ) if exists else "not found in GLP workspace"
            ),
        )

    # ── Present (idempotent add) ───────────────────────────────────────────────
    if p["state"] == "present":
        device_id, exists, device_detail = get_device(module, p["base_url"], token, p["serial_number"])
        if exists:
            module.exit_json(
                changed=False,
                device_id=device_id,
                serial_number=p["serial_number"],
                exists=True,
                msg="{0}: already in GLP workspace (id={1}) — skipping.".format(
                    p["serial_number"], device_id
                ),
            )

        # Add device (async 202)
        status, resp = add_device(
            module, p["base_url"], token, p["serial_number"], p["mac_address"]
        )
        if status not in (200, 201, 202):
            module.fail_json(
                msg="Failed to add device {0}: HTTP {1} - {2}".format(
                    p["serial_number"], status, resp),
                serial_number=p["serial_number"],
            )

        # Poll async operation if transactionId returned
        transaction_id = resp.get("transactionId")
        if transaction_id:
            op_status, op_body = poll_async(
                module, p["base_url"], token, transaction_id,
                p["retries"], p["delay"]
            )
            if op_status == "FAILED":
                module.fail_json(
                    msg="{0}: add to GLP workspace failed: {1}".format(
                        p["serial_number"], op_body),
                    serial_number=p["serial_number"],
                )
            # UNKNOWN/TIMEOUT — async-operations may expire quickly, continue to GET

        # Fetch UUID after async completion
        device_id, found = get_device(module, p["base_url"], token, p["serial_number"])
        if not found or not device_id:
            module.fail_json(
                msg="{0}: POST accepted but device not found in workspace. "
                    "Ensure the device serial/MAC is valid and registered in HPE catalog. "
                    "Devices from other workspaces cannot be added.".format(
                        p["serial_number"]),
                serial_number=p["serial_number"],
            )

        module.exit_json(
            changed=True,
            device_id=device_id,
            serial_number=p["serial_number"],
            exists=False,
            msg="{0}: added to GLP workspace (id={1}).".format(
                p["serial_number"], device_id),
        )



    # ── Absent (archive device) ───────────────────────────────────────────────
    if p["state"] == "absent":
        device_id, exists, device_detail = get_device(
            module, p["base_url"], token, p["serial_number"]
        )
        if not exists:
            module.exit_json(
                changed=False,
                device_id=None,
                serial_number=p["serial_number"],
                exists=False,
                msg="{0}: not found in GLP workspace — skipping archive.".format(
                    p["serial_number"]
                ),
            )
        if device_detail.get("archived", False):
            module.exit_json(
                changed=False,
                device_id=device_id,
                serial_number=p["serial_number"],
                exists=True,
                msg="{0}: already archived — skipping.".format(p["serial_number"]),
            )
        # Archive via PATCH ?id=<device_id> with archived=true
        url = "{0}/devices/v1/devices?id={1}".format(
            p["base_url"].rstrip("/"), device_id
        )
        status, resp = api_request(
            module, url, token, method="PATCH", payload={"archived": True}
        )
        if status not in (200, 202):
            module.fail_json(
                msg="Failed to archive device {0}: HTTP {1} - {2}".format(
                    p["serial_number"], status, resp),
                serial_number=p["serial_number"],
            )
        # Poll async if transactionId returned
        transaction_id = resp.get("transactionId")
        if transaction_id:
            op_status, op_body = poll_async(
                module, p["base_url"], token, transaction_id,
                p["retries"], p["delay"]
            )
            if op_status == "FAILED":
                module.fail_json(
                    msg="{0}: archive failed: {1}".format(p["serial_number"], op_body),
                    serial_number=p["serial_number"],
                )
        module.exit_json(
            changed=True,
            device_id=device_id,
            serial_number=p["serial_number"],
            exists=True,
            msg="{0}: archived successfully.".format(p["serial_number"]),
        )

if __name__ == "__main__":
    main()