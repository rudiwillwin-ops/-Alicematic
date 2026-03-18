import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--max-clips", type=int, default=3)
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--resolution", default="720p")
    ap.add_argument("--stitch-every", type=int, default=3)
    args = ap.parse_args()
    _ = args

if __name__ == "__main__":
    main()
