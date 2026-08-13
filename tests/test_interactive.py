"""
Tests for interactive mode with mocked stdin.
"""

from unittest.mock import patch

import pytest

from generate_argument_specs import ArgumentSpecsGenerator, EntryPointSpec


def _inputs(*values):
    """Return a side_effect callable that yields values then raises if over-consumed."""
    queue = list(values)

    def _next(*_args, **_kwargs):
        if not queue:
            raise AssertionError("Unexpected extra input() call")
        return queue.pop(0)

    return _next


class TestGetArgumentInteractive:
    def test_empty_name_returns_none(self):
        gen = ArgumentSpecsGenerator()
        with patch("builtins.input", side_effect=_inputs("")):
            assert gen._get_argument_interactive() is None

    def test_float_argument_default(self):
        gen = ArgumentSpecsGenerator()
        with patch(
            "builtins.input",
            side_effect=_inputs(
                "ratio",
                "float",
                "Ratio",
                "n",
                "1.5",
                "n",
                "",
            ),
        ):
            spec = gen._get_argument_interactive()
        assert spec.type == "float"
        assert spec.default == 1.5

    def test_bool_argument_with_default(self):
        gen = ArgumentSpecsGenerator()
        with patch(
            "builtins.input",
            side_effect=_inputs(
                "enable_ssl",  # name
                "bool",  # type
                "Enable SSL",  # description
                "y",  # required
                "true",  # default
                "n",  # choices
                "",  # version_added
            ),
        ):
            # required=True with default would fail validation later; interactive allows it
            spec = gen._get_argument_interactive()
        assert spec is not None
        assert spec.name == "enable_ssl"
        assert spec.type == "bool"
        assert spec.required is True
        assert spec.default is True
        assert spec.description == "Enable SSL"

    def test_int_list_dict_defaults_and_choices(self):
        gen = ArgumentSpecsGenerator()
        with patch(
            "builtins.input",
            side_effect=_inputs(
                "port",
                "int",
                "Port number",
                "n",
                "8080",
                "y",
                "80,443,8080",
                "1.2.0",
            ),
        ):
            spec = gen._get_argument_interactive()
        assert spec.type == "int"
        assert spec.default == 8080
        assert spec.choices == ["80", "443", "8080"]
        assert spec.version_added == "1.2.0"

        with patch(
            "builtins.input",
            side_effect=_inputs(
                "packages",
                "list",
                "Packages",
                "n",
                '["nginx","redis"]',
                "n",
                "str",  # elements
                "",
            ),
        ):
            list_spec = gen._get_argument_interactive()
        assert list_spec.type == "list"
        assert list_spec.default == ["nginx", "redis"]
        assert list_spec.elements == "str"

        with patch(
            "builtins.input",
            side_effect=_inputs(
                "cfg",
                "dict",
                "Config",
                "n",
                '{"a":1}',
                "n",
                "str",
                "",
            ),
        ):
            dict_spec = gen._get_argument_interactive()
        assert dict_spec.type == "dict"
        assert dict_spec.default == {"a": 1}

    def test_invalid_json_default_kept_as_string(self, capsys):
        gen = ArgumentSpecsGenerator()
        with patch(
            "builtins.input",
            side_effect=_inputs(
                "items",
                "list",
                "Items",
                "n",
                "not-json",
                "n",
                "str",
                "",
            ),
        ):
            spec = gen._get_argument_interactive()
        assert spec.default == "not-json"
        assert "Warning" in capsys.readouterr().out

    def test_invalid_int_default_returns_none(self, capsys):
        gen = ArgumentSpecsGenerator()
        with patch(
            "builtins.input",
            side_effect=_inputs(
                "count",
                "int",
                "Count",
                "n",
                "nope",
                "n",
                "",
            ),
        ):
            assert gen._get_argument_interactive() is None
        assert "Error" in capsys.readouterr().out


class TestConditionalsInteractive:
    def test_all_conditional_types(self):
        gen = ArgumentSpecsGenerator()
        ep = EntryPointSpec(name="main", short_description="t")
        with patch(
            "builtins.input",
            side_effect=_inputs(
                "y",  # required_if
                "state,present,name",
                "",  # end required_if
                "y",  # required_one_of
                "a,b",
                "",
                "y",  # mutually_exclusive
                "x,y",
                "",
                "y",  # required_together
                "p,q",
                "",
            ),
        ):
            gen._get_conditionals_interactive(ep)

        assert ep.required_if == [["state", "present", ["name"]]]
        assert ep.required_one_of == [["a", "b"]]
        assert ep.mutually_exclusive == [["x", "y"]]
        assert ep.required_together == [["p", "q"]]

    def test_skip_all_conditionals(self):
        gen = ArgumentSpecsGenerator()
        ep = EntryPointSpec(name="main", short_description="t")
        with patch("builtins.input", side_effect=_inputs("n", "n", "n", "n")):
            gen._get_conditionals_interactive(ep)
        assert ep.required_if is None
        assert ep.required_one_of is None
        assert ep.mutually_exclusive is None
        assert ep.required_together is None


class TestInteractiveMode:
    def test_full_interactive_flow_builds_entry_point(self):
        gen = ArgumentSpecsGenerator()
        with patch(
            "builtins.input",
            side_effect=_inputs(
                "main",  # entry name
                "Manage app",  # short desc
                "Line one",  # long desc
                "",  # end long desc
                "Ada <ada@example.com>",  # author
                "",  # end authors
                "y",  # add argument
                "app_name",
                "str",
                "Application name",
                "y",
                "",  # no default
                "n",  # choices
                "1.0.0",
                "n",  # no more args
                "n",
                "n",
                "n",
                "n",  # no conditionals
            ),
        ):
            gen.interactive_mode()

        assert "main" in gen.entry_points
        ep = gen.entry_points["main"]
        assert ep.short_description == "Manage app"
        assert ep.description == ["Line one"]
        assert ep.author == ["Ada <ada@example.com>"]
        assert "app_name" in ep.options
        assert ep.options["app_name"].required is True
        assert ep.options["app_name"].version_added == "1.0.0"

    def test_interactive_default_entry_name(self):
        gen = ArgumentSpecsGenerator()
        with patch(
            "builtins.input",
            side_effect=_inputs(
                "",  # default main
                "Short",
                "",  # no long desc
                "",  # no authors
                "n",  # no args
                "n",
                "n",
                "n",
                "n",
            ),
        ):
            gen.interactive_mode()
        assert "main" in gen.entry_points

    def test_interactive_keyboard_interrupt_exits(self):
        gen = ArgumentSpecsGenerator()
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc:
                gen.interactive_mode()
        assert exc.value.code == 0
