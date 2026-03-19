from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

@dataclass
class TreeNode:
    """A labeled tree node with children."""
    label: str
    children: list["TreeNode"] = field(default_factory=list)
    parent: Optional["TreeNode"] = field(default=None, repr=False)
    _id: int = field(default=-1, repr=False)

    def add_child(self, child: "TreeNode") -> "TreeNode":
        child.parent = self
        self.children.append(child)
        return child

    def siblings(self) -> list["TreeNode"]:
        """Return the sibling group S(m) = children of parent."""
        if self.parent is None:
            return [self]
        return list(self.parent.children)

    def siblings_excluding_self(self) -> list["TreeNode"]:
        """Return S_bar(m) = S(m) \\ {m}."""
        return [s for s in self.siblings() if s is not self]

    def is_root(self) -> bool:
        return self.parent is None

    def depth(self) -> int:
        d = 0
        node = self
        while node.parent is not None:
            d += 1
            node = node.parent
        return d

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


def collect_nodes(root: TreeNode) -> list[TreeNode]:
    """BFS collection of all nodes in a tree, assigning internal IDs."""
    nodes = []
    stack = [root]
    idx = 0
    while stack:
        node = stack.pop()
        node._id = idx
        idx += 1
        nodes.append(node)
        for child in reversed(node.children):
            stack.append(child)
    return nodes


# ---------------------------------------------------------------------------
# No-match sentinel
# ---------------------------------------------------------------------------

class _NoMatch:
    """Sentinel node representing the no-match / deletion target."""
    def __init__(self, name: str = "⊗"):
        self.label = name
        self.children = []
        self.parent = None
        self._id = -1

    def siblings(self):
        return []

    def siblings_excluding_self(self):
        return []

    def is_root(self):
        return True

    def __repr__(self):
        return f"NoMatch({self.label})"

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other

NO_MATCH_1 = _NoMatch("⊗1")
NO_MATCH_2 = _NoMatch("⊗2")


# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------

@dataclass
class CostModel:
    """
    Weights for the flexible tree matching cost model.

    Attributes:
        w_r: relabeling weight (cost of matching nodes with different labels)
        w_n: no-match penalty (cost of leaving a node unmatched)
        w_a: ancestry violation weight
        w_s: sibling violation weight
        relabel_fn: optional custom relabeling cost function(label1, label2) -> float.
                     If None, returns w_r when labels differ, 0 when identical.
    """
    w_r: float = 1.0
    w_n: float = 1.0
    w_a: float = 0.5
    w_s: float = 0.5
    relabel_fn: Optional[Callable[[str, str], float]] = None

    def relabel_cost(self, label1: str, label2: str) -> float:
        if self.relabel_fn is not None:
            return self.relabel_fn(label1, label2)
        return 0.0 if label1 == label2 else self.w_r


# ---------------------------------------------------------------------------
# Matching representation
# ---------------------------------------------------------------------------

@dataclass
class Edge:
    """An edge in the bipartite matching graph."""
    node1: Any  # TreeNode or _NoMatch
    node2: Any  # TreeNode or _NoMatch

    def __hash__(self):
        return hash((id(self.node1), id(self.node2)))

    def __eq__(self, other):
        return self.node1 is other.node1 and self.node2 is other.node2


class Matching:
    """
    A mapping between nodes of T1 and T2.
    Stores edges and provides fast lookup of images.
    """

    def __init__(self):
        self.edges: list[Edge] = []
        self._image: dict[int, Any] = {}  # id(node) -> matched node

    def add_edge(self, e: Edge):
        self.edges.append(e)
        self._image[id(e.node1)] = e.node2
        self._image[id(e.node2)] = e.node1

    def image(self, node) -> Any:
        """Return M(node), the node's image in the matching."""
        return self._image.get(id(node))

    def copy(self) -> "Matching":
        m = Matching()
        for e in self.edges:
            m.add_edge(e)
        return m

    def __len__(self):
        return len(self.edges)


# ---------------------------------------------------------------------------
# Exact cost computation (Section 3)
# ---------------------------------------------------------------------------

