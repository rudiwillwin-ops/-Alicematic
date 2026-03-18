import json
import os
import time
import urllib.error
import urllib.request

BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"


def load_env(env_path):
    env = {}
    if not os.path.exists(env_path):
        return env
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def leonardo_request(method, path, api_key, body=None, timeout=60):
    url = BASE_URL + path
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}",
    }
    data = None
    if body is not None:
        headers["content-type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw}
        return e.code, payload


def poll_generation(api_key, generation_id, timeout=300, interval=5):
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        status_code, data = leonardo_request("GET", f"/generations/{generation_id}", api_key)
        last = data
        if status_code >= 400:
            return status_code, data
        status = extract_status(data)
        if status and status.upper() not in ("PENDING", "IN_PROGRESS", "QUEUED"):
            return status_code, data
        time.sleep(interval)
    return 200, last


def extract_status(obj):
    if isinstance(obj, dict):
        if "status" in obj and isinstance(obj["status"], str):
            return obj["status"]
        for v in obj.values():
            s = extract_status(v)
            if s:
                return s
    elif isinstance(obj, list):
        for item in obj:
            s = extract_status(item)
            if s:
                return s
    return None


def extract_generation_id(obj):
    if isinstance(obj, dict):
        for key in ("generationId", "generation_id", "id"):
            if key in obj and isinstance(obj[key], str):
                return obj[key]
        for v in obj.values():
            gid = extract_generation_id(v)
            if gid:
                return gid
    elif isinstance(obj, list):
        for item in obj:
            gid = extract_generation_id(item)
            if gid:
                return gid
    return None


def extract_image_urls(obj):
    urls = []
    if isinstance(obj, dict):
        if "generated_images" in obj and isinstance(obj["generated_images"], list):
            for gi in obj["generated_images"]:
                url = gi.get("url") if isinstance(gi, dict) else None
                if url:
                    urls.append(url)
        if "generatedImages" in obj and isinstance(obj["generatedImages"], list):
            for gi in obj["generatedImages"]:
                url = gi.get("url") if isinstance(gi, dict) else None
                if url:
                    urls.append(url)
        if "images" in obj and isinstance(obj["images"], list):
            for gi in obj["images"]:
                url = gi.get("url") if isinstance(gi, dict) else None
                if url:
                    urls.append(url)
        for v in obj.values():
            urls.extend(extract_image_urls(v))
    elif isinstance(obj, list):
        for item in obj:
            urls.extend(extract_image_urls(item))
    return list(dict.fromkeys(urls))


def extract_platform_models(obj):
    models = []
    if isinstance(obj, dict):
        for key in ("platformModels", "platform_models", "models"):
            if key in obj and isinstance(obj[key], list):
                for m in obj[key]:
                    if isinstance(m, dict) and m.get("id"):
                        models.append(m)
        for v in obj.values():
            models.extend(extract_platform_models(v))
    elif isinstance(obj, list):
        for item in obj:
            models.extend(extract_platform_models(item))
    # Deduplicate by id
    seen = set()
    uniq = []
    for m in models:
        mid = m.get("id")
        if mid and mid not in seen:
            seen.add(mid)
            uniq.append(m)
    return uniq


def list_platform_models(api_key):
    status, data = leonardo_request("GET", "/platformModels", api_key)
    return status, data
