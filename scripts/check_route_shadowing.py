"""Fail if any literal API route is unreachable because an earlier-registered
route with a path parameter matches it first.

FastAPI resolves in registration order, so `/hr/comp/{employee_id}` registered
before `/hr/comp/cycles` silently swallows the literal one: the request succeeds
with the wrong handler instead of erroring, which is how the comp-cycle and
performance-cycle list endpoints were lost. Run this as a gate.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

PARAM = re.compile(r"\{[^/}]+\}")


def segments(path):
    return [s for s in path.split("/") if s]


def shadows(earlier, later):
    """True if `earlier` (with params) matches every literal in `later`."""
    a, b = segments(earlier), segments(later)
    if len(a) != len(b):
        return False
    saw_param = False
    for seg_a, seg_b in zip(a, b):
        if PARAM.fullmatch(seg_a):
            if PARAM.fullmatch(seg_b):
                continue  # both params: not a shadowing of a literal
            saw_param = True
            continue
        if seg_a != seg_b:
            return False
    return saw_param


def main():
    import server  # noqa: F401  (registers every router at import)

    routes = []
    for r in server.app.routes:
        path, methods = getattr(r, "path", None), getattr(r, "methods", None)
        if path and methods:
            for m in methods:
                routes.append((m, path))

    problems = []
    for i, (method, path) in enumerate(routes):
        if PARAM.search(path):
            continue  # only literal routes can be victims
        for earlier_method, earlier_path in routes[:i]:
            if earlier_method == method and shadows(earlier_path, path):
                problems.append((method, path, earlier_path))
                break

    for method, path, by in problems:
        print(f"SHADOWED  {method:6} {path}\n          unreachable, matched first by {by}")

    print(f"\n{len(problems)} shadowed route(s) across {len(routes)} registered routes.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
