#!/usr/bin/env python3
"""Ask the local Athena service; display its retrieved sources with the answer."""
import argparse
import json
import sys
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="+")
    args = parser.parse_args()
    request = urllib.request.Request("http://127.0.0.1:8001/query",
        data=json.dumps({"question": " ".join(args.question), "top_k": 4}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            result = json.load(response)
    except (OSError, urllib.error.HTTPError, ValueError) as error:
        print(f"Local Athena request failed: {error}", file=sys.stderr)
        return 1
    print(result.get("answer", "No answer returned"))
    print("\nRetrieved sources:")
    for source in result.get("sources", []):
        print("- " + source)
    print("\nModel answer is unverified. Review the sources before taking action.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
