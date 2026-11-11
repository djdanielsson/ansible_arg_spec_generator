"""Follow task execution order and the scopes passed to included task files."""

import re
from pathlib import Path

import yaml
from jinja2 import TemplateSyntaxError

from ._jinja_analysis import VariableUsage, analyze_jinja, expression_guards

_INCLUDE_MODULES = {"include_tasks", "import_tasks", "include", "import_playbook"}
_BLOCKS = {"block", "rescue", "always"}
_CONDITIONS = {"when", "until", "changed_when", "failed_when"}


def module_name(name):
    return name.rsplit(".", 1)[-1] if isinstance(name, str) else ""


def walk_tasks(tasks):
    """Walk actual task lists, including block/rescue/always sections."""
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        yield task
        for section in _BLOCKS:
            yield from walk_tasks(task.get(section))


def include_target(task):
    for key, value in task.items():
        if module_name(key) in _INCLUDE_MODULES:
            if isinstance(value, dict):
                value = value.get("file")
            if isinstance(value, str) and not any(
                marker in value for marker in ("{{", "{%", "{#")
            ):
                return value.strip()
    return None


def task_file_key(path, tasks_dir):
    relative = path.relative_to(tasks_dir)
    if relative.suffix in {".yml", ".yaml"}:
        relative = relative.with_suffix("")
    return relative.as_posix()


