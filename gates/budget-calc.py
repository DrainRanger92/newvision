#!/usr/bin/env python3
"""Calculate CostPerAcceptedChange from budget.json entries."""
import json
import sys

COMPUTE_RATE = 0.50


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/budget.json"
    try:
        with open(path) as f:
            cycles = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("No budget data found.")
        sys.exit(0)

    for c in cycles:
        token = c.get("total_token_cost", 0)
        compute_cost = c.get("total_compute_minutes", 0) * COMPUTE_RATE
        total = token + compute_cost
        c["compute_cost"] = compute_cost
        c["total_cost"] = total
        prs = max(c.get("accepted_prs", 1), 1)
        c["cost_per_accepted_change"] = total / prs

    with open(path, "w") as f:
        json.dump(cycles, f, indent=2)

    total_across = sum(c.get("total_cost", 0) for c in cycles)
    print(f"Total cycles: {len(cycles)}")
    print(f"Total cost: ${total_across:.2f}")
    for c in cycles:
        cid = c.get("cycle_id", "?")
        cpac = c.get("cost_per_accepted_change", 0)
        print(f"  {cid}: ${cpac:.2f}/PR")


if __name__ == "__main__":
    main()
