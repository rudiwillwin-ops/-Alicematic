import argparse, json, os, urllib.request

from _leonardo import load_env, leonardo_request, poll_generation, extract_image_urls

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    env = load_env(os.path.join("automation", ".env"))
    api_key = env.get("LEONARDO_API_KEY", "")
    if not api_key:
        raise SystemExit("LEONARDO_API_KEY missing in automation/.env")

    with open(args.responses, "r", encoding="utf-8") as f:
        data = json.load(f)

    responses = data.get("responses", [])
    assets = []

    for item in responses:
        generation_id = item.get("generation_id")
        detail = item.get("response", {})
        if generation_id:
            _, detail = poll_generation(api_key, generation_id, timeout=900, interval=8)
        urls = extract_image_urls(detail)
        for i, url in enumerate(urls, start=1):
            ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
            filename = f"{generation_id or 'generation'}_{i}{ext}"
            out_path = os.path.join(args.out_dir, filename)
            try:
                urllib.request.urlretrieve(url, out_path)
            except Exception:
                continue
            assets.append({
                "generation_id": generation_id,
                "index": i,
                "url": url,
                "file_path": out_path,
                "nsfw_flag": None,
            })

    manifest = {"assets": assets}
    with open(os.path.join(args.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

if __name__ == "__main__":
    main()
