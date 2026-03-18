import argparse, json, os, time

from _leonardo import load_env, leonardo_request, extract_generation_id, list_platform_models, extract_platform_models

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona-file", required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--providers", default="")
    ap.add_argument("--max-scenes", type=int, default=0)
    ap.add_argument("--model-id", default="")
    ap.add_argument("--auto-model", action="store_true")
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--prompt", default="")
    args = ap.parse_args()

    with open(args.persona_file, "r", encoding="utf-8") as f:
        persona = json.load(f)

    out_root = os.path.join("automation", "out")
    os.makedirs(out_root, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(out_root, f"DRYRUN-{stamp}") if not args.execute else os.path.join(out_root, f"RUN-{stamp}")
    os.makedirs(run_dir, exist_ok=True)

    plan = {
        "mode": "execute" if args.execute else "dry-run",
        "persona_file": args.persona_file,
        "persona_id": persona.get("id", "unknown"),
        "providers": args.providers,
        "max_scenes": args.max_scenes,
        "notes": "No API calls in dry-run."
    }

    with open(os.path.join(run_dir, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    if args.execute:
        providers = [p.strip().lower() for p in args.providers.split(",") if p.strip()] or ["leonardo"]
        if "leonardo" not in providers:
            raise SystemExit("Only leonardo provider is implemented.")

        env = load_env(os.path.join("automation", ".env"))
        api_key = env.get("LEONARDO_API_KEY", "")
        if not api_key:
            raise SystemExit("LEONARDO_API_KEY missing in automation/.env")

        model_id = args.model_id or persona.get("model_id") or env.get("LEONARDO_MODEL_ID", "")
        if not model_id:
            status, models_data = list_platform_models(api_key)
            with open(os.path.join(run_dir, "platform_models.json"), "w", encoding="utf-8") as f:
                json.dump({"status": status, "data": models_data}, f, indent=2)
            models = extract_platform_models(models_data)
            if args.auto_model and models:
                model_id = models[0].get("id", "")
            if not model_id:
                raise SystemExit("Model ID missing. Check platform_models.json or set LEONARDO_MODEL_ID/--model-id.")

        base_prompt = args.prompt or persona.get("prompt") or "Studio portrait of an adult 21+ synthetic woman, natural light, high detail, compliant."
        scenes = persona.get("scenes")
        if not scenes:
            scenes = [{"prompt": base_prompt, "width": args.width, "height": args.height}]

        max_scenes = args.max_scenes or len(scenes)
        responses = []
        for idx, scene in enumerate(scenes[:max_scenes], start=1):
            prompt = scene.get("prompt") or base_prompt
            width = int(scene.get("width") or args.width)
            height = int(scene.get("height") or args.height)
            payload = {
                "prompt": prompt,
                "modelId": model_id,
                "width": width,
                "height": height,
            }
            status, data = leonardo_request("POST", "/generations", api_key, body=payload)
            responses.append({
                "scene_index": idx,
                "request": payload,
                "status_code": status,
                "response": data,
                "generation_id": extract_generation_id(data),
            })

        with open(os.path.join(run_dir, "leonardo_responses.json"), "w", encoding="utf-8") as f:
            json.dump({"responses": responses}, f, indent=2)

if __name__ == "__main__":
    main()
