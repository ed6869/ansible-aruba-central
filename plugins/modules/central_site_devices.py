#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: central_site_devices
short_description: Manage device-to-site associations in HPE Aruba Classic Central
description:
  - Supports C(state=query) to list all Classic Central sites with their numeric IDs.
  - Supports C(state=present) to associate one or more devices to a site in bulk.
  - Uses Classic Central OAuth2 flow (refresh_token fast path or username/password).
  - Query endpoint C(GET /central/v2/sites).
  - Associate endpoint C(POST /central/v2/sites/associations).
version_added: "1.0.0"
author:
  - HPE Aruba Central Ansible Community
options:
  state:
    description:
      - C(query) lists all Classic Central sites with their numeric site IDs.
      - C(present) associates the devices to the specified site.
    type: str
    default: present
    choices: [present, absent, query]
  base_url:
    description:
      - Base URL of the Classic Central API gateway.
      - Example C(https://eu-apigw.central.arubanetworks.com).
    type: str
    required: true
  client_id:
    description: Classic Central application client ID.
    type: str
    required: true
  client_secret:
    description: Classic Central application client secret. Use Ansible Vault.
    type: str
    required: true
    no_log: true
  customer_id:
    description: Classic Central customer ID.
    type: str
    required: true
  refresh_token:
    description:
      - Existing refresh token. If provided, OAuth steps 1-2 are skipped.
      - Preferred for automation. Store in Ansible Vault.
    type: str
    required: false
    no_log: true
  username:
    description: Central user email. Required only if refresh_token is not provided.
    type: str
    required: false
  password:
    description: Central user password. Required only if refresh_token is not provided.
    type: str
    required: false
    no_log: true
  site_id:
    description:
      - Numeric Classic Central site ID.
      - Required for C(state=present). Use C(state=query) to retrieve it.
    type: int
    required: false
  device_type:
    description:
      - Type of devices to associate.
      - Required for C(state=present).
    type: str
    required: false
    choices: [IAP, SWITCH, CONTROLLER]
  device_serials:
    description:
      - List of device serial numbers to associate with the site.
      - Required for C(state=present). Can be empty list for C(state=query).
    type: list
    elements: str
    required: false
    default: []
notes:
  - The returned C(new_refresh_token) should be stored back in vault for the next run.
  - This is a community project, not officially supported by HPE.
"""

EXAMPLES = r"""
# ── Query sites to discover numeric site IDs ──────────────────────────────────
- name: List all Classic Central sites
  workflow.aruba_central.central_site_devices:
    base_url: "https://eu-apigw.central.arubanetworks.com"
    state: query
    client_id: "{{ classic_central_client_id }}"
    client_secret: "{{ classic_central_client_secret }}"
    customer_id: "{{ classic_central_customer_id }}"
    refresh_token: "{{ classic_central_refresh_token }}"
  register: sites_result

- name: Display site names and IDs
  debug:
    msg: "{{ sites_result.sites | map(attribute='site_name') | list }}"

# ── Associate devices to a site ───────────────────────────────────────────────
- name: Associate switches to Paris-HQ site
  workflow.aruba_central.central_site_devices:
    base_url: "https://eu-apigw.central.arubanetworks.com"
    state: present
    client_id: "{{ classic_central_client_id }}"
    client_secret: "{{ classic_central_client_secret }}"
    customer_id: "{{ classic_central_customer_id }}"
    refresh_token: "{{ classic_central_refresh_token }}"
    site_id: 42
    device_type: SWITCH
    device_serials:
      - "SG03KW500G"
      - "SG3ALN0004"
  register: result

- name: Show failed devices if any
  debug:
    msg: "Failed: {{ result.failed }}"
  when: result.failed | length > 0
"""

RETURN = r"""
sites:
  description: List of Classic Central sites with their IDs (state=query only).
  type: list
  returned: when state is query
  sample:
    - site_id: 42
      site_name: "Paris-HQ"
total:
  description: Total number of sites returned (state=query only).
  type: int
  returned: when state is query
site_id:
  description: Numeric site ID devices were associated to (state=present only).
  type: int
  returned: when state is present
device_serials:
  description: List of device serials submitted.
  type: list
  returned: when state is present
success:
  description: List of successfully associated device IDs.
  type: list
  returned: when state is present
failed:
  description: List of devices that failed to associate, with reasons.
  type: list
  returned: when state is present
new_refresh_token:
  description: New refresh token — store back in vault for the next run.
  type: str
  returned: always
  no_log: true
msg:
  description: Human-readable status message.
  type: str
  returned: always
"""

import json

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.workflow.aruba_central.plugins.module_utils.classic_central_auth import (
    get_classic_central_token,
)


def _query_sites(module, base_url, token):
    """GET /central/v2/sites — return all sites with their numeric IDs."""
    url = "{0}/central/v2/sites?limit=100&offset=0".format(base_url)
    req = Request(url, headers={
        "Authorization": "Bearer {0}".format(token),
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
        module.fail_json(msg="Connection error: {0}".format(str(e)))


def _associate_devices(module, base_url, token, site_id, device_type, device_serials):
    """POST /central/v2/sites/associations — associate a list of devices to a site."""
    url = "{0}/central/v2/sites/associations".format(base_url)
    payload = {
        "site_id": site_id,
        "device_type": device_type,
        "device_ids": device_serials,
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST", headers={
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
        module.fail_json(msg="Connection error: {0}".format(str(e)))


def _remove_devices(module, base_url, token, site_id, device_type, device_serials):
    """DELETE /central/v2/sites/associations — remove a list of devices from a site."""
    url = "{0}/central/v2/sites/associations".format(base_url)
    payload = {
        "site_id": site_id,
        "device_type": device_type,
        "device_ids": device_serials,
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="DELETE", headers={
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
        module.fail_json(msg="Connection error: {0}".format(str(e)))


def main():
    module_args = dict(
        state=dict(type="str", default="present", choices=["present", "absent", "query"]),
        base_url=dict(type="str", required=True),
        client_id=dict(type="str", required=True),
        client_secret=dict(type="str", required=True, no_log=True),
        customer_id=dict(type="str", required=True),
        refresh_token=dict(type="str", required=False, no_log=True),
        username=dict(type="str", required=False),
        password=dict(type="str", required=False, no_log=True),
        site_id=dict(type="int", required=False),
        site_name=dict(type="str", required=False),
        device_type=dict(type="str", required=False, choices=["IAP", "SWITCH", "CONTROLLER"]),
        device_serials=dict(type="list", elements="str", required=False, default=[]),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)
    p = module.params

    # ── Authenticate ──────────────────────────────────────────────────────────
    token_data = get_classic_central_token(
        module,
        base_url=p["base_url"].rstrip("/"),
        client_id=p["client_id"],
        client_secret=p["client_secret"],
        customer_id=p["customer_id"],
        refresh_token=p.get("refresh_token"),
        username=p.get("username"),
        password=p.get("password"),
    )

    access_token = token_data["access_token"]
    new_refresh_token = token_data["refresh_token"]

    # ── Persist new refresh token for subsequent tasks in same playbook run ──
    try:
        with open("/tmp/.central_refresh_token", "w") as _f:
            _f.write(new_refresh_token)
    except Exception:
        pass  # non-fatal


    # ── Query state ───────────────────────────────────────────────────────────
    if p["state"] == "query":
        status, resp = _query_sites(module, p["base_url"].rstrip("/"), access_token)
        if status == 200:
            sites = resp.get("sites", [])
            module.exit_json(
                changed=False,
                sites=sites,
                total=resp.get("total", len(sites)),
                new_refresh_token=new_refresh_token,
                msg="Found {0} site(s).".format(resp.get("total", len(sites))),
            )
        module.fail_json(
            msg="Failed to query sites: HTTP {0}".format(status),
            new_refresh_token=new_refresh_token,
            response=resp,
        )

    # ── Absent state ──────────────────────────────────────────────────────────
    if p["state"] == "absent":
        if not p.get("site_id"):
            module.fail_json(msg="'site_id' is required for state=absent")
        if not p.get("device_type"):
            module.fail_json(msg="'device_type' is required for state=absent")
        if not p.get("device_serials"):
            module.fail_json(msg="'device_serials' cannot be empty for state=absent")

        status, resp = _remove_devices(
            module,
            p["base_url"].rstrip("/"),
            access_token,
            p["site_id"],
            p["device_type"],
            p["device_serials"],
        )

        success = resp.get("success", [])
        failed  = resp.get("failed", [])

        if status not in (200, 201):
            module.fail_json(
                msg="Failed to remove devices from site: HTTP {0}".format(status),
                site_id=p["site_id"],
                device_serials=p["device_serials"],
                new_refresh_token=new_refresh_token,
                response=resp,
            )

        failed_details = []
        if isinstance(failed, list):
            for f in failed:
                if isinstance(f, dict):
                    failed_details.append("{0}: {1}".format(
                        f.get("device_id", "?"), f.get("reason", "unknown")
                    ))
                else:
                    failed_details.append(str(f))

        real_failures = [f for f in failed_details if "NOT_ASSOCIATED" not in f and "NOT_ASSIGNED" not in f and "SITE_ERR_DELETE_ASSOCIATION" not in f]

        site_label = p.get("site_name") or str(p["site_id"])
        msg = "Removed {0} device(s) from site {1}.".format(len(success), site_label)
        if failed_details:
            msg += " Failed/Skipped: {0}".format(", ".join(failed_details))

        if real_failures:
            module.fail_json(
                msg=msg,
                site_id=p["site_id"],
                device_serials=p["device_serials"],
                new_refresh_token=new_refresh_token,
                success=success,
                failed=failed,
            )

        module.exit_json(
            changed=len(success) > 0,
            site_id=p["site_id"],
            device_serials=p["device_serials"],
            new_refresh_token=new_refresh_token,
            success=success,
            skipped_devices=failed,
            msg=msg,
        )

    # ── Present state ─────────────────────────────────────────────────────────
    if not p.get("site_id"):
        module.fail_json(msg="'site_id' is required for state=present")
    if not p.get("device_type"):
        module.fail_json(msg="'device_type' is required for state=present")
    if not p.get("device_serials"):
        module.fail_json(msg="'device_serials' cannot be empty for state=present")

    status, resp = _associate_devices(
        module,
        p["base_url"].rstrip("/"),
        access_token,
        p["site_id"],
        p["device_type"],
        p["device_serials"],
    )

    # API returns {"success": [...], "failed": [...]}
    success = resp.get("success", [])
    failed  = resp.get("failed", [])

    if status not in (200, 201):
        module.fail_json(
            msg="Failed to associate devices to site: HTTP {0}".format(status),
            site_id=p["site_id"],
            device_serials=p["device_serials"],
            new_refresh_token=new_refresh_token,
            response=resp,
        )

    # Build human-readable failed details
    failed_details = []
    if isinstance(failed, list):
        for f in failed:
            if isinstance(f, dict):
                failed_details.append("{0}: {1}".format(
                    f.get("device_id", "?"), f.get("reason", "unknown")
                ))
            else:
                failed_details.append(str(f))

    # Already associated is not really a failure - treat as ok
    real_failures = [f for f in failed_details if "ALREADY_ASSOCIATED" not in f and "ALREADY_ASSIGNED" not in f and "SITE_ERR_MAX_NO_ALREADY_ASSIGNED" not in f]

    site_label = p.get("site_name") or str(p["site_id"])
    msg = "Associated {0} device(s) to site {1}.".format(len(success), site_label)
    if failed_details:
        msg += " Failed/Skipped: {0}".format(", ".join(failed_details))

    if real_failures:
        module.fail_json(
            msg=msg,
            site_id=p["site_id"],
            device_serials=p["device_serials"],
            new_refresh_token=new_refresh_token,
            success=success,
            failed=failed,
        )

    module.exit_json(
        changed=len(success) > 0,
        site_id=p["site_id"],
        device_serials=p["device_serials"],
        new_refresh_token=new_refresh_token,
        success=success,
        skipped_devices=failed,
        msg=msg,
    )


if __name__ == "__main__":
    main()