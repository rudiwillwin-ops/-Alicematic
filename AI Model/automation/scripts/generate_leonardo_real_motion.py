import argparse, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-clips", type=int, default=3)
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--stitch-every", type=int, default=3)
    ap.add_argument("--poll-interval", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

if __name__ == "__main__":
    main()