def ancestry_violating_children(m: TreeNode, n: Any, matching: Matching) -> list[TreeNode]:
    """
    V(m): children of m whose images are NOT children of M(m)=n.
    """
    if isinstance(n, _NoMatch):
        # All matched children violate ancestry
        result = []
        for child in m.children:
            img = matching.image(child)
            if img is not None and not isinstance(img, _NoMatch):
                result.append(child)
        return result

    n_children_ids = {id(c) for c in n.children}
    violations = []
    for child in m.children:
        img = matching.image(child)
        if img is not None and not isinstance(img, _NoMatch) and id(img) not in n_children_ids:
            violations.append(child)
    return violations


def compute_ancestry_cost(edge: Edge, matching: Matching, model: CostModel) -> float:
    """Compute ca([m, n]; M) = wa * (|V(m)| + |V(n)|)."""
    m, n = edge.node1, edge.node2
    if isinstance(m, _NoMatch) or isinstance(n, _NoMatch):
        return 0.0
    v_m = len(ancestry_violating_children(m, n, matching))
    v_n = len(ancestry_violating_children(n, m, matching))
    return model.w_a * (v_m + v_n)


def compute_sibling_cost(edge: Edge, matching: Matching, model: CostModel) -> float:
    """Compute cs([m, n]; M) using sibling-invariant/divergent subsets."""
    m, n = edge.node1, edge.node2
    if isinstance(m, _NoMatch) or isinstance(n, _NoMatch):
        return 0.0

    def _sibling_ratio(node, partner):
        siblings = node.siblings()
        partner_sibling_ids = {id(s) for s in partner.siblings()}

        invariant = 0
        divergent = 0
        family_parents = set()

        for sib in siblings:
            img = matching.image(sib)
            if img is None or isinstance(img, _NoMatch):
                continue
            if id(img) in partner_sibling_ids:
                invariant += 1
            else:
                divergent += 1
            # Track distinct families
            if hasattr(img, 'parent') and img.parent is not None:
                family_parents.add(id(img.parent))
            else:
                family_parents.add(id(img))

        num_families = max(len(family_parents), 1)
        invariant = max(invariant, 1)  # Avoid division by zero

        if divergent == 0:
            return 0.0
        return divergent / (invariant * num_families)

    ratio_m = _sibling_ratio(m, n)
    ratio_n = _sibling_ratio(n, m)
    return model.w_s * (ratio_m + ratio_n)


def compute_edge_cost(edge: Edge, matching: Matching, model: CostModel) -> float:
    """Compute total edge cost c(e) = cr(e) + ca(e) + cs(e)."""
    m, n = edge.node1, edge.node2

    # No-match edges have fixed cost
    if isinstance(m, _NoMatch) or isinstance(n, _NoMatch):
        return model.w_n

    cr = model.relabel_cost(m.label, n.label)
    ca = compute_ancestry_cost(edge, matching, model)
    cs = compute_sibling_cost(edge, matching, model)
    return cr + ca + cs


def compute_matching_cost(matching: Matching, model: CostModel,
                          size_t1: int, size_t2: int) -> float:
    """
    Compute c(M) = 1/(|T1|+|T2|) * sum of edge costs.
    """
    total = sum(compute_edge_cost(e, matching, model) for e in matching.edges)
    return total / (size_t1 + size_t2)


# ---------------------------------------------------------------------------
# Edge cost bounds (Section 6)
# ---------------------------------------------------------------------------

