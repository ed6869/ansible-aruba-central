# Ansible Playbook - HPE GreenLake Device Onboarding

This playbook automates device onboarding to the **HPE GreenLake Cloud Platform (GLP)** and **HPE Aruba Networking Central**.

It covers the following steps:
1. Adding devices to the GLP workspace
2. Assigning devices to the HPE Aruba Networking Central application
3. Applying subscriptions to devices

---

## Prerequisites

- Ansible Core 2.15+
- Python 3.9+
- Network access to:
  - `sso.common.cloud.hpe.com` (authentication)
  - `global.api.greenlake.hpe.com` (GLP API)
- An HPE GreenLake API client with the following permissions:
  - Devices: Read / Write
  - Subscriptions: Read
  - Service catalog: Read

> To create an API client, follow the [HPE Aruba Networking Developer Hub guide](https://developer.arubanetworks.com).

---

## Repository structure

```
aruba_central/
├── playbooks/
│   ├── onboarding.yml        # Main playbook - do not edit
│   ├── devices.yml           # List of devices to onboard - edit this
│   ├── vault.yml             # Your credentials (not committed)
│   └── vault.yml.example     # Credentials template
├── .gitignore
└── README.md
```

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd aruba_central/playbooks
```

### 2. Configure credentials

```bash
cp vault.yml.example vault.yml
```

Edit `vault.yml` with your GLP API credentials:

```yaml
glp_client_id: "your-client-id"
glp_client_secret: "your-client-secret"
glp_central_sm_id: "your-service-manager-id"
```

| Variable | Description | Where to find it |
|---|---|---|
| `glp_client_id` | GLP API client ID | GLP portal → Manage → API clients |
| `glp_client_secret` | GLP API client secret | GLP portal → Manage → API clients |
| `glp_central_sm_id` | HPE Aruba Networking Central application ID | GLP portal → Workspace → Services → click on "HPE Aruba Networking Central" → ID is in the URL |

> **Security:** Optionally encrypt your vault file with `ansible-vault encrypt vault.yml`. Run the playbook with `--ask-vault-pass` in that case.

---

### 3. Fill in devices to onboard

Edit `devices.yml` — add one block per device:

```yaml
devices:
  - serial_number: SGxxxxxxx
    mac_address: xx:xx:xx:xx:xx:xx
    device_type: SWITCH
    persona: Access Switch
    device_group: My_Group
    site: My_Site
    glp:
      region: eu-central
      subscription_key: Exxxxxxxxx
```

---

## Input File Breakdown

### Devices (required)

Add one entry per device under the `devices` block.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `serial_number` | string | Yes | Device serial number |
| `mac_address` | string | Yes | Device MAC address |
| `device_type` | enum | Yes | `SWITCH`, `AP` or `GATEWAY` |
| `persona` | string | Yes | Device role — see Persona Options below |
| `device_group` | string | Yes | Target configuration group in Central |
| `site` | string | Yes | Site assignment in Central |
| `glp.region` | string | Yes | GLP deployment region — see supported regions below |
| `glp.subscription_key` | string | Yes | Subscription key from GLP portal |

**Where to find the Serial Number and MAC Address:**

| Device type | Physical location | CLI command |
|---|---|---|
| Access Points | Bottom of the device | `show inventory` |
| AOS-CX Switch | Pull-out tab on the device | `show system` |
| Gateways | Back of the device | `show inventory` |

**Where to find the `subscription_key`:**  
GLP portal → **Subscriptions** → copy the **Key** column value for the subscription matching the device model.

---

### Persona Options by Device Type

| `device_type` | `persona` |
|---|---|
| `AP` | `Campus AP` |
| `SWITCH` | `Access Switch` |
| `SWITCH` | `Core Switch` |
| `SWITCH` | `Aggregation Switch` |
| `GATEWAY` | `Mobility Gateway` |

---

### Sites (optional)

Only required if the site does not already exist in Central. If the site already exists, you may omit this block.

Add site entries under the `sites` block in `devices.yml`:

```yaml
sites:
  - name: My_Site
    address: "1 rue de la Paix"
    city: Paris
    state: Ile-de-France
    country: France
    zipcode: "75001"
    timezone: Europe/Paris
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Unique site name — must match the `site` value in the device entry |
| `address` | string | Yes | Street address |
| `city` | string | Yes | City name |
| `state` | string | Yes | State or region |
| `country` | string | Yes | Country name or ISO code |
| `zipcode` | string | Yes | Postal code — wrap in quotes |
| `timezone` | string | Yes | Timezone identifier (e.g., `Europe/Paris`, `America/Chicago`) |

---

### Device Groups (optional)

Only required if the device group does not already exist in Central. If the group already exists, you may omit this block.

Add device group entries under the `device_groups` block in `devices.yml`:

```yaml
device_groups:
  - name: My_Group
    device_type: SWITCH
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Group name — must match the `device_group` value in the device entry |
| `device_type` | string | Yes | Device type for this group: `SWITCH`, `AP` or `GATEWAY` |

---

## Usage

### Run the playbook

```bash
ansible-playbook onboarding.yml
```

If vault is encrypted:

```bash
ansible-playbook onboarding.yml --ask-vault-pass
```

### Check syntax without running

```bash
ansible-playbook onboarding.yml --syntax-check
```

---

## Onboarding workflow

The playbook executes the following sequence for each device:

```
1. Check if device exists in GLP workspace
        ↓ (add if missing)
2. Retrieve device UUID from serial number
        ↓
3. Assign device to HPE Aruba Networking Central application  [async]
        ↓ (wait for SUCCEEDED)
4. Retrieve subscription ID from subscription key
        ↓
5. Apply subscription to device  [async]
        ↓ (wait for SUCCEEDED)
6. Summary
```

> All asynchronous operations are polled until `SUCCEEDED` or `FAILED` (max 10 retries, 5s delay).

---

## Reference

### Supported regions

| Region |
|---|
| `eu-central` |
| `us-west` |
| `us-east` |
| `ap-northeast` |
| `ap-southeast` |

---

## Notes

- The playbook is **idempotent** for device existence: if a device is already present in the GLP workspace, it will not be added again.
- Application and subscription assignments are always re-applied on each run. GLP handles duplicates gracefully.
- The GLP access token is valid for **2 hours**. For long runs with many devices, the playbook may need to be updated to refresh the token automatically.

---

## Disclaimer

This playbook is a **community project** and is **not developed, maintained or supported by HPE**.  
It is provided as-is, without any warranty or guarantee of any kind.

For questions or improvements, please open an issue or a pull request in this repository.