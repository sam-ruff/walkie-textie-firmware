"""A small reader and writer for KiCad's S-expression files.

A list is a Python list whose first item is its keyword. Quoted strings come
back as `Q` so they are written with quotes again; everything else is a plain
`str` atom.
"""


class Q(str):
    """A string that was, or must be, written in double quotes."""


def parse(text):
    pos = 0
    n = len(text)
    stack = [[]]
    while pos < n:
        ch = text[pos]
        if ch in " \t\r\n":
            pos += 1
        elif ch == "(":
            stack.append([])
            pos += 1
        elif ch == ")":
            done = stack.pop()
            stack[-1].append(done)
            pos += 1
        elif ch == '"':
            pos += 1
            out = []
            while text[pos] != '"':
                if text[pos] == "\\":
                    pos += 1
                    out.append({"n": "\n", "t": "\t", "r": "\r"}.get(text[pos], text[pos]))
                else:
                    out.append(text[pos])
                pos += 1
            pos += 1
            stack[-1].append(Q("".join(out)))
        else:
            start = pos
            while pos < n and text[pos] not in ' \t\r\n()"':
                pos += 1
            stack[-1].append(text[start:pos])
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError("unbalanced S-expression")
    return stack[0][0]


def quote(value):
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def atom(value):
    if isinstance(value, Q):
        return quote(value)
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return "0" if text in ("-0", "") else text
    return str(value)


def dump(node, depth=0):
    """One list per line, nested lists indented with tabs, the way KiCad writes them."""
    pad = "\t" * depth
    if not isinstance(node, list):
        return pad + atom(node)
    simple = all(not isinstance(item, list) for item in node)
    if simple:
        return pad + "(" + " ".join(atom(item) for item in node) + ")"
    head = [atom(item) for item in node if not isinstance(item, list)]
    lines = [pad + "(" + " ".join(head)]
    lines += [dump(item, depth + 1) for item in node if isinstance(item, list)]
    lines.append(pad + ")")
    return "\n".join(lines)


def find(node, key):
    """First child list with this keyword, or None."""
    return next((item for item in node if isinstance(item, list) and item and item[0] == key), None)


def find_all(node, key):
    return [item for item in node if isinstance(item, list) and item and item[0] == key]
