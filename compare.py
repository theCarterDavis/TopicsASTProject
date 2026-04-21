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

def get_function_name(func_node):
    """
    Return the function name from a function_definition TreeNode.
    """
    for child in func_node.children:
        if child.label.startswith("identifier:"):
            return child.label.split(":", 1)[1]
    return None


def get_function_signature(func_node):
    """
    Return a simple signature string based on the parameters child.
    """
    for child in func_node.children:
        if child.label.startswith("parameters"):
            return child.label
    return None


def serialize_tree(node):
    """
    Convert a TreeNode into a deterministic string so we can compare bodies.
    """
    parts = [node.label]
    for child in node.children:
        parts.append(serialize_tree(child))
    return "(" + " ".join(parts) + ")"


def get_function_body_repr(func_node):
    """
    Return a serialized representation of the function body/block.
    """
    for child in func_node.children:
        if child.label == "block":
            return serialize_tree(child)
    return ""

def _split_label(label):
    """
    Split a label like 'identifier:x' into ('identifier', 'x').

    If there is no ':', returns (label, None).
    """
    if label is None:
        return None, None
    if ":" in label:
        kind, value = label.split(":", 1)
        return kind, value
    return label, None

def collect_functions(root):
    """
    Collect all function_definition nodes from the AST.
    Returns a dict: function_name -> function node
    """
    functions = {}

    def walk(node):
        if node.label == "function_definition":
            name = get_function_name(node)
            if name:
                functions[name] = node
        for child in node.children:
            walk(child)

    walk(root)
    return functions


def print_function_summary_from_trees(t1, t2):
    """
    Print a cleaner function-level summary by comparing functions by name,
    not by trusting the general AST matching output.
    """
    old_funcs = collect_functions(t1)
    new_funcs = collect_functions(t2)

    old_names = set(old_funcs.keys())
    new_names = set(new_funcs.keys())

    shared = sorted(old_names & new_names)
    deleted = sorted(old_names - new_names)
    added = sorted(new_names - old_names)

    print("  Function summary:")

    found_any = False

    # Added functions
    for name in added:
        line = new_funcs[name].line
        print(f'    - Added function "{name}" on line {line}')
        found_any = True

    # Deleted functions
    for name in deleted:
        line = old_funcs[name].line
        print(f'    - Deleted function "{name}" from line {line}')
        found_any = True

    # Shared functions: check move / signature / body
    for name in shared:
        old_node = old_funcs[name]
        new_node = new_funcs[name]

        if old_node.line != new_node.line:
            print(
                f'    - Function "{name}" moved from line {old_node.line} to line {new_node.line}'
            )
            found_any = True

        old_sig = get_function_signature(old_node)
        new_sig = get_function_signature(new_node)
        if old_sig != new_sig:
            print(
                f'    - Function "{name}" changed parameters from {old_sig} to {new_sig}'
            )
            found_any = True

        old_body = get_function_body_repr(old_node)
        new_body = get_function_body_repr(new_node)
        if old_body != new_body:
            print(f'    - Function "{name}" changed body')
            found_any = True

    if not found_any:
        print("    - No major function-level changes detected.")


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

    # Print a more human-readable summary
    print_function_summary_from_trees(t1, t2)
    print()


if __name__ == "__main__":
    main()