class BipartiteGraph:
    """
    The complete bipartite graph G between T1 ∪ {⊗1} and T2 ∪ {⊗2},
    with support for edge pruning and bound computation.
    """

    def __init__(self, nodes1: list[TreeNode], nodes2: list[TreeNode],
                 model: CostModel):
        self.nodes1 = nodes1
        self.nodes2 = nodes2
        self.model = model

        # Build adjacency: for each node, track which edges still exist
        # edges_from[id(node)] = set of id(partner) that are still available
        self.edges_from: dict[int, set[int]] = {}
        self._node_by_id: dict[int, Any] = {}

        all1 = list(nodes1) + [NO_MATCH_1]
        all2 = list(nodes2) + [NO_MATCH_2]

        for node in all1:
            self._node_by_id[id(node)] = node
            self.edges_from[id(node)] = {id(n2) for n2 in all2}
        for node in all2:
            self._node_by_id[id(node)] = node
            self.edges_from[id(node)] = {id(n1) for n1 in all1}

    def has_edge(self, a, b) -> bool:
        return id(b) in self.edges_from.get(id(a), set())

    def prune_node(self, node):
        """Remove all edges incident on `node` (except to no-match)."""
        nid = id(node)
        partners = list(self.edges_from.get(nid, set()))
        for pid in partners:
            if pid in self.edges_from:
                self.edges_from[pid].discard(nid)
        self.edges_from[nid] = set()

    def fix_edge(self, m, n):
        """
        Fix edge [m, n]: remove all other edges incident on m and n
        (but keep no-match edges for other nodes).
        """
        mid, nid = id(m), id(n)

        # Remove all edges from m except to n
        for pid in list(self.edges_from.get(mid, set())):
            if pid != nid:
                if pid in self.edges_from:
                    self.edges_from[pid].discard(mid)
        self.edges_from[mid] = {nid}

        # Remove all edges from n except to m
        for pid in list(self.edges_from.get(nid, set())):
            if pid != mid:
                if pid in self.edges_from:
                    self.edges_from[pid].discard(nid)
        self.edges_from[nid] = {mid}

    def available_partners(self, node) -> list:
        """Return all nodes still connected to `node`."""
        return [self._node_by_id[pid]
                for pid in self.edges_from.get(id(node), set())
                if pid in self._node_by_id]

    def edge_exists_between(self, node, target_set_ids: set) -> bool:
        """Check if any edge from node goes to a node in target_set_ids."""
        return bool(self.edges_from.get(id(node), set()) & target_set_ids)

    def all_edges_in(self, node, target_set_ids: set) -> bool:
        """Check if ALL edges from node go to nodes in target_set_ids."""
        edges = self.edges_from.get(id(node), set())
        if not edges:
            return True
        return edges.issubset(target_set_ids)

    def compute_ancestry_bounds(self, m: TreeNode, n: TreeNode) -> tuple[float, float]:
        """Compute [La, Ua] for edge [m, n]."""
        if isinstance(m, _NoMatch) or isinstance(n, _NoMatch):
            return 0.0, 0.0

        children_n_ids = {id(c) for c in n.children} | {id(NO_MATCH_2)}
        not_children_n_ids = set()
        for nid in self.edges_from.get(id(m), set()):
            node = self._node_by_id.get(nid)
            if node and id(node) not in children_n_ids:
                not_children_n_ids.add(nid)

        # For each child of m
        upper_m = 0
        lower_m = 0
        for m_prime in m.children:
            # Upper: can m' induce a violation?
            if self.edge_exists_between(m_prime,
                    {pid for pid in self.edges_from.get(id(m_prime), set())
                     if pid not in children_n_ids}):
                upper_m += 1
            # Lower: must m' induce a violation?
            if not self.edge_exists_between(m_prime, children_n_ids):
                lower_m += 1

        children_m_ids = {id(c) for c in m.children} | {id(NO_MATCH_1)}

        upper_n = 0
        lower_n = 0
        for n_prime in n.children:
            if self.edge_exists_between(n_prime,
                    {pid for pid in self.edges_from.get(id(n_prime), set())
                     if pid not in children_m_ids}):
                upper_n += 1
            if not self.edge_exists_between(n_prime, children_m_ids):
                lower_n += 1

        lower = self.model.w_a * (lower_m + lower_n)
        upper = self.model.w_a * (upper_m + upper_n)
        return lower, upper

    def compute_sibling_bounds(self, m: TreeNode, n: TreeNode) -> tuple[float, float]:
        """Compute [Ls, Us] for edge [m, n]."""
        if isinstance(m, _NoMatch) or isinstance(n, _NoMatch):
            return 0.0, 0.0

        def _compute_side(node, partner):
            s_bar = node.siblings_excluding_self()
            partner_sib_ids = {id(s) for s in partner.siblings_excluding_self()} | {id(NO_MATCH_2 if node in self.nodes1 else NO_MATCH_1)}
            partner_sib_only = {id(s) for s in partner.siblings_excluding_self()}

            ud = sum(1 for sp in s_bar
                     if self.edge_exists_between(sp,
                         {pid for pid in self.edges_from.get(id(sp), set())
                          if pid not in partner_sib_ids}))
            ld = sum(1 for sp in s_bar
                     if not self.edge_exists_between(sp, partner_sib_ids))

            ui = 1 + sum(1 for sp in s_bar
                         if self.edge_exists_between(sp, partner_sib_only))
            li = 1 + sum(1 for sp in s_bar
                         if self.all_edges_in(sp, partner_sib_only))

            return ud, ld, ui, li

        ud_m, ld_m, ui_m, li_m = _compute_side(m, n)
        ud_n, ld_n, ui_n, li_n = _compute_side(n, m)

        # Upper bound
        li_m = max(li_m, 1)
        li_n = max(li_n, 1)
        upper = self.model.w_s / 2 * (ud_m / li_m + ud_n / li_n)

        # Lower bound
        ui_m = max(ui_m, 1)
        ui_n = max(ui_n, 1)
        lower = self.model.w_s * (
            ld_m / (ui_m * (ld_m + 1)) if ld_m > 0 else 0 +
            ld_n / (ui_n * (ld_n + 1)) if ld_n > 0 else 0
        )

        return lower, upper

    def compute_edge_bounds(self, m, n) -> tuple[float, float]:
        """Compute [cL, cU] for edge [m, n]."""
        if isinstance(m, _NoMatch) or isinstance(n, _NoMatch):
            return self.model.w_n, self.model.w_n

        cr = self.model.relabel_cost(m.label, n.label)
        la, ua = self.compute_ancestry_bounds(m, n)
        ls, us = self.compute_sibling_bounds(m, n)
        return cr + la + ls, cr + ua + us


