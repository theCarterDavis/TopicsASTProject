import math
from flexible_tree_matching import parse_python, flexible_tree_match, describe_diff, print_diff, CostModel

code1 = "def foo(x): return x + 1"
code2 = "def bar(x): return x + 2"

t1 = parse_python(code1)
t2 = parse_python(code2)

model = CostModel(w_r=1.0, w_n=1.0, w_a=0.5, w_s=0.3)
matching, cost = flexible_tree_match(t1, t2, model=model)
score = math.exp(-cost)

print(f"Similarity score: {score:.4f}\n")

diff = describe_diff(matching)
print("Differences:")
print_diff(diff)


def deofunc():
    print("Here is a test for JJ!")
