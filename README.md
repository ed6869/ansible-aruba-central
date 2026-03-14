# Ansible Collection — HPE Aruba Central Onboarding

Ansible collection to automate the complete onboarding of HPE Aruba devices through **GLP (HPE GreenLake Platform)** and **HPE Aruba Central**.

> **Disclaimer:** This collection is a community project and is **not developed, maintained or supported by HPE**. It is provided as-is, without any warranty. For questions or improvements, please open an issue or a pull request.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Input Files](#input-files)
  - [vault.yml](#vaultyml--credentials)
  - [devices.yml](#devicesyml--devices-to-onboard)
  - [sites.yml](#sitesyml--aruba-central-sites)
  - [device_groups.yml](#device_groupsyml--device-groups)
- [Playbooks](#playbooks)
  - [full_onboarding.yml](#full_onboardingyml)
  - [glp_management.yml](#glp_managementyml)
  - [site_management.yml](#site_managementyml)
  - [device_site_assignment.yml](#device_site_assignmentyml)
  - [device_persona_management.yml](#device_persona_managementyml)
  - [device_group_management.yml](#device_group_managementyml)
  - [device_group_assignment.yml](#device_group_assignmentyml)
- [Safety Guards](#safety-guards)
- [Onboarding Workflow](#onboarding-workflow)
- [Technical Architecture](#technical-architecture)
- [Troubleshooting](#troubleshooting)

---

## Overview

This collection covers the complete device lifecycle across two platforms:

**Phase 1 — GLP Onboarding** *(optional — skip if devices are already in GLP)*
- Add devices to the GLP workspace
- Assign devices to the HPE Aruba Networking Central application
- Apply subscription licenses

**Phase 2 — Central Onboarding** *(required)*
- Site creation and device assignment
- Device persona configuration
- Device group creation and assignment

> **For Central-only onboarding** (skipping GLP): Devices must already be assigned to your Central application with valid subscriptions, in the `default` group, and not assigned to any site.

---

## Architecture

```
ansible_collections/workflow/aruba_central/
├── plugins/
│   ├── modules/
│   │   ├── glp_device.py              # Device management in GLP
│   │   ├── glp_application.py         # Central application assignment in GLP
│   │   ├── glp_license.py             # License assignment in GLP
│   │   ├── central_site.py            # Site management (New Central)
│   │   ├── central_site_devices.py    # Device <-> site association (Classic Central)
│   │   ├── central_device_persona.py  # Device persona assignment (New Central)
│   │   └── central_device_group.py    # Device group management (Classic Central)
│   └── module_utils/
│       ├── central_auth.py            # GLP / New Central auth (OAuth2 SSO)
│       └── classic_central_auth.py    # Classic Central auth (refresh token + fallback)

playbooks/
├── full_onboarding.yml          # Complete onboarding — all steps
├── glp_management.yml           # GLP post-onboarding operations
├── site_management.yml          # Site lifecycle (create/update/delete)
├── device_site_assignment.yml   # Device <-> site association
├── device_persona_management.yml # Device persona assignment
├── device_group_management.yml  # Group lifecycle (create/update/delete)
├── device_group_assignment.yml  # Device <-> group assignment
├── devices.yml                  # Input: device list
├── sites.yml                    # Input: site list
├── device_groups.yml            # Input: device group list
└── vault.yml                    # Credentials (encrypt with ansible-vault)
```

---

## Requirements

- Ansible Core ≥ 2.15
- Python 3.9+
- An HPE GreenLake API client with the following permissions:
  - Devices: Read / Write
  - Subscriptions: Read
  - Service catalog: Read
- Network access to:

| Endpoint | Purpose |
|----------|---------|
| `sso.common.cloud.hpe.com` | GLP authentication |
| `global.api.greenlake.hpe.com` | GLP API |
| New Central API gateway (region-dependent, see table below) | New Central API |
| Classic Central API gateway (region-dependent, see table below) | Classic Central API |

**Classic Central — API Gateway URLs**

| Region | URL |
|--------|-----|
| US-1 | `https://app1-apigw.central.arubanetworks.com` |
| US-2 | `https://apigw-prod2.central.arubanetworks.com` |
| US-East1 | `https://apigw-us-east-1.central.arubanetworks.com` |
| US-West4 | `https://apigw-uswest4.central.arubanetworks.com` |
| US-West5 | `https://apigw-uswest5.central.arubanetworks.com` |
| EU-1 | `https://eu-apigw.central.arubanetworks.com` |
| EU-Central2 | `https://apigw-eucentral2.central.arubanetworks.com` |
| EU-Central3 | `https://apigw-eucentral3.central.arubanetworks.com` |
| Canada-1 | `https://apigw-ca.central.arubanetworks.com` |
| China-1 | `https://apigw.central.arubanetworks.com.cn` |
| APAC-1 | `https://api-ap.central.arubanetworks.com` |
| APAC-EAST1 | `https://apigw-apaceast.central.arubanetworks.com` |
| APAC-SOUTH1 | `https://apigw-apacsouth.central.arubanetworks.com` |
| UAE-NORTH1 | `https://apigw-uaenorth1.central.arubanetworks.com` |

**New Central — API Gateway Base URLs**

| Region | Base URL |
|--------|----------|
| EU-1 | `https://de1.api.central.arubanetworks.com` |
| EU-Central2 | `https://de2.api.central.arubanetworks.com` |
| EU-Central3 | `https://de3.api.central.arubanetworks.com` |
| UK | `https://gb1.api.central.arubanetworks.com` |
| US-1 | `https://us1.api.central.arubanetworks.com` |
| US-2 | `https://us2.api.central.arubanetworks.com` |
| US-West4 | `https://us4.api.central.arubanetworks.com` |
| US-West5 | `https://us5.api.central.arubanetworks.com` |
| US-East1 | `https://us6.api.central.arubanetworks.com` |
| Canada-1 | `https://ca1.api.central.arubanetworks.com` |
| APAC-1 | `https://in.api.central.arubanetworks.com` |
| APAC-EAST1 | `https://jp1.api.central.arubanetworks.com` |
| APAC-SOUTH1 | `https://au1.api.central.arubanetworks.com` |
| UAE | `https://ae1.api.central.arubanetworks.com` |
| China | `https://cn1.api.central.arubanetworks.com.cn` |

> To create a GLP API client, follow the [HPE GreenLake authentication guide](https://developer.greenlake.hpe.com/docs/greenlake/guides/public/authentication/authentication#creating-a-personal-api-client).

---

## Installation

```bash
# Clone the repository
git clone https://github.com/<your-org>/ansible-aruba-central.git
cd ansible-aruba-central

# Install the collection
ansible-galaxy collection install . --force

# Verify
ansible-doc workflow.aruba_central.glp_device
```

Configure `ansible.cfg`:

```ini
[defaults]
inventory = inventory
collections_path = ~/.ansible/collections:~/ansible_collections
```

And `inventory`:

```ini
localhost ansible_connection=local
```

---

## Input Files

### `vault.yml` — Credentials

Contains all required secrets. Encrypt with `ansible-vault encrypt vault.yml` and run playbooks with `--ask-vault-pass`.

```yaml
# ── GLP / New Central ──────────────────────────────────────────────────────────
# How to get these: GLP portal → Manage → API Clients
# Permissions required: Devices R/W, Subscriptions R, Service catalog R
central_client_id: "<your-glp-client-id>"
central_client_secret: "<your-glp-client-secret>"

# Service Manager ID of your Central workspace in GLP
# GLP → Workspace → Services → click "HPE Aruba Networking Central" → ID is in the URL
glp_central_sm_id: "<your-glp-sm-id>"

# ── Classic Central ────────────────────────────────────────────────────────────
# How to get these: Aruba Central → Maintenance → API Gateway → System Apps & Tokens
# Reference: https://developer.arubanetworks.com/central/docs/api-oauth-access-token
classic_central_client_id: "<your-classic-client-id>"
classic_central_client_secret: "<your-classic-client-secret>"

# Classic Central → Global Settings → Customer ID
classic_central_customer_id: "<your-customer-id>"

# User account used as fallback if the refresh token has expired
classic_central_username: "admin@yourcompany.com"
classic_central_password: "<your-password>"

# Single-use refresh token — automatically updated after each run
# Leave empty on first run, it will be initialized automatically
classic_central_refresh_token: ""
```

> ⚠️ **Refresh token is single-use.** The playbook automatically updates it in `vault.yml` after each successful run. Never modify it manually between runs, and never run two playbooks simultaneously against Classic Central.

> ⚠️ **Classic Central rate limit.** The login endpoint (`/oauth2/authorize/central/api/login`) is limited to **3 calls per 30 minutes**. As long as the refresh token is valid, no login call is made. If you hit the rate limit, wait ~30 minutes before retrying. You can verify your token is valid with:
> ```bash
> curl -s -X POST "https://eu-apigw.central.arubanetworks.com/oauth2/token" \
>   -d "grant_type=refresh_token" \
>   -d "client_id=<your-classic-client-id>" \
>   -d "client_secret=<your-classic-client-secret>" \
>   -d "refresh_token=$(cat /tmp/.central_refresh_token)"
> ```
> A valid response returns `{"access_token": "...", "refresh_token": "..."}`. An `{"error": "invalid_request"}` means the token is expired.

> ℹ️ **Token sync.** The latest valid token is always saved to both `vault.yml` and `/tmp/.central_refresh_token`. If vault and file are out of sync, resync with:
> ```bash
> TOKEN=$(cat /tmp/.central_refresh_token)
> sed -i "s/classic_central_refresh_token:.*/classic_central_refresh_token: \"$TOKEN\"/" ~/playbooks/vault.yml
> ```

---

### `devices.yml` — Devices to Onboard

One block per device. All fields are required except `glp.tags`.

```yaml
devices:
  - serial_number: SG03KW500G          # Device serial number
    mac_address: b8:d4:e7:0d:52:40     # MAC address
    device_type: SWITCH                 # SWITCH | AP | GATEWAY
    persona: ACCESS_SWITCH             # New Central persona (see table below)
    device_group: Ansible_Onboarding   # Classic Central group (must exist or be created)
    site: Paris-HQ                     # Site name (must match sites.yml)
    glp:
      region: eu-central               # GLP region (see supported regions below)
      subscription_key: E6FF23F6C1986469AB  # Subscription key (GLP → Subscriptions → Key column)
      # tags:                          # (optional) GLP key/value tags
      #   managed_by: ansible
      #   environment: production
```

**Where to find the serial number and MAC address:**

| Device type | Physical location |
|-------------|-------------------|
| Access Points | Bottom of the device |
| AOS-CX Switches | Pull-out tab on the device |
| Gateways | Back of the device |

**Supported `device_type` / `persona` values:**

| device_type | persona |
|-------------|---------|
| `SWITCH` | `ACCESS_SWITCH`, `CORE_SWITCH`, `DISTRIBUTION_SWITCH` |
| `AP` | `CAMPUS_AP`, `REMOTE_AP`, `MESH_PORTAL`, `MESH_POINT` |
| `GATEWAY` | `BRANCH_GATEWAY`, `VPN_CONCENTRATOR`, `WAN_GATEWAY` |

**Supported GLP regions:**

| Region |
|--------|
| `eu-central` |
| `us-west` |
| `us-east` |
| `ap-northeast` |
| `ap-southeast` |

---

### `sites.yml` — Aruba Central Sites

Defines sites to create and manage in Aruba Central. Names must exactly match the `site` field in `devices.yml`.

```yaml
sites:
  - site_name: "Paris-HQ"
    address: "1 Rue de la Paix"
    city: "Paris"
    state_region: "Ile-de-France"
    country: "France"
    zip_code: "75001"
    latitude: 48.8698
    longitude: 2.3309
    timezone: "Europe/Paris"

  - site_name: "Lyon-Branch"
    address: "10 Place Bellecour"
    city: "Lyon"
    state_region: "Rhone-Alpes"
    country: "France"
    zip_code: "69002"
    latitude: 45.7579
    longitude: 4.832
    timezone: "Europe/Paris"
```

| Field | Required | Description |
|-------|----------|-------------|
| `site_name` | Yes | Unique site name — must match `site` in `devices.yml` |
| `address` | Yes | Street address |
| `city` | Yes | City name |
| `state_region` | Yes | State or region (no spaces) |
| `country` | Yes | Country name |
| `zip_code` | Yes | Postal code (wrap in quotes) |
| `latitude` | No | GPS latitude |
| `longitude` | No | GPS longitude |
| `timezone` | Yes | IANA timezone (e.g. `Europe/Paris`, `America/Chicago`) |

---

### `device_groups.yml` — Device Groups

```yaml
# Groups to create (Central with AOS-CX and AOS 10 architecture)
device_groups:
  - name: "Ansible_Onboarding"
    allowed_dev_types: ["AccessPoints", "Gateways", "Switches"]
    allowed_switch_types: ["AOS_CX"]
    architecture: "AOS10"
    ap_network_role: "Standard"
    gw_network_role: "WLANGateway"
    template_wired: false
    template_wireless: false
    new_central: true
```

---

## Playbooks

### `full_onboarding.yml`

Complete device onboarding — GLP + Classic Central + New Central. No tags — always runs all steps from start to finish. Use `-e serials=...` to target specific devices.

```bash
# All devices
ansible-playbook full_onboarding.yml

# Single device
ansible-playbook full_onboarding.yml -e serials=SG03KW500G

# Multiple devices
ansible-playbook full_onboarding.yml -e "serials=SG03KW500G,SG3ALN0004"
```

---

### `glp_management.yml`

GLP post-onboarding operations. All operations target devices already in the GLP workspace.

| Tag | Description | Filter |
|-----|-------------|--------|
| `glp_tags` | Apply/update GLP tags | `-e serials=...` optional |
| `glp_assign_app` | Assign Central application | `-e serials=...` optional |
| `glp_assign_sub` | Assign subscription | `-e serials=...` optional |
| `glp_unassign_app` | Unassign Central application | **`-e serials=...` required** |
| `glp_unassign_sub` | Unassign subscription | **`-e serials=...` required** |

```bash
# Apply tags to all devices (devices must have glp.tags defined in devices.yml)
ansible-playbook glp_management.yml --tags glp_tags

# Apply tags to a specific device
ansible-playbook glp_management.yml --tags glp_tags -e serials=SG03KW500G

# Assign application to all devices
ansible-playbook glp_management.yml --tags glp_assign_app

# Assign application to specific devices
ansible-playbook glp_management.yml --tags glp_assign_app -e serials=SG03KW500G
ansible-playbook glp_management.yml --tags glp_assign_app -e "serials=SG03KW500G,CNQBLPQ0FF"

# Unassign application (serials required)
ansible-playbook glp_management.yml --tags glp_unassign_app -e serials=SG03KW500G
ansible-playbook glp_management.yml --tags glp_unassign_app -e "serials=SG03KW500G,SG3ALN0004,CNQBLPQ0FF"

# Assign subscription to all devices
ansible-playbook glp_management.yml --tags glp_assign_sub

# Assign subscription to specific devices
ansible-playbook glp_management.yml --tags glp_assign_sub -e serials=SG03KW500G

# Unassign subscription (serials required)
# Note: the Central application must be assigned before unassigning the subscription
ansible-playbook glp_management.yml --tags glp_unassign_sub -e serials=SG03KW500G
ansible-playbook glp_management.yml --tags glp_unassign_sub -e "serials=SG03KW500G,CNQBLPQ0FF"
```

---

### `site_management.yml`

Site lifecycle management in Aruba Central. Does **not** handle device-to-site associations (use `device_site_assignment.yml` for that).

> ⚠️ A site cannot be deleted if it still contains devices. Use `device_site_assignment.yml --tags unassign_site` first.

| Tag | Description | Filter |
|-----|-------------|--------|
| `create_site` | Create sites (idempotent) | `-e site_names=...` optional |
| `update_site` | Update site details | **`-e site_names=...` required** |
| `delete_site` | Delete sites | **`-e site_names=...` required** |

```bash
# Create all sites (idempotent)
ansible-playbook site_management.yml --tags create_site

# Create a single site
ansible-playbook site_management.yml --tags create_site -e site_names=Paris-HQ

# Update site details
ansible-playbook site_management.yml --tags update_site -e site_names=Paris-HQ

# Update multiple sites
ansible-playbook site_management.yml --tags update_site -e "site_names=Paris-HQ,Lyon-Branch"

# Delete a site (devices must be unassigned first)
ansible-playbook device_site_assignment.yml --tags unassign_site -e "serials=SG03KW500G,SG3ALN0004"
ansible-playbook site_management.yml --tags delete_site -e site_names=Lyon-Branch

# Delete multiple sites
ansible-playbook site_management.yml --tags delete_site -e "site_names=Paris-HQ,Lyon-Branch"
```

---

### `device_site_assignment.yml`

Device-to-site associations in Classic Central.

| Tag | Description | Filter |
|-----|-------------|--------|
| `assign_site` | Associate devices to their site | `-e serials=...` optional |
| `unassign_site` | Remove devices from their site | **`-e serials=...` required** |

```bash
# Associate all devices to their site
ansible-playbook device_site_assignment.yml --tags assign_site

# Associate specific devices
ansible-playbook device_site_assignment.yml --tags assign_site -e serials=SG03KW500G
ansible-playbook device_site_assignment.yml --tags assign_site -e "serials=SG03KW500G,SG3ALN0004"

# Remove a device from its site
ansible-playbook device_site_assignment.yml --tags unassign_site -e serials=SG03KW500G

# Remove multiple devices from their site
ansible-playbook device_site_assignment.yml --tags unassign_site -e "serials=SG03KW500G,SG3ALN0004,CNQBLPQ0FF"
```

---

### `device_persona_management.yml`

Device persona assignment via New Central API. No Classic Central involved — no rate limit concern.

| Tag | Description | Filter |
|-----|-------------|--------|
| `assign_persona` | Assign persona to devices | `-e serials=...` optional |

```bash
# Assign persona to all devices
ansible-playbook device_persona_management.yml --tags assign_persona

# Assign persona to specific devices
ansible-playbook device_persona_management.yml --tags assign_persona -e serials=CNQBLPQ0FF
```

---

### `device_group_management.yml`

Device group lifecycle management in Classic Central. Does **not** handle device-to-group assignments (use `device_group_assignment.yml` for that).

> ⚠️ A group cannot be deleted if it still contains devices. Use `device_group_assignment.yml --tags unassign_group` first to move devices back to the `default` group.

| Tag | Description | Filter |
|-----|-------------|--------|
| `create_group` | Create groups (idempotent) | `-e target_group_names=...` optional |
| `update_group` | Update group properties | **`-e target_group_names=...` required** |
| `delete_group` | Delete groups | **`-e target_group_names=...` required** |

```bash
# Create all groups (idempotent)
ansible-playbook device_group_management.yml --tags create_group

# Create a single group
ansible-playbook device_group_management.yml --tags create_group -e target_group_names=Ansible_Onboarding

# Update group properties
ansible-playbook device_group_management.yml --tags update_group -e target_group_names=Ansible_Onboarding

# Delete a group (devices must be moved out first)
ansible-playbook device_group_assignment.yml --tags unassign_group -e "serials=SG03KW500G,SG3ALN0004,CNQBLPQ0FF"
ansible-playbook device_group_management.yml --tags delete_group -e target_group_names=Ansible_Onboarding

# Delete multiple groups
ansible-playbook device_group_management.yml --tags delete_group -e "target_group_names=Group1,Group2"
```

---

### `device_group_assignment.yml`

Device-to-group assignments in Classic Central.

| Tag | Description | Filter |
|-----|-------------|--------|
| `assign_group` | Move devices to their group | `-e serials=...` optional |
| `unassign_group` | Move devices back to default group | **`-e serials=...` required** |

```bash
# Move all devices to their group
ansible-playbook device_group_assignment.yml --tags assign_group

# Move specific devices
ansible-playbook device_group_assignment.yml --tags assign_group -e serials=SG03KW500G

# Move devices back to default group
ansible-playbook device_group_assignment.yml --tags unassign_group -e serials=SG03KW500G
```

---

## Safety Guards

Potentially destructive operations are protected by a two-layer mechanism:

**1. `never` tag** — these tasks never run during a normal playbook execution. They must be called explicitly with `--tags`.

**2. Mandatory filter** — a filter (`serials`, `site_names`, or `target_group_names`) must be passed via `-e`. Without it, the playbook stops before taking any action.

| Operation | Playbook | Required filter |
|-----------|----------|----------------|
| `glp_unassign_app` | `glp_management.yml` | `-e serials=...` |
| `glp_unassign_sub` | `glp_management.yml` | `-e serials=...` |
| `update_site` | `site_management.yml` | `-e site_names=...` |
| `delete_site` | `site_management.yml` | `-e site_names=...` |
| `unassign_site` | `device_site_assignment.yml` | `-e serials=...` |
| `update_group` | `device_group_management.yml` | `-e target_group_names=...` |
| `delete_group` | `device_group_management.yml` | `-e target_group_names=...` |
| `unassign_group` | `device_group_assignment.yml` | `-e serials=...` |

---

## Onboarding Workflow

```
Input validation
      ↓
Phase 1 — GLP
  ├─ Check if device exists in GLP workspace
  ├─ Add device if missing
  ├─ Assign device to HPE Aruba Networking Central application
  └─ Apply subscription license

Phase 2 — Classic Central
  ├─ Create site if it does not exist (idempotent)
  ├─ Associate device to site
  ├─ Create device group if it does not exist (idempotent)
  └─ Move device to group

Phase 3 — New Central
  └─ Assign device persona

Summary
```

---

## Technical Architecture

### Authentication

| Component | Method | Notes |
|-----------|--------|-------|
| GLP / New Central | OAuth2 Client Credentials | `POST /as/token.oauth2` — token valid for 2h |
| Classic Central | Single-use refresh token | Fallback to username/password if expired |

**Classic Central token flow:**

The refresh token is **single-use** — each API call consumes it and returns a new one. The collection handles this automatically:

1. At playbook start, the token is loaded from `/tmp/.central_refresh_token` if it exists (more recent than vault), otherwise from `vault.yml`
2. The first Classic Central call authenticates and writes the new token to `/tmp/.central_refresh_token`
3. All subsequent calls in the same run use the file token
4. At the end of the run, `vault.yml` is updated with the latest token

This ensures only **one login call per playbook run**, regardless of how many Classic Central operations are performed.

### Custom Modules

| Module | API endpoint | Supported states |
|--------|-------------|-----------------|
| `glp_device` | `GET/POST/PATCH /devices/v1/devices` | `query`, `present`, `absent` |
| `glp_application` | `GET/PATCH /devices/v1/devices/{id}` | `query`, `present`, `absent` |
| `glp_license` | `GET/PATCH /devices/v1/devices/{id}` | `query`, `present`, `absent` |
| `central_site` | `GET/POST/PUT/DELETE /platform/device_inventory/v1/sites` | `query`, `present`, `update`, `absent` |
| `central_site_devices` | `GET/POST/DELETE /central/v2/sites/associations` | `query`, `present`, `absent` |
| `central_device_persona` | `GET/POST /device-management/v1/devices/persona` | `query`, `present` |
| `central_device_group` | `GET/POST/PATCH/DELETE /configuration/v2/groups` | `query`, `present`, `update`, `absent`, `move` |

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `Classic Central Step 1 rate limited — retry in X seconds` | Too many login attempts in 30 min | Wait ~30 min. Verify token: `curl -s -X POST "https://eu-apigw.central.arubanetworks.com/oauth2/token" -d "grant_type=refresh_token" -d "client_id=..." -d "client_secret=..." -d "refresh_token=$(cat /tmp/.central_refresh_token)"` |
| `refresh token invalid (HTTP 400)` | Token in `vault.yml` is outdated | Sync: `TOKEN=$(cat /tmp/.central_refresh_token) && sed -i "s/classic_central_refresh_token:.*/classic_central_refresh_token: \"$TOKEN\"/" ~/playbooks/vault.yml` |
| `PAGE_LIMIT_SIZE_EXCEEDED` | `limit` parameter too high | The playbook uses `limit: 100` — do not override |
| `HTTP 400 on GLP device add` | Device already archived in GLP | Unarchive manually in the GLP portal |
| `YAML syntax error` | Malformed input file | Run `ansible-playbook full_onboarding.yml --syntax-check` |
| Device not appearing in Central | Device cannot reach Central | Verify network connectivity and factory-reset status |
| `glp_unassign_sub` fails with `FAILED` status | Application must be assigned before unassigning subscription | Run `glp_assign_app` first, then retry `glp_unassign_sub` |
| `SITE_ERR_MAX_NO_ALREADY_ASSIGNED` in assign_site | Device already associated to this site | Normal — treated as idempotent, no action needed |
| `SITE_ERR_DELETE_ASSOCIATION` in unassign_site | Device already removed from site | Normal — treated as idempotent, no action needed |

### Useful references

- [Central API Gateway Base URLs](https://developer.arubanetworks.com/new-central/docs/getting-started-with-rest-apis#api-gateway-base-urls)
- [How to get API credentials for Central](https://developer.arubanetworks.com/new-central/docs/generating-and-managing-access-tokens)
- [How to get API credentials for GLP](https://developer.greenlake.hpe.com/docs/greenlake/guides/public/authentication/authentication#creating-a-personal-api-client)
- [Classic Central API OAuth token](https://developer.arubanetworks.com/central/docs/api-oauth-access-token)
- [HPE Aruba Networking Central onboarding workflow (official)](https://developer.arubanetworks.com/new-central/docs/onboarding)
- [IANA timezone list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)