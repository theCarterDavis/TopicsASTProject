import sys
import tree_sitter_python as tspython
from tree_sitter import Language, Parser


def print_tree(node, source_code: bytes, indent: int = 0) -> None:
    """
    Recursively prints the Tree-sitter syntax tree in a readable format.

    - node: current Tree-sitter node
    - source_code: original file contents (as bytes)
    - indent: controls indentation level for pretty printing
    """
    
    prefix = "  " * indent

    #grabs the exact source text for this node
    text = source_code[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    #output stays one line per node
    text = text.replace("\n", "\\n")

    #keeps output readable
    if len(text) > 50:
        text = text[:47] + "..." #truncates long text 


    #prints node type with a some source text
    print(f"{prefix}{node.type}: {text}")

    #prints only named children - ignores punctuation
    for child in node.named_children:
        print_tree(child, source_code, indent + 1)


def main():
    """
    Entry point of the program.

    - Validates command-line arguments
    - Reads a Python file
    - Uses Tree-sitter to parse it
    - Prints the resulting syntax tree
    """

    #ensures only argument is provided (filename)
    if len(sys.argv) != 2:
        print("Usage: python parse.py <python_file>")
        sys.exit(1)

    filename = sys.argv[1]

    #reads files as bytes because tree-sitter uses bytes not strings
    with open(filename, "rb") as f:
        source_code = f.read()

    #loads python grammar
    py_language = Language(tspython.language())

    #creates a python parser and parses code into an AST
    parser = Parser(py_language)
    tree = parser.parse(source_code)

    #prints the tree
    print(f"Parse tree for {filename}:\n")
    print_tree(tree.root_node, source_code)


if __name__ == "__main__":
    main()