# ---------------------------------------------------------------------------
# Metropolis algorithm (Section 7)
# ---------------------------------------------------------------------------

def _build_initial_matching(nodes1: list[TreeNode], nodes2: list[TreeNode],
                            model: CostModel, gamma: float = 0.7) -> Matching:
    """
    Build an initial matching by traversing edges in order of increasing
    lower bound, accepting each with probability gamma.
    """
    graph = BipartiteGraph(nodes1, nodes2, model)
    matching = Matching()
    matched1 = set()
    matched2 = set()

    # Compute bounds for all candidate edges
    candidates = []
    for m in nodes1:
        for n in nodes2:
            lb, ub = graph.compute_edge_bounds(m, n)
            candidates.append((lb, ub, m, n))

    # Sort by lower bound
    candidates.sort(key=lambda x: x[0])

    for lb, ub, m, n in candidates:
        if id(m) in matched1 or id(n) in matched2:
            continue
        if random.random() < gamma:
            matching.add_edge(Edge(m, n))
            matched1.add(id(m))
            matched2.add(id(n))
            graph.fix_edge(m, n)

    # Match remaining nodes to no-match
    for m in nodes1:
        if id(m) not in matched1:
            matching.add_edge(Edge(m, NO_MATCH_2))
    for n in nodes2:
        if id(n) not in matched2:
            matching.add_edge(Edge(NO_MATCH_1, n))

    return matching


