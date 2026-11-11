"""Find external Jinja names without evaluating templates or loading plugins."""

from dataclasses import dataclass, field
from typing import Set

from jinja2 import Environment, TemplateSyntaxError, nodes
from jinja2.visitor import NodeVisitor

_ENVIRONMENT = Environment(extensions=["jinja2.ext.do", "jinja2.ext.loopcontrols"])
_GLOBALS = set(_ENVIRONMENT.globals) | {"lookup", "query", "q", "undef", "now"}


@dataclass
class VariableUsage:
    """Track references separately from references that need a supplied value."""

    names: Set[str] = field(default_factory=set)
    required: Set[str] = field(default_factory=set)

    def update(self, other: "VariableUsage") -> None:
        self.names.update(other.names)
        self.required.update(other.required)

    def filtered(self, predicate) -> "VariableUsage":
        return VariableUsage(
            {name for name in self.names if predicate(name)},
            {name for name in self.required if predicate(name)},
        )


def root_name(node):
    """Return the variable at the root of a member/index expression."""
    while isinstance(node, (nodes.Getattr, nodes.Getitem)):
        node = node.node
    return node.name if isinstance(node, nodes.Name) else None


def defined_guards(node, truth=True) -> Set[str]:
    """Names known to be defined when an expression has the given truth value."""
    if isinstance(node, nodes.Not):
        return defined_guards(node.node, not truth)
    if isinstance(node, nodes.Test):
        name = node.name.rsplit(".", 1)[-1]
        if (name == "defined" and truth) or (name == "undefined" and not truth):
            root = root_name(node.node)
            return {root} if root else set()
    if isinstance(node, (nodes.And, nodes.Or)):
        left = defined_guards(node.left, truth)
        right = defined_guards(node.right, truth)
        if (isinstance(node, nodes.And) and truth) or (
            isinstance(node, nodes.Or) and not truth
        ):
            return left | right
        return left & right
    return set()


