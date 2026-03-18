import argparse, csv, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-csv", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--max-clips", type=int, default=12)
    ap.add_argument("--duration", type=int, default=6)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    args = ap.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    # Placeholder: no real rendering

if __name__ == "__main__":
    main()
