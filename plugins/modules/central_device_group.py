#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: central_device_group
short_description: Manage device groups in HPE Aruba Classic Central
description:
  - Query or create device groups via Classic Central API.
  - Query fetches group list from C(GET /configuration/v2/groups) then enriches
    each group with properties from C(GET /configuration/v1/groups/properties).
  - Create uses C(POST /configuration/v3/groups).
  - Idempotent for C(state=present) — skips creation if group already exists.
version_added: "1.0.0"
author:
  - HPE Aruba Central Ansible Community
options:
  base_url:
    description: Classic Central API gateway base URL.
    type: str
    required: true
  client_id:
    description: Classic Central OAuth2 client ID.
    type: str
    required: true
  client_secret:
    description: Classic Central OAuth2 client secret. Use Ansible Vault.
    type: str
    required: true
    no_log: true
  customer_id:
    description: Classic Central customer ID.
    type: str
    required: true
  refresh_token:
    description: Classic Central OAuth2 refresh token. Use Ansible Vault.
    type: str
    required: false
    no_log: true
  username:
    description: Classic Central username. Required if refresh token is invalid.
    type: str
    required: false
  password:
    description: Classic Central password. Required if refresh token is invalid.
    type: str
    required: false
    no_log: true
  state:
    description:
      - C(query) - list all device groups with their properties.
      - C(present) - create device group if it does not exist (idempotent).
    type: str
    required: true
    choices: [query, present, updated, absent, move]
  group_name:
    description:
      - Name of the device group to create.
      - Required for C(state=present).
    type: str
    required: false
  allowed_dev_types:
    description:
      - Device types allowed in the group.
      - Required for C(state=present).
    type: list
    elements: str
    required: false
    default: ["AccessPoints", "Gateways", "Switches"]
    choices: [AccessPoints, Gateways, Switches, SD_WAN_Gateway]
  allowed_switch_types:
    description:
      - Switch types allowed in the group.
      - Required if Switches is in allowed_dev_types.
    type: list
    elements: str
    required: false
    default: ["AOS_CX"]
    choices: [AOS_S, AOS_CX]
  architecture:
    description:
      - Architecture for access points and gateways.
      - Required if AccessPoints or Gateways in allowed_dev_types.
    type: str
    required: false
    default: "AOS10"
    choices: [Instant, AOS10]
  ap_network_role:
    description:
      - Network role for access points.
    type: str
    required: false
    default: "Standard"
    choices: [Standard, Microbranch]
  gw_network_role:
    description:
      - Network role for gateways.
    type: str
    required: false
    default: "WLANGateway"
    choices: [BranchGateway, VPNConcentrator, WLANGateway]
  template_wired:
    description:
      - Use template mode for wired (switches).
      - false means UI mode.
    type: bool
    required: false
    default: false
  template_wireless:
    description:
      - Use template mode for wireless (APs and gateways).
      - false means UI mode.
    type: bool
    required: false
    default: false
  new_central:
    description:
      - Flag to make the group compatible with New Central workflows.
    type: bool
    required: false
    default: true
"""

EXAMPLES = r"""
- name: Query all Classic Central device groups
  workflow.aruba_central.central_device_group:
    base_url: "https://eu-apigw.central.arubanetworks.com"
    client_id: "{{ classic_central_client_id }}"
    client_secret: "{{ classic_central_client_secret }}"
    customer_id: "{{ classic_central_customer_id }}"
    refresh_token: "{{ classic_central_refresh_token | default('') }}"
    username: "{{ classic_central_username | default(omit) }}"
    password: "{{ classic_central_password | default(omit) }}"
    state: query

- name: Create AOS10 device group for onboarding
  workflow.aruba_central.central_device_group:
    base_url: "https://eu-apigw.central.arubanetworks.com"
    client_id: "{{ classic_central_client_id }}"
    client_secret: "{{ classic_central_client_secret }}"
    customer_id: "{{ classic_central_customer_id }}"
    refresh_token: "{{ classic_central_refresh_token | default('') }}"
    username: "{{ classic_central_username | default(omit) }}"
    password: "{{ classic_central_password | default(omit) }}"
    state: present
    group_name: "Ansible_Onboarding"
    allowed_dev_types: ["AccessPoints", "Gateways", "Switches"]
    allowed_switch_types: ["AOS_CX"]
    architecture: "AOS10"
    ap_network_role: "Standard"
    gw_network_role: "WLANGateway"
    new_central: true