def _propose_matching(current: Matching, nodes1: list[TreeNode],
                      nodes2: list[TreeNode], model: CostModel,
                      gamma: float = 0.7) -> Matching:
    """
    Propose a new matching M_hat by fixing the first j edges from
    the current matching and re-building the rest.
    """
    # Choose a random split point
    # Only consider real (non-no-match) edges
    real_edges = [e for e in current.edges
                  if not isinstance(e.node1, _NoMatch) and not isinstance(e.node2, _NoMatch)]

    if len(real_edges) == 0:
        return _build_initial_matching(nodes1, nodes2, model, gamma)

    j = random.randint(0, len(real_edges))

    # Fix the first j edges
    matching = Matching()
    matched1 = set()
    matched2 = set()
    graph = BipartiteGraph(nodes1, nodes2, model)

    for i in range(j):
        e = real_edges[i]
        matching.add_edge(e)
        matched1.add(id(e.node1))
        matched2.add(id(e.node2))
        graph.fix_edge(e.node1, e.node2)

    # Build the rest greedily with stochastic selection
    remaining1 = [m for m in nodes1 if id(m) not in matched1]
    remaining2 = [n for n in nodes2 if id(n) not in matched2]

    candidates = []
    for m in remaining1:
        for n in remaining2:
            lb, ub = graph.compute_edge_bounds(m, n)
            candidates.append((lb, ub, m, n))

    candidates.sort(key=lambda x: x[0])

    for lb, ub, m, n in candidates:
        if id(m) in matched1 or id(n) in matched2:
            continue
        if random.random() < gamma:
            matching.add_edge(Edge(m, n))
            matched1.add(id(m))
            matched2.add(id(n))

    # Match remaining to no-match
    for m in nodes1:
        if id(m) not in matched1:
            matching.add_edge(Edge(m, NO_MATCH_2))
    for n in nodes2:
        if id(n) not in matched2:
            matching.add_edge(Edge(NO_MATCH_1, n))

    return matching


def flexible_tree_match(t1: TreeNode, t2: TreeNode,
                        model: Optional[CostModel] = None,
                        n_iterations: int = 100,
                        beta: float = 10.0,
                        gamma: float = 0.7,
                        seed: Optional[int] = None) -> tuple[Matching, float]:
    """
    Find an approximate minimum-cost flexible matching between trees T1 and T2
    using the Metropolis algorithm.

    Args:
        t1: Root of tree 1
        t2: Root of tree 2
        model: Cost model with weights (defaults to balanced weights)
        n_iterations: Number of Metropolis iterations
        beta: Boltzmann constant for acceptance probability
        gamma: Edge acceptance probability during construction
        seed: Random seed for reproducibility

    Returns:
        (best_matching, best_cost): The lowest-cost matching found and its cost
    """
    if seed is not None:
        random.seed(seed)

    if model is None:
        model = CostModel()

    nodes1 = collect_nodes(t1)
    nodes2 = collect_nodes(t2)
    size1 = len(nodes1)
    size2 = len(nodes2)

    # Initialize
    current = _build_initial_matching(nodes1, nodes2, model, gamma)
    current_cost = compute_matching_cost(current, model, size1, size2)

    best = current
    best_cost = current_cost

    for _ in range(n_iterations):
        proposed = _propose_matching(current, nodes1, nodes2, model, gamma)
        proposed_cost = compute_matching_cost(proposed, model, size1, size2)

        # Metropolis acceptance
        f_proposed = math.exp(-beta * proposed_cost)
        f_current = math.exp(-beta * current_cost)

        if f_current > 0:
            alpha = min(1.0, f_proposed / f_current)
        else:
            alpha = 1.0

        if random.random() < alpha:
            current = proposed
            current_cost = proposed_cost

        if current_cost < best_cost:
            best = current
            best_cost = current_cost

    return best, best_cost


# ---------------------------------------------------------------------------
# Similarity score
# ---------------------------------------------------------------------------

def tree_similarity(t1: TreeNode, t2: TreeNode,
                    model: Optional[CostModel] = None,
                    **kwargs) -> float:
    """
    Compute a similarity score in [0, 1] between two trees.
    1.0 means identical structure/labels, 0.0 means completely different.

    This normalizes the matching cost into a similarity score.
    """
    _, cost = flexible_tree_match(t1, t2, model=model, **kwargs)
    # The cost is already normalized by tree sizes.
    # Convert to similarity: lower cost = higher similarity
    return math.exp(-cost)


# ---------------------------------------------------------------------------
# Diff description
# ---------------------------------------------------------------------------

@dataclass
class DiffEntry:
    """A single entry in a tree diff."""
    kind: str              # "match" | "relabel" | "deleted" | "inserted"
    label1: Optional[str]  # label from T1 (None if inserted)
    label2: Optional[str]  # label from T2 (None if deleted)


