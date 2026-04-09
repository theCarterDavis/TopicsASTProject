"""
Compare two Python source files using tree-sitter AST parsing
and the flexible tree matching algorithm.

Usage:
    python compare.py <old_file> <new_file>

Prints:
    - The AST for each file
    - The similarity score between the two ASTs
    - A detailed diff (matched, relabeled, deleted, inserted nodes)
"""

import sys
import math
from flexible_tree_matching import (
    parse_python,
    flexible_tree_match,
    describe_diff,
    print_diff,
    print_tree,
    CostModel,
)

SEPARATOR = "=" * 60


def main():
    if len(sys.argv) != 3:
        print("Usage: python compare.py <old_file> <new_file>")
        sys.exit(1)

    old_path = sys.argv[1]
    new_path = sys.argv[2]

    # Read source files
    with open(old_path, "r") as f:
        old_source = f.read()
    with open(new_path, "r") as f:
        new_source = f.read()

    # Parse both files into TreeNode ASTs
    t1 = parse_python(old_source)
    t2 = parse_python(new_source)

    # Print both ASTs
    print(SEPARATOR)
    print(f"  OLD AST  ({old_path})")
    print(SEPARATOR)
    print_tree(t1)

    print()
    print(SEPARATOR)
    print(f"  NEW AST  ({new_path})")
    print(SEPARATOR)
    print_tree(t2)

    # Run the flexible tree matching algorithm
    model = CostModel(w_r=1.0, w_n=1.0, w_a=0.5, w_s=0.3)
    matching, cost = flexible_tree_match(t1, t2, model=model, seed=42)
    score = math.exp(-cost)

    # Print comparison results
    print()
    print(SEPARATOR)
    print("  COMPARISON RESULTS")
    print(SEPARATOR)
    print(f"  Similarity score : {score:.4f}")
    print(f"  Matching cost    : {cost:.4f}")
    print()

    # Print the diff summary
    diff = describe_diff(matching)
    print("  Differences:")
    print_diff(diff)
    print()


if __name__ == "__main__":
    main()

