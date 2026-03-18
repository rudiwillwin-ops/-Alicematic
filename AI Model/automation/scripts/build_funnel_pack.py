import argparse, csv, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", required=True)
    ap.add_argument("--videos-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    queue = os.path.join(args.out_dir, "MIA_VIDEO_CLIP_QUEUE.csv")
    with open(queue, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["clip_id", "source_path", "type", "duration", "notes"])
    print(queue)

if __name__ == "__main__":
    main()
