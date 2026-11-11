"""Regression tests for false arguments, missing dependencies, and optionality."""

import textwrap

import pytest
import yaml

from generate_argument_specs import ArgumentSpecsGenerator
from generate_argument_specs._jinja_analysis import analyze_jinja


@pytest.fixture
def build_role(tmp_path):
    def build(files):
        role = tmp_path / "role"
        (role / "tasks").mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            path = role / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content), encoding="utf-8")
        gen = ArgumentSpecsGenerator(collection_mode=False)
        gen.process_single_role(str(role))
        return gen

    return build


@pytest.mark.parametrize("loop_keyword", ["loop", "with_items"])
def test_custom_loop_and_index_are_local(build_role, loop_keyword):
    gen = build_role({"tasks/main.yml": f"""
        - debug:
            msg: "{{{{ package_entry.name }}}} {{{{ package_index }}}}"
          {loop_keyword}: "{{{{ app_packages }}}}"
          when: package_entry.enabled
          loop_control:
            loop_var: package_entry
            index_var: package_index
            label: "{{{{ package_entry.name }}}}"
    """})
    assert set(gen.entry_points["main"].options) == {"app_packages"}


def test_loop_binding_does_not_hide_external_use_in_another_task(build_role):
    gen = build_role({"tasks/main.yml": """
        - debug:
            msg: "{{ package_entry }}"
          loop: [one]
          loop_control:
            loop_var: package_entry
        - debug:
            msg: "{{ package_entry }}"
    """})
    assert set(gen.entry_points["main"].options) == {"package_entry"}
    assert gen.entry_points["main"].options["package_entry"].required


def test_include_inherits_loop_and_task_vars(build_role):
    gen = build_role(
        {
            "tasks/main.yml": """
            - ansible.builtin.include_tasks:
                file: nested/setup.yml
              loop: "{{ app_servers }}"
              loop_control:
                loop_var: server_entry
                index_var: server_index
              vars:
                local_alias: "{{ app_name }}"
        """,
            "tasks/nested/setup.yml": """
            - debug:
                msg: "{{ server_entry.name }} {{ server_index }} {{ local_alias }} {{ app_port }}"
        """,
        }
    )
    assert set(gen.entry_points) == {"main"}
    assert set(gen.entry_points["main"].options) == {
        "app_servers",
        "app_name",
        "app_port",
    }


def test_shared_include_is_analyzed_for_each_call_scope(build_role):
    gen = build_role(
        {
            "tasks/main.yml": """
            - include_tasks: helper.yml
              vars:
                local_value: hello
            - include_tasks: helper.yml
        """,
            "tasks/helper.yml": '- debug:\n    msg: "{{ local_value }}"\n',
        }
    )
    assert set(gen.entry_points["main"].options) == {"local_value"}
    assert gen.entry_points["main"].options["local_value"].required


def test_task_vars_and_block_vars_do_not_become_inputs(build_role):
    gen = build_role({"tasks/main.yml": """
        - block:
            - debug:
                msg: "{{ local_value }} {{ local_alias }}"
              vars:
                local_alias: "{{ local_value }}"
          vars:
            local_value: "{{ app_name }}"
    """})
    assert set(gen.entry_points["main"].options) == {"app_name"}


@pytest.mark.parametrize("module", ["set_fact", "ansible.builtin.set_fact"])
def test_all_fact_assignments_and_registered_results_cross_files(build_role, module):
    gen = build_role(
        {
            "tasks/main.yml": f"""
            - {module}:
                first_fact: "{{{{ app_name }}}}"
                second_fact: hello
            - include_tasks: producer.yml
            - include_tasks: consumer.yml
        """,
            "tasks/producer.yml": """
            - debug:
                msg: hello
              register: command_result
        """,
            "tasks/consumer.yml": """
            - debug:
                msg: "{{ first_fact }} {{ second_fact }} {{ command_result.msg }} {{ stdout }}"
        """,
        }
    )
    assert set(gen.entry_points["main"].options) == {"app_name", "stdout"}


def test_register_available_to_own_postconditions(build_role):
    gen = build_role({"tasks/main.yml": """
        - command: echo hello
          register: command_result
          changed_when: command_result.rc != 0
          failed_when: command_result.failed
          until: command_result.rc == app_expected_rc
    """})
    assert set(gen.entry_points["main"].options) == {"app_expected_rc"}


def test_prior_external_read_is_not_hidden_by_later_assignment(build_role):
    gen = build_role({"tasks/main.yml": """
        - debug:
            msg: "{{ computed_value }}"
        - set_fact:
            computed_value: hello
    """})
    assert set(gen.entry_points["main"].options) == {"computed_value"}
    assert gen.entry_points["main"].options["computed_value"].required


