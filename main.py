import argparse
import json
from typing import Any, Dict

from app.agent import Agent


def pretty_print(payload: Dict[str, Any]) -> None:
    if "message" in payload:
        print("\n[message]")
        print(payload["message"])
    if "result" in payload:
        result = payload["result"]
        if "error" in result:
            print(f"\n[error] {result['error']}")
        else:
            print("\n[result]")
            print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Resilient multi-tool agent demo.")
    parser.add_argument("query", nargs="?", help="User question to send to the agent")
    args = parser.parse_args()

    if not args.query:
        args.query = input("Enter a query: ")

    agent = Agent()
    output = agent.handle(args.query)
    pretty_print(output)


if __name__ == "__main__":
    main()