class TaskAnalyzer:
    def __init__(self, generator, role_dir=None):
        self.generator = generator
        self.role_dir = role_dir
        self.tasks_dir = role_dir / "tasks" if role_dir is not None else None
        self.templates_dir = role_dir / "templates" if role_dir is not None else None
        self.cache = {}
        self.referenced_templates = set()
        self.template_usage = VariableUsage()

    def load(self, path):
        if path not in self.cache:
            try:
                with open(path, "r", encoding="utf-8") as stream:
                    content = stream.read()
                self.generator._analyze_variable_usage_context(content, path)
                try:
                    tasks = yaml.safe_load(content)
                except yaml.YAMLError:
                    tasks = None
                self.cache[path] = (content, tasks)
            except (OSError, UnicodeError) as error:
                self.generator.log_verbose(f"Could not read task file {path}: {error}")
                self.cache[path] = ("", None)
        return self.cache[path]

    def resolve_include(self, target, parent):
        """Resolve paths relative to the including file, then its task ancestors."""
        if not target:
            return None
        candidates = [parent / target]
        if self.tasks_dir is not None:
            for directory in parent.parents:
                if directory == self.tasks_dir or self.tasks_dir in directory.parents:
                    candidates.append(directory / target)
                if directory == self.tasks_dir:
                    break
            candidates.append(self.tasks_dir / target)
        for candidate in candidates:
            paths = [candidate]
            if not candidate.suffix:
                paths = [
                    candidate.with_suffix(".yml"),
                    candidate.with_suffix(".yaml"),
                    candidate,
                ]
            for path in paths:
                if path.is_file():
                    return path.resolve()
        return None

    def value_usage(
        self,
        value,
        bound=(),
        optional=(),
        expression=False,
        assertion=False,
        template_loader=None,
    ):
        usage = VariableUsage()
        if isinstance(value, str):
            try:
                usage.update(
                    analyze_jinja(
                        value,
                        bound,
                        optional,
                        expression=expression,
                        require_defined=assertion,
                        template_loader=template_loader,
                    )
                )
            except TemplateSyntaxError as error:
                self.generator.log_verbose(f"Could not parse Jinja expression: {error}")
                # One malformed interpolation must not hide independent valid
                # references elsewhere in the same YAML scalar.
                for fragment in re.findall(r"\{\{.*?\}\}", value, re.DOTALL):
                    try:
                        usage.update(analyze_jinja(fragment, bound, optional))
                    except TemplateSyntaxError:
                        continue
        elif isinstance(value, dict):
            for key, child in value.items():
                usage.update(self.value_usage(key, bound, optional))
                usage.update(
                    self.value_usage(child, bound, optional, expression, assertion)
                )
        elif isinstance(value, (list, tuple)):
            for child in value:
                usage.update(
                    self.value_usage(child, bound, optional, expression, assertion)
                )
        return usage

    def analyze_file(
        self, path, bound=(), known=None, optional=(), follow_includes=True, stack=()
    ):
        try:
            path = path.resolve()
        except OSError as error:
            self.generator.log_verbose(f"Could not resolve task file {path}: {error}")
            return VariableUsage()
        if path in stack:
            return VariableUsage()
        known = set() if known is None else known
        content, tasks = self.load(path)
        if not isinstance(tasks, list):
            # Recover complete Jinja expressions from malformed YAML, without
            # interpreting comments and literal words as task declarations.
            usage = VariableUsage()
            for expression in re.findall(r"\{\{.*?\}\}", content, re.DOTALL):
                usage.update(self.value_usage(expression, set(bound) | known, optional))
            return usage.filtered(self.generator._is_valid_role_variable)
        usage = self.analyze_tasks(
            tasks,
            path,
            set(bound),
            known,
            set(optional),
            follow_includes,
            stack + (path,),
        )
        return usage.filtered(self.generator._is_valid_role_variable)

    def analyze_template(self, path, bound=(), optional=(), stack=()):
        path = path.resolve()
        if path in stack:
            return VariableUsage()
        self.referenced_templates.add(path)

        def load_template(name, child_bound, child_optional):
            roots = (
                [self.templates_dir, path.parent]
                if self.templates_dir
                else [path.parent]
            )
            for directory in roots:
                child = directory / name
                if child.is_file():
                    return self.analyze_template(
                        child, child_bound, child_optional, stack + (path,)
                    )
            return None

        try:
            with open(path, "r", encoding="utf-8") as stream:
                content = stream.read()
            usage = self.value_usage(
                content, bound, optional, template_loader=load_template
            )
            self.template_usage.update(
                usage.filtered(self.generator._is_valid_role_variable)
            )
            return usage
        except (OSError, UnicodeError) as error:
            self.generator.log_verbose(f"Could not read template {path}: {error}")
            return VariableUsage()

    def analyze_tasks(
        self, tasks, path, bound, known, optional, follow_includes, stack
    ):
        usage = VariableUsage()
        if not isinstance(tasks, list):
            return usage
        for task in tasks:
            if not isinstance(task, dict):
                continue
            local_vars = task.get("vars", {})
            local_vars = local_vars if isinstance(local_vars, dict) else {}
            local_names = set(local_vars)
            scope = bound | known | local_names
            loop = "loop" in task or any(
                isinstance(key, str) and key.startswith("with_") for key in task
            )
            for key, value in task.items():
                if key == "loop" or (isinstance(key, str) and key.startswith("with_")):
                    usage.update(self.value_usage(value, scope, optional))
            control = task.get("loop_control", {})
            control = control if isinstance(control, dict) else {}
            if loop:
                loop_var = control.get("loop_var", "item")
                index_var = control.get("index_var")
                scope = scope | {
                    name for name in (loop_var, index_var) if isinstance(name, str)
                }

            guarded = set(optional)
            conditions = task.get("when", [])
            conditions = conditions if isinstance(conditions, list) else [conditions]
            for condition in conditions:
                usage.update(
                    self.value_usage(condition, scope, guarded, expression=True)
                )
                guarded.update(expression_guards(condition))
            # Task vars are lazy and can refer to the current loop item. Sibling
            # definitions are local, while a self reference needs an incoming value.
            for name, value in local_vars.items():
                usage.update(self.value_usage(value, scope - {name}, guarded))
            registered = task.get("register")
            fact_names = set()
            for key, value in task.items():
                if module_name(key) == "set_fact" and isinstance(value, dict):
                    fact_names.update(name for name in value if name != "cacheable")
            post_scope = (
                scope
                | fact_names
                | ({registered} if isinstance(registered, str) else set())
            )
            for key in ("until", "changed_when", "failed_when"):
                usage.update(
                    self.value_usage(
                        task.get(key), post_scope, guarded, expression=True
                    )
                )
            for key, value in control.items():
                if key not in {"loop_var", "index_var"}:
                    usage.update(
                        self.value_usage(
                            value, scope, guarded, expression=(key == "break_when")
                        )
                    )

            for key, value in task.items():
                if key in _BLOCKS | _CONDITIONS | {
                    "vars",
                    "loop",
                    "loop_control",
                    "register",
                }:
                    continue
                if isinstance(key, str) and key.startswith("with_"):
                    continue
                short_name = module_name(key)
                if short_name == "assert" and isinstance(value, dict):
                    for param, argument in value.items():
                        usage.update(
                            self.value_usage(
                                argument,
                                scope,
                                guarded,
                                expression=(param == "that"),
                                assertion=(param == "that"),
                            )
                        )
                elif short_name == "debug" and isinstance(value, dict):
                    for param, argument in value.items():
                        usage.update(
                            self.value_usage(
                                argument, scope, guarded, expression=(param == "var")
                            )
                        )
                else:
                    usage.update(self.value_usage(value, scope, guarded))
                if (
                    short_name == "template"
                    and isinstance(value, dict)
                    and self.templates_dir is not None
                ):
                    source = value.get("src")
                    if isinstance(source, str) and not any(
                        marker in source for marker in ("{{", "{%", "{#")
                    ):
                        template = (self.templates_dir / source).resolve()
                        if template.is_file():
                            self.referenced_templates.add(template)
                            usage.update(
                                self.analyze_template(template, scope, guarded)
                            )

            # Included tasks see loop/task-local variables and previously created
            # host variables. Host variables assigned by the include persist.
            target = include_target(task)
            if target and follow_includes:
                included = self.resolve_include(target, path.parent)
                if included is not None:
                    include_known = known.copy()
                    usage.update(
                        self.analyze_file(
                            included,
                            scope,
                            include_known,
                            guarded,
                            follow_includes,
                            stack,
                        )
                    )
                    if "when" not in task:
                        known.update(include_known)

            if isinstance(task.get("block"), list):
                block_known = known.copy()
                usage.update(
                    self.analyze_tasks(
                        task["block"],
                        path,
                        scope,
                        block_known,
                        guarded,
                        follow_includes,
                        stack,
                    )
                )
                if isinstance(task.get("rescue"), list):
                    rescue_known = known.copy()
                    usage.update(
                        self.analyze_tasks(
                            task["rescue"],
                            path,
                            scope,
                            rescue_known,
                            guarded,
                            follow_includes,
                            stack,
                        )
                    )
                    block_known.intersection_update(rescue_known)
                usage.update(
                    self.analyze_tasks(
                        task.get("always"),
                        path,
                        scope,
                        block_known,
                        guarded,
                        follow_includes,
                        stack,
                    )
                )
                if "when" not in task:
                    known.update(block_known)
            # Ansible registers a result even for a task skipped by when.
            if isinstance(registered, str):
                known.add(registered)
            if "when" not in task:
                known.update(fact_names)
        return usage