def test_facts_from_other_entrypoint_do_not_hide_inputs(build_role):
    gen = build_role(
        {
            "tasks/main.yml": "- set_fact:\n    computed_value: hello\n",
            "tasks/standalone.yml": '- debug:\n    msg: "{{ computed_value }}"\n',
        }
    )
    assert set(gen.entry_points["main"].options) == set()
    assert set(gen.entry_points["standalone"].options) == {"computed_value"}


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("{{ app_config.port }}", {"app_config"}),
        ("{{ app_config['port'] }}", {"app_config"}),
        ("{{ app_config[app_key] }}", {"app_config", "app_key"}),
        ("{{ app_port + app_offset }}", {"app_port", "app_offset"}),
        ("{{ app_value | default(app_fallback) }}", {"app_value", "app_fallback"}),
        (
            "{{ app_value | my.collection.custom_filter(extra_value) }}",
            {"app_value", "extra_value"},
        ),
        ("{{ lookup('env', app_env_key) }}", {"app_env_key"}),
    ],
)
def test_expression_dependencies_are_exact(build_role, expression, expected):
    content = yaml.safe_dump([{"debug": {"msg": expression}}])
    gen = build_role({"tasks/main.yml": content})
    assert set(gen.entry_points["main"].options) == expected


@pytest.mark.parametrize(
    "condition, expected",
    [
        ("app_enabled", {"app_enabled"}),
        ("app_enabled | bool", {"app_enabled"}),
        ("app_enabled and app_ready", {"app_enabled", "app_ready"}),
        ("app_config.enabled", {"app_config"}),
        (
            "app_version is my.collection.custom_test(expected_version)",
            {"app_version", "expected_version"},
        ),
    ],
)
def test_implicit_condition_expressions(build_role, condition, expected):
    gen = build_role(
        {
            "tasks/main.yml": yaml.safe_dump(
                [{"debug": {"msg": "hello"}, "when": condition}]
            )
        }
    )
    assert set(gen.entry_points["main"].options) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "{{ app_message | default('hello') }}",
        "{{ app_message | d('hello') }}",
        "{{ app_message | ansible.builtin.default('hello') }}",
        "{{ app_message if app_message is defined else 'hello' }}",
    ],
)
def test_fallback_does_not_require_input(build_role, expression):
    gen = build_role(
        {"tasks/main.yml": yaml.safe_dump([{"debug": {"msg": expression}}])}
    )
    assert set(gen.entry_points["main"].options) == {"app_message"}
    assert gen.entry_points["main"].options["app_message"].required is False


def test_fallback_variable_is_required_and_unguarded_use_wins(build_role):
    gen = build_role({"tasks/main.yml": """
        - debug:
            msg: "{{ app_message | default(app_fallback) }}"
        - debug:
            msg: "{{ app_message }}"
    """})
    assert {
        name
        for name, option in gen.entry_points["main"].options.items()
        if option.required
    } == {"app_message", "app_fallback"}


@pytest.mark.parametrize(
    "when",
    [
        "app_message is defined",
        "app_message is not undefined",
        "app_message is defined and app_message | length > 0",
    ],
)
def test_defined_guard_keeps_reference_optional(build_role, when):
    gen = build_role(
        {
            "tasks/main.yml": yaml.safe_dump(
                [{"debug": {"msg": "{{ app_message }}"}, "when": when}]
            )
        }
    )
    assert set(gen.entry_points["main"].options) == {"app_message"}
    assert not gen.entry_points["main"].options["app_message"].required


def test_assert_defined_is_an_explicit_requirement(build_role):
    gen = build_role({"tasks/main.yml": """
        - ansible.builtin.assert:
            that:
              - app_name is defined
    """})
    assert gen.entry_points["main"].options["app_name"].required


def test_jinja_locals_and_template_call_scope(build_role):
    gen = build_role(
        {
            "tasks/main.yml": """
            - set_fact:
                computed_value: hello
            - template:
                src: app.j2
                dest: /tmp/app
              loop: "{{ app_servers }}"
              loop_control:
                loop_var: server_entry
              vars:
                local_value: hello
        """,
            "templates/app.j2": """
            {% set template_local = 'hello' %}
            {% macro render(value) %}{{ value }} {{ app_suffix }}{% endmacro %}
            {% for server in app_backends %}
            {{ server.name }} {{ loop.index }} {{ render(server) }}
            {% endfor %}
            {{ template_local }} {{ computed_value }} {{ local_value }} {{ server_entry }}
        """,
        }
    )
    assert set(gen.entry_points["main"].options) == {
        "app_servers",
        "app_backends",
        "app_suffix",
    }


def test_jinja_assignment_scope_and_external_same_name():
    usage = analyze_jinja(
        "{% for server in app_servers %}{{ server }}{% endfor %}{{ server }}"
    )
    assert usage.names == {"app_servers", "server"}
    assert usage.required == usage.names


