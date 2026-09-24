import json
import subprocess
import time

from urllib.parse import quote

from config import XUI_HOST, XUI_API_TOKEN

INBOUND_IDS = [8, 20, 30, 31]

def _request(method, path, data=None):
    url = f"{XUI_HOST}{path}"

    command = [
    "curl",
    "-ksS",
    "--http1.1",
    "--max-time", "15",
    "-X", method,
    "-H", f"Authorization: Bearer {XUI_API_TOKEN}",
    "-H", "Accept: application/json",
]
    if data is not None:
        command.extend([
            "-H", "Content-Type: application/json",
            "--data", json.dumps(data),
        ])

    command.append(url)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=20,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"3x-ui API curl failed: {result.stderr.strip()}"
        )

    if not result.stdout:
        raise RuntimeError("3x-ui API returned empty response")

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"invalid JSON from 3x-ui: {result.stdout[:500]}"
        ) from e

    if not response.get("success"):
        raise RuntimeError(
            response.get("msg") or "3x-ui API request failed"
        )

    return response

def get_client(email=None, tg_id=None):
    if email is not None:
        result = _request(
            "GET",
            f"/panel/api/clients/get/{quote(email, safe='')}",
        )

        return result.get("obj")

    if tg_id is not None:
        result = _request(
            "GET",
            f"/panel/api/clients/get/tgId/{tg_id}",
        )

        clients = result.get("obj") or []

        return clients[0] if clients else None

    raise ValueError("email or tg_id is required")


def get_traffic(email):
    result = _request(
        "GET",
        f"/panel/api/clients/traffic/{quote(email, safe='')}",
    )

    return result.get("obj")


def get_inbounds():
    result = _request(
        "GET",
        "/panel/api/inbounds/list",
    )

    return result.get("obj") or []


def get_subscription_url(sub_id, json_mode=False):
    if not sub_id:
        raise ValueError("sub_id is empty")

    path = "/jsnn/" if json_mode else "/s/"

    return f"https://87.121.82.175:2096{path}{sub_id}"

def find_client(email):
    inbounds = get_inbounds()

    for inbound in inbounds:
        settings = inbound.get("settings", {})
        clients = settings.get("clients", [])

        for client in clients:
            if client.get("email") == email:
                return client

    return None

def find_client_by_sub_id(sub_id):
    inbounds = get_inbounds()

    for inbound in inbounds:
        settings = inbound.get("settings", {})
        clients = settings.get("clients", [])

        for client in clients:
            if client.get("subId") == sub_id:
                return client

    return None

def create_client(
    tg_id,
    email,
    expiry_hours=12,
    total_gb=0,
    group="trial",
):
    now = int(time.time() * 1000)

    expiry_time = now + (
        expiry_hours * 60 * 60 * 1000
    )

    payload = {
        "client": {
            "email": email,
            "enable": True,
            "expiryTime": expiry_time,
            "totalGB": total_gb,
            "tgId": tg_id,
            "limitHwid": 1,
            "limitIp": 0,
            "reset": 0,
            "resetDay": 0,
            "resetMax": 0,
            "trafficReset": "never",
            "trafficResetDay": 1,
            "flow": "xtls-rprx-vision",
            "security": "auto",
            "comment": "",
            "group": group,
        },
        "inboundIds": INBOUND_IDS,
    }

    result = _request(
        "POST",
        "/panel/api/clients/add",
        payload,
    )

    client = find_client(email)

    if not client:
        raise RuntimeError(
            f"client {email} was created but not found"
        )

    sub_id = client.get("subId")

    if not sub_id:
        raise RuntimeError(
            f"client {email} has no subId"
        )

    return {
        "email": email,
        "tg_id": tg_id,
        "expiry_time": expiry_time,
        "inbound_ids": INBOUND_IDS,
        "group": group,
        "flow": "xtls-rprx-vision",
        "sub_id": sub_id,
        "subscription_url": get_subscription_url(
           sub_id,
           json_mode=True,
        ),
        "api_result": result,
    }

