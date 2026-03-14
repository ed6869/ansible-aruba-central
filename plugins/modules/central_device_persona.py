#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: central_device_persona
short_description: Assign a persona (device function) to devices in HPE Aruba New Central
description:
  - Assigns a device function/persona to one or more devices via New Central API.
  - API endpoint C(POST /network-config/v1alpha1/persona-assignment/{device-function}).
version_added: "1.0.0"
author:
  - HPE Aruba Central Ansible Community
options:
  base_url:
    description: New Central API gateway base URL.
    type: str
    required: true
  client_id:
    description: GLP API client ID.
    type: str
    required: true
  client_secret:
    description: GLP API client secret. Use Ansible Vault.
    type: str
    required: true
    no_log: true
  device_serials:
    description: List of device serial numbers to assign the persona to.
    type: list
    elements: str
    required: true
  persona:
    description:
      - Device function to assign. Use the API value directly.
    type: str
    required: true
    choices:
      - ACCESS_SWITCH
      - AGG_SWITCH
      - ALL
      - AOSS_ACCESS_SWITCH
      - AOSS_AGG_SWITCH
      - AOSS_CORE_SWITCH
      - BRANCH_GW
      - BRIDGE
      - CAMPUS_AP
      - CORE_SWITCH
      - HYBRID_NAC
      - IOT
      - MICROBRANCH_AP
      - MOBILITY_GW
      - SERVICE_PERSONA
      - VPNC
"""

EXAMPLES = r"""
- name: Assign Access Switch persona to a switch
  workflow.aruba_central.central_device_persona:
    base_url: "https://de1.api.central.arubanetworks.com"
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    device_serials:
      - "SG03KW500G"
    persona: "ACCESS_SWITCH"

- name: Assign Campus AP persona to multiple APs
  workflow.aruba_central.central_device_persona:
    base_url: "https://de1.api.central.arubanetworks.com"
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    device_serials:
      - "AP001"
      - "AP002"
    persona: "CAMPUS_AP"
"""

RETURN = r"""
persona:
  description: API device-function value that was assigned.
  type: str
  returned: always
device_serials:
  description: List of device serials the persona was assigned to.
  type: list
  returned: always
msg:
  description: Human-readable status message.
  type: str
  returned: always
response:
  description: Raw API response body.
  type: dict
  returned: always
"""

import json

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.workflow.aruba_central.plugins.module_utils.central_auth import (
    get_central_token,
)

# All supported device-function values from the New Central API swagger
SUPPORTED_PERSONAS = [
    "ACCESS_SWITCH",
    "AGG_SWITCH",
    "ALL",
    "AOSS_ACCESS_SWITCH",
    "AOSS_AGG_SWITCH",
    "AOSS_CORE_SWITCH",
    "BRANCH_GW",
    "BRIDGE",
    "CAMPUS_AP",
    "CORE_SWITCH",
    "HYBRID_NAC",
    "IOT",
    "MICROBRANCH_AP",
    "MOBILITY_GW",
    "SERVICE_PERSONA",
    "VPNC",
]


def assign_persona(module, base_url, token, device_function, device_serials):
    """
    POST /network-config/v1alpha1/persona-assignment/{device-function}
    Assigns a device function to a list of devices.
    """
    url = "{0}/network-config/v1alpha1/persona-assignment/{1}".format(
        base_url.rstrip("/"), device_function
    )
    payload = {
        "persona-device-list": [
            {
                "device-function": device_function,
                "device-id": device_serials,
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={
        "Authorization": "Bearer {0}".format(token),
        "Content-Type": "application/json",
        "Accept": "application/json",
    })

    try:
        with urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}
    except URLError as e:
        module.fail_json(msg="Connection error calling persona-assignment: {0}".format(str(e)))


def main():
    module_args = dict(
        base_url=dict(type="str", required=True),
        client_id=dict(type="str", required=True),
        client_secret=dict(type="str", required=True, no_log=True),
        device_serials=dict(type="list", elements="str", required=True),
        persona=dict(type="str", required=True, choices=SUPPORTED_PERSONAS),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)
    p = module.params

    # Authenticate via GLP SSO
    token = get_central_token(module, p["client_id"], p["client_secret"])

    # Assign persona via New Central API
    status, resp = assign_persona(
        module,
        p["base_url"],
        token,
        p["persona"],
        p["device_serials"],
    )

    if status not in (200, 201):
        module.fail_json(
            msg="Failed to assign persona '{0}': HTTP {1} - {2}".format(
                p["persona"], status, resp
            ),
            persona=p["persona"],
            device_serials=p["device_serials"],
            response=resp,
        )

    module.exit_json(
        changed=True,
        persona=p["persona"],
        device_serials=p["device_serials"],
        msg="Persona '{0}' successfully assigned to {1} device(s).".format(
            p["persona"], len(p["device_serials"])
        ),
        response=resp,
    )


if __name__ == "__main__":
    main()