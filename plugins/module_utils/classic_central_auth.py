#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, HPE Aruba Central Ansible Collection
# Community project - not supported by HPE
# GNU General Public License v3.0+

"""
classic_central_auth.py - Classic Central OAuth2 authentication helper.
Inspired by the official Aruba Central Python SDK (MIT License).

3-step flow:
  Step 1: POST /oauth2/authorize/central/api/login  -> csrftoken + session cookies
  Step 2: POST /oauth2/authorize/central/api        -> auth_code
  Step 3: POST /oauth2/token                        -> access_token + refresh_token

Fast path (preferred):
  POST /oauth2/token?grant_type=refresh_token       -> new access_token + refresh_token
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

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def _check_requests(module):
    if not HAS_REQUESTS:
        module.fail_json(
            msg="The 'requests' Python library is required. "
                "Install it with: pip3 install requests"
        )


def _step1_login(module, base_url, client_id, username, password, session):
    """
    Step 1: Login and get csrftoken + session cookies.
    Uses requests.Session so cookies are handled automatically.
    Returns csrf_token string.
    """
    url = "{0}/oauth2/authorize/central/api/login?client_id={1}".format(
        base_url.rstrip("/"), client_id
    )
    data = json.dumps({"username": username, "password": password}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    try:
        resp = session.post(url, data=data, headers=headers, verify=True)
    except Exception as e:
        module.fail_json(msg="Classic Central Step 1 - connection error: {0}".format(str(e)))

    if resp.status_code == 429:
        try:
            seconds = resp.json().get("message", "").split("after ")[-1].split(" ")[0]
        except Exception:
            seconds = "unknown"
        module.fail_json(
            msg="Classic Central Step 1 (login) rate limited — retry in {0} seconds".format(seconds)
        )

    if resp.status_code != 200:
        module.fail_json(
            msg="Classic Central Step 1 (login) failed: HTTP {0} - {1}".format(
                resp.status_code, resp.text)
        )

    csrf_token = resp.cookies.get("csrftoken")
    if not csrf_token:
        module.fail_json(
            msg="Classic Central Step 1: no csrftoken in response cookies. "
                "Cookies: {0} Body: {1}".format(dict(resp.cookies), resp.text)
        )

    return csrf_token


def _step2_auth_code(module, base_url, client_id, customer_id, csrf_token, session):
    """
    Step 2: Exchange CSRF + session for auth_code.
    Session cookies (including session=) are sent automatically.
    """
    url = "{0}/oauth2/authorize/central/api?client_id={1}&response_type=code&scope=all".format(
        base_url.rstrip("/"), client_id
    )
    data = json.dumps({"customer_id": customer_id}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": csrf_token,
    }

    try:
        resp = session.post(url, data=data, headers=headers, verify=True)
    except Exception as e:
        module.fail_json(msg="Classic Central Step 2 - connection error: {0}".format(str(e)))

    if resp.status_code != 200:
        module.fail_json(
            msg="Classic Central Step 2 (auth code) failed: HTTP {0} - {1}".format(
                resp.status_code, resp.text)
        )

    try:
        auth_code = resp.json().get("auth_code")
    except Exception:
        auth_code = None

    if not auth_code:
        module.fail_json(
            msg="Classic Central Step 2: no auth_code in response: {0}".format(resp.text)
        )

    return auth_code


def _step3_access_token(module, base_url, client_id, client_secret, auth_code):
    """Step 3: Exchange auth_code for access_token + refresh_token."""
    url = "{0}/oauth2/token?client_id={1}&client_secret={2}&grant_type=authorization_code&code={3}".format(
        base_url.rstrip("/"), client_id, client_secret, auth_code
    )

    try:
        resp = requests.post(url, verify=True)
    except Exception as e:
        module.fail_json(msg="Classic Central Step 3 - connection error: {0}".format(str(e)))

    if resp.status_code != 200:
        module.fail_json(
            msg="Classic Central Step 3 (access token) failed: HTTP {0} - {1}".format(
                resp.status_code, resp.text)
        )

    try:
        body = resp.json()
    except Exception:
        module.fail_json(msg="Classic Central Step 3: invalid JSON response: {0}".format(resp.text))

    if not body.get("access_token"):
        module.fail_json(
            msg="Classic Central Step 3: no access_token in response: {0}".format(body)
        )

    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", ""),
    }


def _refresh_token(module, base_url, client_id, client_secret, refresh_token):
    """Use refresh_token to get a new access_token + refresh_token."""
    url = "{0}/oauth2/token?client_id={1}&client_secret={2}&grant_type=refresh_token&refresh_token={3}".format(
        base_url.rstrip("/"), client_id, client_secret, refresh_token
    )

    try:
        resp = requests.post(url, verify=True)
    except Exception as e:
        return None, -1

    if resp.status_code != 200:
        return None, resp.status_code

    try:
        body = resp.json()
    except Exception:
        return None, resp.status_code

    if not body.get("access_token"):
        return None, resp.status_code

    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", refresh_token),
    }, 200


def get_classic_central_token(
    module,
    base_url,
    client_id,
    client_secret,
    customer_id,
    username=None,
    password=None,
    refresh_token=None,
):
    """
    Get a valid Classic Central access token.

    - If refresh_token provided: try refresh first.
      On failure, auto-fallback to full 3-step OAuth2 flow.
    - Otherwise: full 3-step flow with username + password.

    Returns dict: {access_token, refresh_token}
    """
    _check_requests(module)

    # Fast path: try refresh token first
    if refresh_token:
        token, status = _refresh_token(module, base_url, client_id, client_secret, refresh_token)
        if token:
            return token
        module.warn(
            "Classic Central refresh token invalid (HTTP {0}), "
            "falling back to username/password flow.".format(status)
        )

    # Full OAuth2 flow — uses requests.Session for automatic cookie management
    if not username or not password:
        module.fail_json(
            msg="Classic Central auth: refresh token invalid and no username/password provided. "
                "Add classic_central_username and classic_central_password to vault.yml."
        )

    session = requests.Session()
    csrf_token = _step1_login(module, base_url, client_id, username, password, session)
    auth_code = _step2_auth_code(module, base_url, client_id, customer_id, csrf_token, session)
    return _step3_access_token(module, base_url, client_id, client_secret, auth_code)
