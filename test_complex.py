"""
Complex AST comparison tests using flexible tree matching.
Each scenario compares two related but different Python code snippets.
"""
import math
from flexible_tree_matching import parse_python, flexible_tree_match, describe_diff, print_diff, CostModel

model = CostModel(w_r=1.0, w_n=1.0, w_a=0.5, w_s=0.3)

SEPARATOR = "=" * 60


def compare(label: str, code1: str, code2: str):
    t1 = parse_python(code1)
    t2 = parse_python(code2)
    matching, cost = flexible_tree_match(t1, t2, model=model, seed=42)
    score = math.exp(-cost)
    diff = describe_diff(matching)

    print(SEPARATOR)
    print(f"  {label}")
    print(SEPARATOR)
    print(f"  Code 1:\n    {code1.strip()}")
    print(f"\n  Code 2:\n    {code2.strip()}")
    print(f"\n  Similarity score: {score:.4f}\n")
    print("  Differences:")
    print_diff(diff)
    print()


# ---------------------------------------------------------------------------
# 1. Factorial: iterative vs recursive
# ---------------------------------------------------------------------------
compare(
    "Factorial — iterative vs recursive",
    code1="""
def factorial(n):
    result = 1
    for i in range(1, n + 1):
        result = result * i
    return result
""",
    code2="""
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""",
)

# ---------------------------------------------------------------------------
# 2. Sum of list: for-loop vs while-loop
# ---------------------------------------------------------------------------
compare(
    "Sum of list — for-loop vs while-loop",
    code1="""
def sum_list(items):
    total = 0
    for x in items:
        total = total + x
    return total
""",
    code2="""
def sum_list(items):
    total = 0
    i = 0
    while i < len(items):
        total = total + items[i]
        i = i + 1
    return total
""",
)

# ---------------------------------------------------------------------------
# 3. Fibonacci: memoized vs plain recursive
# ---------------------------------------------------------------------------
compare(
    "Fibonacci — plain recursive vs memoized",
    code1="""
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
""",
    code2="""
def fib(n, memo={}):
    if n <= 1:
        return n
    if n not in memo:
        memo[n] = fib(n - 1, memo) + fib(n - 2, memo)
    return memo[n]
""",
)

# ---------------------------------------------------------------------------
# 4. Linear search vs binary search
# ---------------------------------------------------------------------------
compare(
    "Search — linear vs binary",
    code1="""
def search(items, target):
    for i in range(len(items)):
        if items[i] == target:
            return i
    return -1
""",
    code2="""
def search(items, target):
    lo = 0
    hi = len(items) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if items[mid] == target:
            return mid
        elif items[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""",
)

# ---------------------------------------------------------------------------
# 5. Nearly identical functions — only the operator changes
# ---------------------------------------------------------------------------
compare(
    "Arithmetic — addition vs multiplication accumulator",
    code1="""
def accumulate(values):
    result = 0
    for v in values:
        result = result + v
    return result
""",
    code2="""
def accumulate(values):
    result = 1
    for v in values:
        result = result * v
    return result
""",
)

# ---------------------------------------------------------------------------
# 6. Class definition — similar classes, different method bodies
# ---------------------------------------------------------------------------
compare(
    "Counter class — increment-only vs increment/decrement",
    code1="""
class Counter:
    def __init__(self):
        self.count = 0
    def increment(self):
        self.count = self.count + 1
    def get(self):
        return self.count
""",
    code2="""
class Counter:
    def __init__(self):
        self.count = 0
    def increment(self):
        self.count = self.count + 1
    def decrement(self):
        self.count = self.count - 1
    def get(self):
        return self.count
""",
)

# ---------------------------------------------------------------------------
# 7. Completely different functions — low similarity expected
# ---------------------------------------------------------------------------
compare(
    "Unrelated functions — string reverse vs bubble sort",
    code1="""
def reverse_string(s):
    return s[::-1]
""",
    code2="""
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
""",
)
