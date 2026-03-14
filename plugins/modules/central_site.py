#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: central_site
short_description: Manage sites in HPE Aruba Networking Central
description:
  - Create, update, delete or query sites in HPE Aruba Networking Central.
  - Uses HPE GreenLake SSO for authentication (client_credentials flow).
  - API endpoint C(/network-config/v1/sites).
version_added: "1.0.0"
author:
  - HPE Aruba Central Ansible Community
options:
  base_url:
    description:
      - Base URL of the Central API (depends on your geographical cluster).
      - Example C(https://de1.api.central.arubanetworks.com).
    type: str
    required: true
  client_id:
    description:
      - Central API client ID (from HPE GreenLake Personal API clients).
    type: str
    required: true
  client_secret:
    description:
      - Central API client secret. Use Ansible Vault to protect this value.
    type: str
    required: true
    no_log: true
  state:
    description:
      - C(present) creates the site if it does not exist (idempotent).
      - C(update) updates an existing site identified by C(scope_id).
      - C(absent) deletes a site identified by C(scope_id).
      - C(query) lists sites with optional filtering, sorting and pagination.
    type: str
    default: present
    choices: [present, update, absent, query]
  site_name:
    description:
      - Name of the site. Required for C(present) and C(update).
    type: str
  scope_id:
    description:
      - Scope ID of the site. Required for C(update) and C(absent).
    type: str
  address:
    description: Street address of the site.
    type: str
  city:
    description: City of the site.
    type: str
  state_region:
    description:
      - State or region of the site.
      - Named C(state_region) to avoid conflict with the Ansible C(state) parameter.
      - Maps to the API field C(state).
    type: str
  country:
    description: Country of the site.
    type: str
  zip_code:
    description: ZIP or postal code of the site. Maps to API field C(zipcode).
    type: str
  latitude:
    description: Latitude coordinate of the site location.
    type: float
  longitude:
    description: Longitude coordinate of the site location.
    type: float
  timezone:
    description:
      - Timezone of the site in IANA format (e.g. C(Europe/Paris), C(America/New_York)).
      - Required for C(present) and C(update).
    type: str
  filter:
    description:
      - OData 4.0 filter string for C(query) state.
      - Filterable fields C(scopeName), C(address), C(city), C(state), C(country), C(zipcode), C(collectionName).
      - Example C(city eq 'Paris').
    type: str
  sort:
    description:
      - Sort field for C(query) state.
      - Sortable fields C(scopeName), C(address), C(state), C(country), C(city), C(deviceCount),
        C(collectionName), C(zipcode), C(timezone), C(longitude), C(latitude).
    type: str
  limit:
    description: Number of sites to fetch for C(query) state. Max 100.
    type: int
    default: 100
  offset:
    description: Offset for pagination in C(query) state.
    type: int
    default: 0
notes:
  - Tokens are valid for 2 hours. Each playbook run generates a new token.
  - C(state_region) maps to the API field C(state) to avoid Ansible naming conflict.
  - This is a community project, not officially supported by HPE.
"""

EXAMPLES = r"""
# ── CREATE ────────────────────────────────────────────────────────────────────
- name: Create a site
  workflow.aruba_central.central_site:
    base_url: "https://de1.api.central.arubanetworks.com"
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    state: present
    site_name: "Paris-HQ"
    address: "1 Rue de la Paix"
    city: "Paris"
    state_region: "Ile-de-France"
    country: "France"
    zip_code: "75001"
    latitude: 48.8698
    longitude: 2.3309
    timezone: "Europe/Paris"
  register: site_result

# ── UPDATE ────────────────────────────────────────────────────────────────────
- name: Update a site address
  workflow.aruba_central.central_site:
    base_url: "https://de1.api.central.arubanetworks.com"
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    state: update
    scope_id: "{{ site_result.site_id }}"
    site_name: "Paris-HQ"
    address: "5 Avenue de Opera"
    city: "Paris"
    state_region: "Ile-de-France"
    country: "France"
    zip_code: "75001"
    timezone: "Europe/Paris"

# ── DELETE ────────────────────────────────────────────────────────────────────
- name: Delete a site
  workflow.aruba_central.central_site:
    base_url: "https://de1.api.central.arubanetworks.com"
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    state: absent
    scope_id: "12345678"

# ── QUERY ─────────────────────────────────────────────────────────────────────
- name: List all sites
  workflow.aruba_central.central_site:
    base_url: "https://de1.api.central.arubanetworks.com"
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    state: query
  register: all_sites

- name: Query sites filtered by city
  workflow.aruba_central.central_site:
    base_url: "https://de1.api.central.arubanetworks.com"
    client_id: "{{ central_client_id }}"
    client_secret: "{{ central_client_secret }}"
    state: query
    filter: "city eq 'Paris'"
    sort: "scopeName"
    limit: 50
  register: paris_sites
"""

RETURN = r"""
site_id:
  description: Scope ID of the site.
  type: str
  returned: when state is present or update
  sample: "12345678"
site_name:
  description: Name of the site.
  type: str
  returned: when state is present or update
  sample: "Paris-HQ"
sites:
  description: List of sites returned by the API.
  type: list
  returned: when state is query
  sample: []
total:
  description: Total number of sites matching the query.
  type: int
  returned: when state is query
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
import time
from datetime import datetime

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError
    from urllib import urlencode

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.workflow.aruba_central.plugins.module_utils.central_auth import get_central_token


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_timezone(tz_name):
    """Build timezone dict required by Central API (no pytz dependency)."""
    try:
        import zoneinfo  # Python 3.9+
        zi = zoneinfo.ZoneInfo(tz_name)
        now = datetime.now(zi)
        raw_offset = int(now.utcoffset().total_seconds() * 1000)
        tz_abbr = now.strftime("%Z")
    except Exception:
        raw_offset = -time.timezone * 1000
        tz_abbr = time.tzname[0]
    return {
        "rawOffset": raw_offset,
        "timezoneId": tz_name,
        "timezoneName": tz_abbr,
    }


def _api_request(module, url, method="GET", token=None, payload=None, params=None):
    """Generic HTTP helper. Returns (status_code, response_dict)."""
    if params:
        url = "{0}?{1}".format(url, urlencode(params))

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer {0}".format(token)

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}
    except URLError as e:
        module.fail_json(msg="Connection error: {0}".format(str(e)))