"""

RETURN = r"""
groups:
  description: List of device groups with their properties (state=query).
  type: list
  returned: when state=query
group_names:
  description: Flat list of group names (state=query).
  type: list
  returned: when state=query
total:
  description: Total number of device groups (state=query).
  type: int
  returned: when state=query
group_name:
  description: Name of the device group created (state=present).
  type: str
  returned: when state=present
new_refresh_token:
  description: New refresh token to store back in vault for next run.
  type: str
  returned: always
msg:
  description: Human-readable status message.
  type: str
  returned: always
"""

import json

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
    from urllib.parse import quote
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError
    from urllib import quote

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.workflow.aruba_central.plugins.module_utils.classic_central_auth import (
    get_classic_central_token,
)


def api_request(module, url, token, method="GET", payload=None):
    """Generic HTTP request helper for Classic Central API."""
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


def get_group_names(module, base_url, token):
    """
    GET /configuration/v2/groups
    Returns a flat list of all group name strings with pagination.
    """
    all_names = []
    offset = 0
    limit = 20

    while True:
        url = "{0}/configuration/v2/groups?limit={1}&offset={2}".format(
            base_url.rstrip("/"), limit, offset
        )
        status, body = api_request(module, url, token)
        if status != 200:
            module.fail_json(
                msg="Failed to list device groups: HTTP {0} - {1}".format(status, body)
            )
        # Response: {"data": [["group_name"], ...], "total": N}
        items = [entry[0] for entry in body.get("data", []) if entry]
        all_names.extend(items)

        total = body.get("total", len(all_names))
        if len(all_names) >= total or len(items) < limit:
            break
        offset += limit

    return all_names


def get_group_properties(module, base_url, token, group_names):
    """
    GET /configuration/v1/groups/properties?groups=name1,name2,...
    Fetches properties for up to 20 groups per call (API limit).
    Returns a dict: {group_name: properties_dict}
    """
    properties_map = {}
    chunk_size = 20

    for i in range(0, len(group_names), chunk_size):
        chunk = group_names[i:i + chunk_size]
        # URL-encode each name to handle spaces and special characters
        groups_param = ",".join(quote(name, safe="") for name in chunk)
        url = "{0}/configuration/v1/groups/properties?groups={1}".format(
            base_url.rstrip("/"), groups_param
        )
        status, body = api_request(module, url, token)
        if status != 200:
            module.fail_json(
                msg="Failed to fetch group properties: HTTP {0} - {1}".format(status, body)
            )
        # Response: {"data": [{"group": "name", "properties": {...}}, ...]}
        for entry in body.get("data", []):
            name = entry.get("group")
            props = entry.get("properties", {})
            if name:
                properties_map[name] = props

    return properties_map


def create_group(module, base_url, customer_id, token, p):
    """
    POST /configuration/v3/groups?cust_id=<customer_id>
    Creates a new device group with the specified properties.
    """
    url = "{0}/configuration/v3/groups?cust_id={1}".format(
        base_url.rstrip("/"), customer_id
    )

    # Build group_properties based on AllowedDevTypes
    group_properties = {
        "AllowedDevTypes": p["allowed_dev_types"],
        "MonitorOnly": [],
        "NewCentral": p["new_central"],
    }

    # Architecture, ApNetworkRole, GwNetworkRole only apply when APs or Gateways are present
    if "AccessPoints" in p["allowed_dev_types"] or "Gateways" in p["allowed_dev_types"]:
        group_properties["Architecture"] = p["architecture"]
    if "AccessPoints" in p["allowed_dev_types"]:
        group_properties["ApNetworkRole"] = p["ap_network_role"]
    if "Gateways" in p["allowed_dev_types"]:
        group_properties["GwNetworkRole"] = p["gw_network_role"]

    # AllowedSwitchTypes only applies when Switches are present
    if "Switches" in p["allowed_dev_types"]:
        group_properties["AllowedSwitchTypes"] = p["allowed_switch_types"]

    payload = {
        "group": p["group_name"],
        "group_attributes": {
            "template_info": {
                "Wired": p["template_wired"],
                "Wireless": p["template_wireless"],
            },
            "group_properties": group_properties,
        },
    }

    return api_request(module, url, token, method="POST", payload=payload)





def move_devices(module, base_url, token, group_name, device_serials, preserve_config_overrides):
    """
    POST /configuration/v1/devices/move
    Moves a list of devices to the specified group.
    preserve_config_overrides: list of device types to preserve config for (e.g. ["AOS_CX"])
    """
    url = "{0}/configuration/v1/devices/move".format(base_url.rstrip("/"))

    payload = {
        "group": group_name,
        "serials": device_serials,
    }
    if preserve_config_overrides:
        payload["preserve_config_overrides"] = preserve_config_overrides

    return api_request(module, url, token, method="POST", payload=payload)

def update_group(module, base_url, token, group_name, p):
    """
    PATCH /configuration/v2/groups/{group_name}/properties
    Updates properties of an existing device group.
    Only adds new device types — updating existing ones is not permitted by the API.
    """
    url = "{0}/configuration/v2/groups/{1}/properties".format(
        base_url.rstrip("/"), quote(group_name, safe="")
    )

    group_properties = {
        "AllowedDevTypes": p["allowed_dev_types"],
        "MonitorOnly": [],
        "NewCentral": p["new_central"],
    }

    # Architecture, ApNetworkRole, GwNetworkRole only apply when APs or Gateways are present
    if "AccessPoints" in p["allowed_dev_types"] or "Gateways" in p["allowed_dev_types"]:
        group_properties["Architecture"] = p["architecture"]
    if "AccessPoints" in p["allowed_dev_types"]:
        group_properties["ApNetworkRole"] = p["ap_network_role"]
    if "Gateways" in p["allowed_dev_types"]:
        group_properties["GwNetworkRole"] = p["gw_network_role"]
    if "Switches" in p["allowed_dev_types"]:
        group_properties["AllowedSwitchTypes"] = p["allowed_switch_types"]

    payload = {
        "group_properties": group_properties,
        "template_info": {
            "Wired": p["template_wired"],
            "Wireless": p["template_wireless"],
        },
    }

    return api_request(module, url, token, method="PATCH", payload=payload)

def delete_group(module, base_url, token, group_name):
    """
    DELETE /configuration/v1/groups/{group_name}
    Deletes an existing device group by name.
    """
    url = "{0}/configuration/v1/groups/{1}".format(
        base_url.rstrip("/"), quote(group_name, safe="")
    )
    return api_request(module, url, token, method="DELETE")


def main():
    module_args = dict(
        base_url=dict(type="str", required=True),
        client_id=dict(type="str", required=True),
        client_secret=dict(type="str", required=True, no_log=True),
        customer_id=dict(type="str", required=True),
        refresh_token=dict(type="str", required=False, no_log=True),
        username=dict(type="str", required=False),
        password=dict(type="str", required=False, no_log=True),
        state=dict(type="str", required=True, choices=["query", "present", "updated", "absent", "move"]),
        group_name=dict(type="str", required=False),
        allowed_dev_types=dict(
            type="list", elements="str", required=False,
            default=["AccessPoints", "Gateways", "Switches"]
        ),
        allowed_switch_types=dict(
            type="list", elements="str", required=False,
            default=["AOS_CX"]
        ),
        architecture=dict(
            type="str", required=False, default="AOS10",
            choices=["Instant", "AOS10"]
        ),
        ap_network_role=dict(
            type="str", required=False, default="Standard",
            choices=["Standard", "Microbranch"]
        ),
        gw_network_role=dict(
            type="str", required=False, default="WLANGateway",
            choices=["BranchGateway", "VPNConcentrator", "WLANGateway"]
        ),
        template_wired=dict(type="bool", required=False, default=False),
        template_wireless=dict(type="bool", required=False, default=False),
        new_central=dict(type="bool", required=False, default=True),
        device_serials=dict(type="list", elements="str", required=False, default=[]),
        preserve_config_overrides=dict(type="list", elements="str", required=False, default=[]),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)
    p = module.params

    # Validate required params per state
    if p["state"] == "present" and not p["group_name"]:
        module.fail_json(msg="'group_name' is required for state=present")

    # Authenticate via Classic Central OAuth2
    token_data = get_classic_central_token(
        module=module,
        base_url=p["base_url"],
        client_id=p["client_id"],
        client_secret=p["client_secret"],
        customer_id=p["customer_id"],
        username=p.get("username"),
        password=p.get("password"),
        refresh_token=p.get("refresh_token"),
    )
    access_token = token_data["access_token"]
    new_refresh_token = token_data["refresh_token"]

    # Write new refresh token to temp file (avoids no_log masking)
    try:
        open("/tmp/.central_refresh_token", "w").write(new_refresh_token)
    except Exception:
        pass

    # ── Query ─────────────────────────────────────────────────────────────────
    if p["state"] == "query":
        group_names = get_group_names(module, p["base_url"], access_token)
        properties_map = get_group_properties(module, p["base_url"], access_token, group_names)
        groups = [
            {"group": name, "properties": properties_map.get(name, {})}
            for name in group_names
        ]
        module.exit_json(
            changed=False,
            groups=groups,
            group_names=group_names,
            total=len(groups),
            new_refresh_token=new_refresh_token,
            msg="{0} device group(s) found.".format(len(groups)),
        )

    # ── Present (idempotent create) ────────────────────────────────────────────
    if p["state"] == "present":
        # Check if group already exists
        group_names = get_group_names(module, p["base_url"], access_token)
        if p["group_name"] in group_names:
            module.exit_json(
                changed=False,
                group_name=p["group_name"],
                new_refresh_token=new_refresh_token,
                msg="Device group '{0}' already exists — skipping creation.".format(
                    p["group_name"]
                ),
            )

        # Create the group
        status, resp = create_group(module, p["base_url"], p["customer_id"], access_token, p)
        if status not in (200, 201):
            module.fail_json(
                msg="Failed to create device group '{0}': HTTP {1} - {2}".format(
                    p["group_name"], status, resp
                ),
                group_name=p["group_name"],
            )

        module.exit_json(
            changed=True,
            group_name=p["group_name"],
            new_refresh_token=new_refresh_token,
            msg="Device group '{0}' created successfully.".format(p["group_name"]),
        )





    # ── Move devices to group ─────────────────────────────────────────────────
    if p["state"] == "move":
        if not p["group_name"]:
            module.fail_json(msg="'group_name' is required for state=move")
        if not p["device_serials"]:
            module.fail_json(msg="'device_serials' is required for state=move")

        status, resp = move_devices(
            module,
            p["base_url"],
            access_token,
            p["group_name"],
            p["device_serials"],
            p["preserve_config_overrides"],
        )
        if status != 200:
            module.fail_json(
                msg="Failed to move devices to group '{0}': HTTP {1} - {2}".format(
                    p["group_name"], status, resp
                ),
                group_name=p["group_name"],
                device_serials=p["device_serials"],
            )

        module.exit_json(
            changed=True,
            group_name=p["group_name"],
            device_serials=p["device_serials"],
            new_refresh_token=new_refresh_token,
            msg="Successfully moved {0} device(s) to group '{1}'.".format(
                len(p["device_serials"]), p["group_name"]
            ),
        )

    # ── Updated (update properties) ───────────────────────────────────────────
    if p["state"] == "updated":
        if not p["group_name"]:
            module.fail_json(msg="'group_name' is required for state=updated")

        # Check if group exists before attempting update
        group_names = get_group_names(module, p["base_url"], access_token)
        if p["group_name"] not in group_names:
            module.fail_json(
                msg="Device group '{0}' does not exist — cannot update.".format(
                    p["group_name"]
                ),
                group_name=p["group_name"],
            )

        status, resp = update_group(module, p["base_url"], access_token, p["group_name"], p)
        if status not in (200, 201, 204):
            module.fail_json(
                msg="Failed to update device group '{0}': HTTP {1} - {2}".format(
                    p["group_name"], status, resp
                ),
                group_name=p["group_name"],
            )

        module.exit_json(
            changed=True,
            group_name=p["group_name"],
            new_refresh_token=new_refresh_token,
            msg="Device group '{0}' updated successfully.".format(p["group_name"]),
        )

    # ── Absent (delete) ───────────────────────────────────────────────────────
    if p["state"] == "absent":
        if not p["group_name"]:
            module.fail_json(msg="'group_name' is required for state=absent")

        # Check if group exists before attempting delete
        group_names = get_group_names(module, p["base_url"], access_token)
        if p["group_name"] not in group_names:
            module.exit_json(
                changed=False,
                group_name=p["group_name"],
                new_refresh_token=new_refresh_token,
                msg="Device group '{0}' does not exist — skipping deletion.".format(
                    p["group_name"]
                ),
            )

        status, resp = delete_group(module, p["base_url"], access_token, p["group_name"])
        if status not in (200, 201, 204):
            module.fail_json(
                msg="Failed to delete device group '{0}': HTTP {1} - {2}".format(
                    p["group_name"], status, resp
                ),
                group_name=p["group_name"],
            )

        module.exit_json(
            changed=True,
            group_name=p["group_name"],
            new_refresh_token=new_refresh_token,
            msg="Device group '{0}' deleted successfully.".format(p["group_name"]),
        )

if __name__ == "__main__":
    main()