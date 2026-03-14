#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

"""
central_auth.py - Shared authentication helper for HPE Aruba Central modules.

Usage in a module:
    from ansible_collections.workflow.aruba_central.plugins.module_utils.central_auth import get_central_token
    token = get_central_token(module, client_id, client_secret)
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import json

try:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError
    from urllib import urlencode

CENTRAL_AUTH_URL = "https://sso.common.cloud.hpe.com/as/token.oauth2"


def get_central_token(module, client_id, client_secret):
    """
    Authenticate against HPE GreenLake SSO and return a Bearer token
    for HPE Aruba Networking Central API calls.

    :param module: AnsibleModule instance (used for fail_json on error)
    :param client_id: Central API client ID
    :param client_secret: Central API client secret
    :return: access_token string
    """
    payload = urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")

    req = Request(
        CENTRAL_AUTH_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            token = body.get("access_token")
            if not token:
                module.fail_json(msg="Authentication succeeded but no access_token in response.")
            return token
    except HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        module.fail_json(msg="Central authentication failed: HTTP {0} - {1}".format(e.code, error_body))
    except URLError as e:
        module.fail_json(msg="Central authentication failed: {0}".format(str(e)))