def describe_diff(matching: Matching) -> list[DiffEntry]:
    """
    Analyze a Matching and return a list of DiffEntry objects.

    Each entry is one of:
      - "match"    : nodes paired with identical labels
      - "relabel"  : nodes paired but with different labels
      - "deleted"  : node in T1 has no counterpart in T2
      - "inserted" : node in T2 has no counterpart in T1
    """
    entries: list[DiffEntry] = []
    for e in matching.edges:
        n1_is_nomatch = isinstance(e.node1, _NoMatch)
        n2_is_nomatch = isinstance(e.node2, _NoMatch)

        if n1_is_nomatch:
            entries.append(DiffEntry("inserted", None, e.node2.label))
        elif n2_is_nomatch:
            entries.append(DiffEntry("deleted", e.node1.label, None))
        elif e.node1.label == e.node2.label:
            entries.append(DiffEntry("match", e.node1.label, e.node2.label))
        else:
            entries.append(DiffEntry("relabel", e.node1.label, e.node2.label))

    return entries


def print_diff(diff: list[DiffEntry]):
    """Print a human-readable summary of a tree diff."""
    relabeled = [d for d in diff if d.kind == "relabel"]
    deleted   = [d for d in diff if d.kind == "deleted"]
    inserted  = [d for d in diff if d.kind == "inserted"]
    matched   = [d for d in diff if d.kind == "match"]

    print(f"  Exact matches : {len(matched)}")
    print(f"  Relabeled     : {len(relabeled)}")
    print(f"  Deleted (T1)  : {len(deleted)}")
    print(f"  Inserted (T2) : {len(inserted)}")

    if relabeled:
        print("\n  --- Relabeled nodes ---")
        for d in relabeled:
            print(f"    {d.label1}  →  {d.label2}")

    if deleted:
        print("\n  --- Deleted nodes (in T1, no match in T2) ---")
        for d in deleted:
            print(f"    - {d.label1}")

    if inserted:
        print("\n  --- Inserted nodes (in T2, no match in T1) ---")
        for d in inserted:
            print(f"    + {d.label2}")


# ---------------------------------------------------------------------------
# AST utilities  (tree-sitter based)
# ---------------------------------------------------------------------------

def _get_ts_parser():
    """Return a cached tree-sitter Parser for Python."""
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser

    lang = Language(tspython.language())
    parser = Parser(lang)
    return parser


def tree_sitter_to_tree(ts_node, source: bytes) -> TreeNode:
    """
    Convert a tree-sitter Node into a TreeNode for matching.

    Only *named* nodes are kept (skipping anonymous punctuation / keywords).
    Leaf named nodes are enriched with their source text so that, e.g.,
    two ``identifier`` nodes with different names get distinct labels.

    Args:
        ts_node:  A ``tree_sitter.Node`` (typically the root_node of a parsed tree).
        source:   The original source code as ``bytes`` (needed to extract text).

    Returns:
        A ``TreeNode`` hierarchy suitable for flexible tree matching.
    """
    # Build label
    label = ts_node.type

    # For leaf named nodes, append the actual source text for richer matching
    if ts_node.named_child_count == 0 and ts_node.is_named:
        text = source[ts_node.start_byte:ts_node.end_byte].decode(errors="replace")
        label = f"{ts_node.type}:{text}"

    tree_node = TreeNode(label=label)

    for child in ts_node.named_children:
        child_tree = tree_sitter_to_tree(child, source)
        tree_node.add_child(child_tree)

    return tree_node


def parse_python(source: str) -> TreeNode:
    """
    Parse a Python source string with tree-sitter and return a TreeNode tree.

    Usage::

        t = parse_python("x = 1 + 2")
    """
    parser = _get_ts_parser()
    source_bytes = source.encode()
    ts_tree = parser.parse(source_bytes)
    return tree_sitter_to_tree(ts_tree.root_node, source_bytes)


# ---------------------------------------------------------------------------
# Visualization / debugging helpers
# ---------------------------------------------------------------------------

def print_tree(node: TreeNode, indent: int = 0):
    """Print a tree structure to stdout."""
    print("  " * indent + node.label)
    for child in node.children:
        print_tree(child, indent + 1)


