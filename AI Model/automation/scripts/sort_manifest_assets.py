import argparse, json, os, shutil

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dest-root", required=True)
    ap.add_argument("--persona-id", required=True)
    ap.add_argument("--mode", default="copy")
    args = ap.parse_args()
    os.makedirs(args.dest_root, exist_ok=True)
    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assets = manifest.get("assets", [])
    persona_dir = os.path.join(args.dest_root, args.persona_id)
    os.makedirs(persona_dir, exist_ok=True)
    for asset in assets:
        src = asset.get("file_path")
        if not src or not os.path.exists(src):
            continue
        dst = os.path.join(persona_dir, os.path.basename(src))
        if args.mode == "move":
            shutil.move(src, dst)
        else:
            shutil.copy2(src, dst)

if __name__ == "__main__":
    main()