def test_jinja_optional_access_and_local_imports():
    usage = analyze_jinja("""
        {% from 'macros.j2' import render as local_render %}
        {% with local_value = app_value | default('hello') %}{{ local_render(local_value) }}{% endwith %}
        {% if app_config is defined %}{{ app_config.port }}{% endif %}
    """)
    assert usage.names == {"app_value", "app_config"}
    assert usage.required == set()


def test_unused_template_does_not_require_arguments(build_role):
    gen = build_role(
        {"tasks/main.yml": "[]", "templates/unused.j2": "{{ unused_value }}"}
    )
    assert set(gen.entry_points["main"].options) == {"unused_value"}
    assert not gen.entry_points["main"].options["unused_value"].required


def test_role_vars_are_available_before_validation(build_role):
    gen = build_role(
        {
            "tasks/main.yml": '- debug:\n    msg: "{{ app_state }}"\n',
            "vars/main.yml": "app_state: present\n",
        }
    )
    assert set(gen.entry_points["main"].options) == {"app_state"}
    assert not gen.entry_points["main"].options["app_state"].required


def test_valid_names_are_not_treated_as_literal_values(build_role):
    gen = build_role(
        {
            "tasks/main.yml": '- debug:\n    msg: "{{ version }} {{ default }} {{ production }} {{ outer_item }}"\n'
        }
    )
    assert set(gen.entry_points["main"].options) == {
        "version",
        "default",
        "production",
        "outer_item",
    }


def test_comments_and_literal_conditions_do_not_create_arguments(build_role):
    gen = build_role({"tasks/main.yml": """
        # {{ commented_value }}
        - debug:
            msg: "literal_value is defined"
          when: "app_mode == 'production'"
    """})
    assert set(gen.entry_points["main"].options) == {"app_mode"}


def test_lazy_task_var_can_reference_loop_item(build_role):
    gen = build_role({"tasks/main.yml": """
        - debug:
            msg: "{{ local_name }}"
          vars:
            local_name: "{{ server_entry.name }}"
          loop: "{{ app_servers }}"
          loop_control:
            loop_var: server_entry
    """})
    assert set(gen.entry_points["main"].options) == {"app_servers"}


def test_when_list_guards_later_conditions_and_lazy_vars(build_role):
    gen = build_role({"tasks/main.yml": """
        - debug:
            msg: "{{ local_value }}"
          vars:
            local_value: "{{ app_config.port }}"
          when:
            - app_config is defined
            - app_config.enabled
    """})
    assert set(gen.entry_points["main"].options) == {"app_config"}
    assert not gen.entry_points["main"].options["app_config"].required


def test_always_assignments_are_available_after_block(build_role):
    gen = build_role({"tasks/main.yml": """
        - block:
            - debug:
                msg: hello
          always:
            - set_fact:
                computed_value: hello
        - debug:
            msg: "{{ computed_value }}"
    """})
    assert set(gen.entry_points["main"].options) == set()


def test_facts_are_available_to_own_postconditions(build_role):
    gen = build_role({"tasks/main.yml": """
        - set_fact:
            computed_value: hello
          changed_when: computed_value != 'hello'
    """})
    assert set(gen.entry_points["main"].options) == set()


def test_jinja_include_inherits_lexical_loop_scope(build_role):
    gen = build_role(
        {
            "tasks/main.yml": "- template:\n    src: app.j2\n    dest: /tmp/app\n",
            "templates/app.j2": "{% for server in app_servers %}{% include 'partial.j2' %}{% endfor %}",
            "templates/partial.j2": "{{ server.name }} {{ app_suffix }}",
        }
    )
    assert set(gen.entry_points["main"].options) == {"app_servers", "app_suffix"}
    assert all(option.required for option in gen.entry_points["main"].options.values())


def test_jinja_conditional_assignments_do_not_hide_other_branches():
    usage = analyze_jinja(
        "{% if app_enabled %}{% set local_value = 'hello' %}{% else %}{{ local_value }}{% endif %}"
    )
    assert usage.names == {"app_enabled", "local_value"}
    assert usage.required == usage.names


def test_jinja_assignment_in_all_branches_is_local():
    usage = analyze_jinja(
        "{% if app_enabled %}{% set local_value = 'hello' %}{% else %}{% set local_value = 'world' %}{% endif %}{{ local_value }}"
    )
    assert usage.names == {"app_enabled"}


def test_jinja_tuple_and_capture_assignments_are_local():
    usage = analyze_jinja(
        "{% set left, right = app_pair %}{% set local_value | upper %}{{ app_name }}{% endset %}{{ local_value }} {{ left }} {{ right }}"
    )
    assert usage.names == {"app_pair", "app_name"}


def test_jinja_elif_retains_guards_from_previous_branches():
    usage = analyze_jinja(
        "{% if app_config is not defined %}none{% elif app_config.enabled %}{{ app_config.port }}{% endif %}"
    )
    assert usage.names == {"app_config"}
    assert usage.required == set()