def _build_site_payload(p):
    """Build POST/PUT payload from module params."""
    payload = {"name": p["site_name"]}
    if p.get("address"):
        payload["address"] = p["address"]
    if p.get("city"):
        payload["city"] = p["city"]
    if p.get("state_region"):
        payload["state"] = p["state_region"]  # API field is "state"
    if p.get("country"):
        payload["country"] = p["country"]
    if p.get("zip_code"):
        payload["zipcode"] = p["zip_code"]
    if p.get("latitude") is not None:
        payload["latitude"] = p["latitude"]
    if p.get("longitude") is not None:
        payload["longitude"] = p["longitude"]
    if p.get("timezone"):
        payload["timezone"] = _build_timezone(p["timezone"])
    return payload


# ── Actions ───────────────────────────────────────────────────────────────────

def action_present(module, base_url, token, p):
    """Create site (idempotent)."""
    url = "{0}/network-config/v1/sites".format(base_url)
    payload = _build_site_payload(p)
    status, resp = _api_request(module, url, method="POST", token=token, payload=payload)

    if status in (200, 201):
        site_id = str(resp.get("id") or resp.get("site_id", ""))
        module.exit_json(
            changed=True, site_id=site_id, site_name=p["site_name"],
            msg="Site '{0}' created successfully.".format(p["site_name"]),
            response=resp,
        )

    if status == 409 or (status == 400 and "SITE_NAME_ALREADY_EXIST" in str(resp)):
        module.exit_json(
            changed=False, site_id="", site_name=p["site_name"],
            msg="Site '{0}' already exists, no change made.".format(p["site_name"]),
            response=resp,
        )

    module.fail_json(msg="Failed to create site: HTTP {0}".format(status), response=resp)