class _UsageVisitor(NodeVisitor):
    def __init__(
        self, bound=(), optional=(), require_defined=False, template_loader=None
    ):
        self.bound = set(bound) | _GLOBALS
        self.optional = set(optional)
        self.require_defined = require_defined
        self.template_loader = template_loader
        self.usage = VariableUsage()

    def _visit_scoped(self, body, bound=(), optional=()):
        previous_bound, previous_optional = self.bound, self.optional
        self.bound = self.bound | set(bound)
        self.optional = self.optional | set(optional)
        try:
            for child in body:
                self.visit(child)
        finally:
            self.bound, self.optional = previous_bound, previous_optional

    def _bind(self, target):
        if isinstance(target, nodes.Name):
            self.bound.add(target.name)
        elif isinstance(target, (nodes.Tuple, nodes.List)):
            for item in target.items:
                self._bind(item)

    def visit_Name(self, node, *args, **kwargs):
        if node.ctx == "load" and node.name not in self.bound:
            self.usage.names.add(node.name)
            if node.name not in self.optional:
                self.usage.required.add(node.name)

    def visit_Filter(self, node, *args, **kwargs):
        protected = set()
        if node.name.rsplit(".", 1)[-1] in {"default", "d"}:
            root = root_name(node.node)
            if root:
                protected.add(root)
        if node.node is not None:
            self._visit_scoped([node.node], optional=protected)
        for child in list(node.args) + list(node.kwargs):
            self.visit(child)
        for child in (node.dyn_args, node.dyn_kwargs):
            if child is not None:
                self.visit(child)

    def visit_Test(self, node, *args, **kwargs):
        protected = set()
        if not self.require_defined and node.name.rsplit(".", 1)[-1] in {
            "defined",
            "undefined",
        }:
            root = root_name(node.node)
            if root:
                protected.add(root)
        if node.node is not None:
            self._visit_scoped([node.node], optional=protected)
        for child in list(node.args) + list(node.kwargs):
            self.visit(child)

    def visit_And(self, node, *args, **kwargs):
        self.visit(node.left)
        self._visit_scoped([node.right], optional=defined_guards(node.left))

    def visit_Or(self, node, *args, **kwargs):
        self.visit(node.left)
        self._visit_scoped([node.right], optional=defined_guards(node.left, False))

    def visit_CondExpr(self, node, *args, **kwargs):
        self.visit(node.test)
        self._visit_scoped([node.expr1], optional=defined_guards(node.test))
        if node.expr2 is not None:
            self._visit_scoped([node.expr2], optional=defined_guards(node.test, False))

    def visit_Assign(self, node, *args, **kwargs):
        self.visit(node.node)
        self._bind(node.target)

    def visit_AssignBlock(self, node, *args, **kwargs):
        self._visit_scoped(node.body)
        if node.filter is not None:
            self.visit(node.filter)
        self._bind(node.target)

    def visit_For(self, node, *args, **kwargs):
        self.visit(node.iter)
        targets = {name.name for name in node.target.find_all(nodes.Name)}
        if isinstance(node.target, nodes.Name):
            targets.add(node.target.name)
        body = ([node.test] if node.test is not None else []) + node.body
        self._visit_scoped(body, bound=targets | {"loop"})
        self._visit_scoped(node.else_)

    def visit_If(self, node, *args, **kwargs):
        previous_bound, previous_optional = self.bound.copy(), self.optional
        branch_bindings = []
        branches = []
        fallthrough = set()
        for conditional in [node] + list(node.elif_):
            self.bound = previous_bound.copy()
            self.optional = previous_optional | fallthrough
            self.visit(conditional.test)
            branches.append(
                (conditional.body, fallthrough | defined_guards(conditional.test))
            )
            fallthrough = fallthrough | defined_guards(conditional.test, False)
        branches.append((node.else_, fallthrough))
        for body, guards in branches:
            self.bound = previous_bound.copy()
            self.optional = previous_optional | guards
            for child in body:
                self.visit(child)
            branch_bindings.append(self.bound)
        # A value assigned in every branch is local after the conditional. A
        # missing branch can still fall back to an incoming context variable.
        self.bound = set.intersection(*branch_bindings)
        self.optional = previous_optional

    def visit_Macro(self, node, *args, **kwargs):
        self.bound.add(node.name)
        self._visit_scoped(
            list(node.defaults) + node.body,
            bound={arg.name for arg in node.args} | {"varargs", "kwargs", "caller"},
        )

    def visit_CallBlock(self, node, *args, **kwargs):
        self.visit(node.call)
        self._visit_scoped(
            list(node.defaults) + node.body, bound={arg.name for arg in node.args}
        )

    def visit_With(self, node, *args, **kwargs):
        for value in node.values:
            self.visit(value)
        targets = set()
        for target in node.targets:
            if isinstance(target, nodes.Name):
                targets.add(target.name)
        self._visit_scoped(node.body, bound=targets)

    def _include_template(self, node):
        self.visit(node.template)
        if self.template_loader is None:
            return
        templates = (
            node.template.items
            if isinstance(node.template, (nodes.List, nodes.Tuple))
            else [node.template]
        )
        for template in templates:
            if isinstance(template, nodes.Const) and isinstance(template.value, str):
                with_context = getattr(node, "with_context", True)
                usage = self.template_loader(
                    template.value,
                    self.bound if with_context else _GLOBALS,
                    self.optional if with_context else set(),
                )
                if usage is not None:
                    self.usage.update(usage)
                    break

    def visit_Include(self, node, *args, **kwargs):
        self._include_template(node)

    def visit_Extends(self, node, *args, **kwargs):
        self._include_template(node)

    def visit_Import(self, node, *args, **kwargs):
        self._include_template(node)
        self.bound.add(node.target)

    def visit_FromImport(self, node, *args, **kwargs):
        self._include_template(node)
        for name in node.names:
            self.bound.add(name[1] if isinstance(name, tuple) else name)


def parse_jinja(content, expression=False):
    """Parse only: custom Ansible filters/tests need not be installed."""
    if expression and not any(marker in content for marker in ("{{", "{%", "{#")):
        content = "{{ " + content + " }}"
    return _ENVIRONMENT.parse(content)


def analyze_jinja(
    content,
    bound=(),
    optional=(),
    expression=False,
    require_defined=False,
    template_loader=None,
):
    tree = parse_jinja(content, expression)
    visitor = _UsageVisitor(bound, optional, require_defined, template_loader)
    visitor.visit(tree)
    return visitor.usage


def expression_guards(value) -> Set[str]:
    """Collect positive defined guards from a task's when conditions."""
    result: Set[str] = set()
    values = value if isinstance(value, list) else [value]
    for expression in values:
        if not isinstance(expression, str):
            continue
        try:
            tree = parse_jinja(expression, expression=True)
        except TemplateSyntaxError:
            continue
        for output in tree.body:
            if isinstance(output, nodes.Output):
                for node in output.nodes:
                    result.update(defined_guards(node))
    return result