def print_matching(matching: Matching):
    """Print the edges of a matching."""
    for e in matching.edges:
        l1 = e.node1.label if hasattr(e.node1, 'label') else str(e.node1)
        l2 = e.node2.label if hasattr(e.node2, 'label') else str(e.node2)
        if isinstance(e.node1, _NoMatch):
            print(f"  [DELETE] ← {l2}")
        elif isinstance(e.node2, _NoMatch):
            print(f"  {l1} → [DELETE]")
        else:
            marker = "=" if l1 == l2 else "≈"
            print(f"  {l1} {marker} {l2}")


# ---------------------------------------------------------------------------
# Demo / example usage
# ---------------------------------------------------------------------------

def demo_basic():
    """Demonstrate matching two simple labeled trees."""
    print("=" * 60)
    print("DEMO: Basic labeled tree matching")
    print("=" * 60)

    # Tree 1:      A
    #            /   \
    #           B     D
    #          / \   / \
    #         C   C F   G
    t1 = TreeNode("A")
    b1 = t1.add_child(TreeNode("B"))
    d1 = t1.add_child(TreeNode("D"))
    b1.add_child(TreeNode("C"))
    b1.add_child(TreeNode("C"))
    d1.add_child(TreeNode("F"))
    d1.add_child(TreeNode("G"))

    # Tree 2:      A
    #            /   \
    #           G     D
    #            \   / \
    #             B C   C
    #            / \
    #           F   F
    t2 = TreeNode("A")
    g2 = t2.add_child(TreeNode("G"))
    d2 = t2.add_child(TreeNode("D"))
    b2 = g2.add_child(TreeNode("B"))
    d2.add_child(TreeNode("C"))
    d2.add_child(TreeNode("C"))
    b2.add_child(TreeNode("F"))
    b2.add_child(TreeNode("F"))

    print("\nTree 1:")
    print_tree(t1)
    print("\nTree 2:")
    print_tree(t2)

    # Try different weight configurations
    configs = [
        ("Balanced", CostModel(w_r=1.0, w_n=1.0, w_a=0.5, w_s=0.5)),
        ("Ancestry-heavy", CostModel(w_r=0.9, w_n=1.0, w_a=1.0, w_s=0.1)),
        ("Sibling-heavy", CostModel(w_r=0.9, w_n=1.0, w_a=0.1, w_s=1.0)),
    ]

    for name, model in configs:
        matching, cost = flexible_tree_match(t1, t2, model=model, seed=42)
        sim = tree_similarity(t1, t2, model=model, seed=42)
        print(f"\n--- {name} (w_r={model.w_r}, w_a={model.w_a}, w_s={model.w_s}) ---")
        print(f"Cost: {cost:.4f}  |  Similarity: {sim:.4f}")
        print_matching(matching)


def demo_ast_comparison():
    """Demonstrate comparing Python ASTs (via tree-sitter)."""

    print("\n" + "=" * 60)
    print("DEMO: AST similarity comparison (tree-sitter)")
    print("=" * 60)

    code_a = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""

    code_b = """
def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)
"""

    code_c = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
"""

    code_d = """
def hello():
    print("Hello, world!")
"""

    snippets = [
        ("factorial_v1", code_a),
        ("factorial_v2", code_b),
        ("fibonacci", code_c),
        ("hello_world", code_d),
    ]

    trees = [(name, parse_python(code)) for name, code in snippets]

    model = CostModel(w_r=1.0, w_n=1.0, w_a=0.5, w_s=0.3)

    print("\nPairwise similarity matrix:\n")
    header = "                " + "  ".join(f"{name:>14}" for name, _ in trees)
    print(header)
    print("-" * len(header))

    for name1, t1 in trees:
        row = f"{name1:>14}  "
        for name2, t2 in trees:
            if name1 == name2:
                row += f"{'1.000':>14}  "
            else:
                sim = tree_similarity(t1, t2, model=model, n_iterations=50, seed=42)
                row += f"{sim:>14.3f}  "
        print(row)


if __name__ == "__main__":
    demo_basic()
    demo_ast_comparison()