def disable_client(email):
    client = get_client(email=email)

    if not client:
        return False

    client_data = client.get("client", client)

    payload = {
        "email": client_data.get("email", email),
        "subId": client_data.get("subId"),
        "id": client_data.get("uuid") or client_data.get("id"),
        "password": client_data.get("password"),
        "auth": client_data.get("auth"),
        "flow": client_data.get("flow") or "",
        "security": client_data.get("security") or "auto",
        "totalGB": client_data.get("totalGB", 0),
        "expiryTime": client_data.get("expiryTime", 0),
        "limitIp": client_data.get("limitIp", 0),
        "limitHwid": 3,
        "tgId": client_data.get("tgId", 0),
        "reset": client_data.get("reset", 0),
        "resetDay": client_data.get("resetDay", 0),
        "resetMax": client_data.get("resetMax", 0),
        "trafficReset": client_data.get(
            "trafficReset",
            "never",
        ),
        "trafficResetDay": client_data.get(
            "trafficResetDay",
            1,
        ),
        "group": client_data.get("group") or "",
        "comment": client_data.get("comment") or "",
        "enable": False,
    }

    _request(
        "POST",
        f"/panel/api/clients/update/{quote(email, safe='')}",
        payload,
    )

    return True


def get_client_summary(email=None, tg_id=None):
    client = get_client(
        email=email,
        tg_id=tg_id,
    )

    if not client:
        return None

    client_data = client.get("client", client)

    client_email = client_data.get("email")
    sub_id = client_data.get("subId")

    return {
        "id": client_data.get("id"),
        "email": client_email,
        "tg_id": client_data.get("tgId"),
        "uuid": client_data.get("uuid")
            or client_data.get("id"),
        "sub_id": sub_id,
        "expiry_time": client_data.get("expiryTime"),
        "enable": bool(client_data.get("enable")),
        "total_gb": client_data.get("totalGB", 0),
        "traffic": get_traffic(client_email),
        "inbound_ids": client.get(
            "inboundIds",
            [],
        ),
        "subscription_url": get_subscription_url(
            sub_id
        ),
        "json_url": get_subscription_url(
            sub_id,
            json_mode=True,
        ),
    }

def get_hwid_devices(email):
    result = _request(
        "POST",
        f"/panel/api/clients/hwids/{quote(email, safe='')}",
    )

    return result.get("obj") or []


def delete_all_hwid_devices(email):
    _request(
        "DELETE",
        f"/panel/api/clients/hwids/{quote(email, safe='')}",
    )

    return True
def renew_client_by_sub_id(sub_id, days=30):
    client = find_client_by_sub_id(sub_id)

    if not client:
        raise RuntimeError("subscription not found")

    email = client.get("email")

    if not email:
        raise RuntimeError("client email not found")

    client_data = client.get("client", client)

    # paid payment = exactly N full days from the moment of payment.
    expiry_time = int(time.time() * 1000) + (
        days * 24 * 60 * 60 * 1000
    )

    payload = {
        "email": client_data.get("email", email),
        "subId": client_data.get("subId"),
        "id": client_data.get("uuid") or client_data.get("id"),
        "password": client_data.get("password"),
        "auth": client_data.get("auth"),
        "flow": client_data.get("flow") or "",
        "security": client_data.get("security") or "auto",
        "totalGB": client_data.get("totalGB", 0),
        "expiryTime": expiry_time,
        "limitIp": client_data.get("limitIp", 0),
        "limitHwid": client_data.get("limitHwid", 0),
        "tgId": client_data.get("tgId", 0),
        "reset": client_data.get("reset", 0),
        "resetDay": client_data.get("resetDay", 0),
        "resetMax": client_data.get("resetMax", 0),
        "trafficReset": client_data.get("trafficReset", "never"),
        "trafficResetDay": client_data.get("trafficResetDay", 1),
        "group": client_data.get("group") or "paid",
        "comment": client_data.get("comment") or "",
        "enable": True,
    }

    _request(
        "POST",
        f"/panel/api/clients/update/{quote(email, safe='')}",
        payload,
    )

    updated = find_client(email)

    if not updated:
        raise RuntimeError("client disappeared after renewal")

    return updated

def ban_client_by_sub_id(sub_id):
    client = find_client_by_sub_id(sub_id)

    if not client:
        raise RuntimeError("subscription not found")

    email = client.get("email")

    if not email:
        raise RuntimeError("client email not found")

    _request(
        "POST",
        "/panel/api/clients/bulkDisable",
        {"emails": [email]},
    )

    return True
