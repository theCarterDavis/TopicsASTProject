# AST Diff — Flexible Tree Matching for Python Source Code

A tool that parses Python source files into Abstract Syntax Trees (ASTs) using
[tree-sitter](https://tree-sitter.github.io/tree-sitter/) and compares them
using a flexible tree matching algorithm based on the Metropolis method. A
GitHub Actions workflow automatically detects changed Python files on every push
and runs the AST comparison inside a Docker container.

---

## Overview

| Component | Description |
|---|---|
| `parse.py` | Parses a single Python file with tree-sitter and prints its AST |
| `compare.py` | Compares two Python files — prints both ASTs, a similarity score, and a structural diff |
| `flexible_tree_matching.py` | Core library implementing the flexible tree matching algorithm (cost model, Metropolis optimisation, diff generation) |
| `Dockerfile` | Packages the tools into a lightweight Python 3.11 container with all dependencies |
| `.github/workflows/ast-parse.yml` | GitHub Actions workflow that runs the comparison automatically on every push |
| `test.py` | Quick smoke test comparing two one-liner functions |
| `test_complex.py` | Suite of seven comparison scenarios (iterative vs recursive, linear vs binary search, etc.) |

---

## How It Works

### 1. AST Parsing (tree-sitter)

`parse.py` reads a Python file, parses it with the tree-sitter Python grammar,
and prints the full syntax tree. Each node shows its type and a snippet of the
corresponding source text.

### 2. Flexible Tree Matching Algorithm

`flexible_tree_matching.py` implements a cost-based tree matching approach:

- **Relabeling cost (`w_r`)** — penalty when two matched nodes have different labels.
- **No-match cost (`w_n`)** — penalty for leaving a node unmatched (deletion / insertion).
- **Ancestry cost (`w_a`)** — penalty when a matched pair's parent–child relationships are violated.
- **Sibling cost (`w_s`)** — penalty when a matched pair's sibling relationships are violated.

The algorithm uses a **Metropolis (simulated annealing) search** to find a
low-cost matching between the two trees, then converts the cost into a
**similarity score** between 0 and 1 (`exp(-cost)`).

### 3. Diff Output

After matching, the tool reports:

- **Similarity score** — 1.0 means structurally identical, closer to 0 means very different.
- **Exact matches** — AST nodes that are identical in both versions.
- **Relabeled nodes** — nodes that exist in both trees but with different labels (e.g., a renamed variable).
- **Deleted nodes** — nodes present in the old version but missing from the new.
- **Inserted nodes** — nodes present in the new version but missing from the old.

### 4. CI / GitHub Actions Pipeline

On every push to any branch, the GitHub Actions workflow:

1. Checks out the repository with full git history.
2. Builds the Docker image from the `Dockerfile`.
3. Compares `HEAD` against `HEAD~1` to find changed `.py` files.
4. For each changed file:
   - If the file existed in the previous commit → extracts both versions, runs `compare.py` inside Docker, and prints the ASTs, similarity score, and diff.
   - If the file is newly added → runs `parse.py` inside Docker and prints only its AST.

---

## Getting Started

### Prerequisites

- Docker
- (Optional) Python 3.11+ with `tree-sitter` and `tree-sitter-python` for local runs

### Build the Docker image

```bash
docker build -t ast-parser .
```

### Parse a single file

```bash
docker run --rm -v "$(pwd)/hello_world_example.py:/app/target.py" ast-parser parse.py target.py
```

### Compare two files

```bash
docker run --rm \
  -v "$(pwd)/file_old.py:/app/old.py" \
  -v "$(pwd)/file_new.py:/app/new.py" \
  ast-parser compare.py old.py new.py
```

### Run locally (without Docker)

```bash
pip install tree-sitter==0.25.2 tree-sitter-python==0.25.0

# Parse a single file
python parse.py hello_world_example.py

# Compare two files
python compare.py file_old.py file_new.py

# Run the test suites
python test.py
python test_complex.py
```

---

## Project Structure

```
TopicsASTProject/
├── .github/
│   └── workflows/
│       └── ast-parse.yml            # CI workflow — runs on every push
├── Dockerfile                        # Container with Python 3.11 + tree-sitter
├── README.md
├── parse.py                          # Single-file AST printer
├── compare.py                        # Two-file AST comparison entry point
├── flexible_tree_matching.py         # Core matching algorithm & utilities
├── test.py                           # Quick comparison smoke test
├── test_complex.py                   # Seven detailed comparison scenarios
└── hello_world_example.py            # Sample Python file for testing
```

---

## Example Output

Running `compare.py` on two versions of a function produces output like:

```
============================================================
  OLD AST  (old.py)
============================================================
module
  function_definition
    identifier:factorial
    parameters
      identifier:n
    ...

============================================================
  NEW AST  (new.py)
============================================================
module
  function_definition
    identifier:factorial
    parameters
      identifier:n
    ...

============================================================
  COMPARISON RESULTS
============================================================
  Similarity score : 0.8523
  Matching cost    : 0.1598

  Differences:
  Exact matches : 14
  Relabeled     : 2
  Deleted (T1)  : 3
  Inserted (T2) : 1

  --- Relabeled nodes ---
    identifier:result  →  identifier:n
    ...
```

---