def action_update(module, base_url, token, p):
    """Update an existing site."""
    if not p.get("scope_id"):
        module.fail_json(msg="'scope_id' is required for state=update")

    url = "{0}/network-config/v1/sites".format(base_url)
    payload = _build_site_payload(p)
    payload["scopeId"] = p["scope_id"]

    status, resp = _api_request(module, url, method="PUT", token=token, payload=payload)

    if status in (200, 204):
        module.exit_json(
            changed=True, site_id=p["scope_id"], site_name=p.get("site_name", ""),
            msg="Site '{0}' updated successfully.".format(p.get("site_name", p["scope_id"])),
            response=resp,
        )

    module.fail_json(msg="Failed to update site: HTTP {0}".format(status), response=resp)


def action_absent(module, base_url, token, p):
    """Bulk delete sites - POST /network-config/v1/sites/bulk."""
    if not p.get("scope_id"):
        module.fail_json(msg="'scope_id' is required for state=absent")

    url = "{0}/network-config/v1/sites/bulk".format(base_url)
    # API expects: {"items": [{"id": "scope_id"}, ...]}
    payload = {"items": [{"id": p["scope_id"]}]}

    status, resp = _api_request(module, url, method="DELETE", token=token, payload=payload)

    if status in (200, 204):
        module.exit_json(
            changed=True,
            msg="Site '{0}' deleted successfully.".format(p["scope_id"]),
            response=resp,
        )

    if status == 404:
        module.exit_json(
            changed=False,
            msg="Site '{0}' not found, nothing to delete.".format(p["scope_id"]),
            response=resp,
        )

    module.fail_json(msg="Failed to delete site: HTTP {0}".format(status), response=resp)


def action_query(module, base_url, token, p):
    """List/search sites with pagination and filtering."""
    url = "{0}/network-config/v1/sites".format(base_url)
    params = {
        "limit": p.get("limit") or 100,
        "offset": p.get("offset") or 0,
    }
    if p.get("filter"):
        params["filter"] = p["filter"]
    if p.get("sort"):
        params["sort"] = p["sort"]

    status, resp = _api_request(module, url, method="GET", token=token, params=params)

    if status == 200:
        sites = resp.get("items", resp.get("sites", []))
        total = resp.get("total", len(sites))
        module.exit_json(
            changed=False, sites=sites, total=total,
            msg="Found {0} site(s).".format(total),
            response=resp,
        )

    module.fail_json(msg="Failed to query sites: HTTP {0}".format(status), response=resp)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    module_args = dict(
        base_url=dict(type="str", required=True),
        client_id=dict(type="str", required=True),
        client_secret=dict(type="str", required=True, no_log=True),
        state=dict(type="str", default="present",
                   choices=["present", "update", "absent", "query"]),
        site_name=dict(type="str"),
        scope_id=dict(type="str"),
        address=dict(type="str"),
        city=dict(type="str"),
        state_region=dict(type="str"),
        country=dict(type="str"),
        zip_code=dict(type="str"),
        latitude=dict(type="float"),
        longitude=dict(type="float"),
        timezone=dict(type="str"),
        filter=dict(type="str"),
        sort=dict(type="str"),
        limit=dict(type="int", default=100),
        offset=dict(type="int", default=0),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=False)
    p = module.params

    # Validate required args per state
    if p["state"] in ("present", "update") and not p.get("site_name"):
        module.fail_json(msg="'site_name' is required for state={0}".format(p["state"]))
    if p["state"] == "present" and not p.get("timezone"):
        module.fail_json(msg="'timezone' is required for state=present")

    token = get_central_token(module, p["client_id"], p["client_secret"])
    base_url = p["base_url"].rstrip("/")

    dispatch = {
        "present": action_present,
        "update":  action_update,
        "absent":  action_absent,
        "query":   action_query,
    }
    dispatch[p["state"]](module, base_url, token, p)


if __name__ == "__main__":
    main()