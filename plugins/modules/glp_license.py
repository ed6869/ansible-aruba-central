#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: glp_license
short_description: Assign a GLP subscription/licence to a device
description:
  - Retrieves available subscriptions from GLP workspace.
  - Assigns a subscription to a device via C(PATCH /devices/v1/devices?id=<device_id>).
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
  subscription_key:
    description: Subscription key to assign (e.g. E6FF23F6C1986469AB).
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
- name: Assign subscription to device
  workflow.aruba_central.glp_license:
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    device_id: "{{ device_uuid_map[item.serial_number] }}"
    serial_number: "{{ item.serial_number }}"
    subscription_key: "{{ item.glp.subscription_key }}"
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
subscription_key:
  description: Subscription key that was assigned.
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


def get_subscription_id(module, base_url, token, subscription_key):
    """
    GET /subscriptions/v1/subscriptions?select=id,key
    Returns the subscription UUID matching the given key.
    """
    url = "{0}/subscriptions/v1/subscriptions?select=id,key".format(base_url.rstrip("/"))
    status, body = api_request(module, url, token)
    if status != 200:
        module.fail_json(
            msg="Failed to retrieve subscriptions: HTTP {0} - {1}".format(status, body)
        )
    for item in body.get("items", []):
        if item.get("key") == subscription_key:
            return item["id"]
    module.fail_json(
        msg="Subscription key '{0}' not found in GLP workspace.".format(subscription_key)
    )


def assign_subscription(module, base_url, token, device_id, subscription_id):
    """
    PATCH /devices/v1/devices?id=<device_id>
    Assigns a subscription to a device.
    Pass subscription_id=None to unassign (sends empty array).
    """
    url = "{0}/devices/v1/devices?id={1}".format(base_url.rstrip("/"), device_id)
    if subscription_id is None:
        payload = {"subscription": []}
    else:
        payload = {"subscription": [{"id": subscription_id}]}
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
        subscription_key=dict(type="str", required=True),
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
        subs = body.get("subscription") or []
        sub_key = subs[0].get("key") if subs else None
        sub_id = subs[0].get("id") if subs else None
        module.exit_json(
            changed=False,
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            subscription_key=sub_key,
            subscription_id=sub_id,
            msg="{0}: subscription_key={1}".format(p["serial_number"], sub_key),
        )

    # ── Absent (unassign subscription) ────────────────────────────────────────
    if p["state"] == "absent":
        status, resp = assign_subscription(
            module, p["base_url"], token, p["device_id"], subscription_id=None
        )
        if status not in (200, 202):
            module.fail_json(
                msg="Failed to unassign subscription from device {0}: HTTP {1} - {2}".format(
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
                    msg="Subscription unassignment for device {0} failed: {1}".format(
                        p["serial_number"], op_body),
                    serial_number=p["serial_number"],
                    device_id=p["device_id"],
                )
        module.exit_json(
            changed=True,
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            subscription_key=p.get("subscription_key", ""),
            status="SUCCEEDED",
            msg="Subscription unassigned from device {0}.".format(p["serial_number"]),
        )

    # ── Present (assign subscription) ─────────────────────────────────────────
    # Resolve subscription key to UUID

    subscription_id = get_subscription_id(
        module, p["base_url"], token, p["subscription_key"]
    )

    # Assign subscription to device
    status, resp = assign_subscription(
        module, p["base_url"], token, p["device_id"], subscription_id
    )
    if status not in (200, 202):
        module.fail_json(
            msg="Failed to assign subscription '{0}' to device {1}: HTTP {2} - {3}".format(
                p["subscription_key"], p["serial_number"], status, resp),
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            subscription_key=p["subscription_key"],
        )

    # Poll async operation
    transaction_id = resp.get("transactionId")
    if not transaction_id:
        module.exit_json(
            changed=True,
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            subscription_key=p["subscription_key"],
            status="SUCCEEDED",
            msg="Subscription '{0}' assigned to device {1} (synchronous).".format(
                p["subscription_key"], p["serial_number"]),
        )

    op_status, op_body = poll_async(
        module, p["base_url"], token, transaction_id, p["retries"], p["delay"]
    )

    if op_status != "SUCCEEDED":
        module.fail_json(
            msg="Subscription assignment for device {0} {1}: {2}".format(
                p["serial_number"], op_status, op_body),
            serial_number=p["serial_number"],
            device_id=p["device_id"],
            subscription_key=p["subscription_key"],
            status=op_status,
        )

    module.exit_json(
        changed=True,
        serial_number=p["serial_number"],
        device_id=p["device_id"],
        subscription_key=p["subscription_key"],
        status=op_status,
        msg="Subscription '{0}' assigned to device {1}: {2}.".format(
            p["subscription_key"], p["serial_number"], op_status),
    )


if __name__ == "__main__":
    main()