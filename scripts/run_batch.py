import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loop import run_batch


def main():
    parser = argparse.ArgumentParser(description="Run QoneqtReel Batch Pipeline")
    parser.add_argument("topics_file", help="Path to text file containing topics (one per line)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay in seconds between jobs")
    args = parser.parse_args()

    file_path = Path(args.topics_file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    topics = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not topics:
        print("Error: No valid topics found in file.")
        sys.exit(1)

    print(f"Loaded {len(topics)} topics from {file_path}")
    summary = run_batch(topics, delay_sec=args.delay)
    print(f"\nCompleted! Pass Rate: {summary['pass_rate_percent']}%")
    print("Reports generated: batch_report.json and batch_report.md")


if __name__ == "__main__":
    main()
