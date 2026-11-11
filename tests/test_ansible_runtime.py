"""Execute generated specs with Ansible so false arguments cannot hide in unit tests.

The ordinary suite skips these tests when ansible-playbook is unavailable. CI
installs ansible-core in a dedicated job and runs this module explicitly.
"""

import os
import shutil
import subprocess
import textwrap

import pytest
import yaml

from generate_argument_specs import ArgumentSpecsGenerator

ANSIBLE_PLAYBOOK = shutil.which("ansible-playbook")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        ANSIBLE_PLAYBOOK is None, reason="ansible-core is not installed"
    ),
]


CASES = {
    "custom_loop": {"tasks/main.yml": """
        - ansible.builtin.debug:
            msg: "{{ package_entry }} {{ package_idx }}"
          loop: [alpha, beta]
          loop_control:
            loop_var: package_entry
            index_var: package_idx
    """},
    "optional_default": {"tasks/main.yml": """
        - ansible.builtin.debug:
            msg: "{{ app_message | default('hello') }}"
    """},
    "task_vars": {"tasks/main.yml": """
        - ansible.builtin.debug:
            msg: "{{ local_value }}"
          vars:
            local_value: hello
    """},
    "multiple_facts": {"tasks/main.yml": """
        - ansible.builtin.set_fact:
            first_fact: hello
            second_fact: world
        - ansible.builtin.debug:
            msg: "{{ first_fact }} {{ second_fact }}"
    """},
    "registered_result": {
        "tasks/main.yml": """
            - ansible.builtin.debug:
                msg: hello
              register: command_result
            - ansible.builtin.include_tasks: use.yml
        """,
        "tasks/use.yml": """
            - ansible.builtin.debug:
                msg: "{{ command_result }}"
        """,
    },
    "include_scope": {
        "tasks/main.yml": """
            - ansible.builtin.include_tasks: nested/use.yml
              loop: [alpha, beta]
              loop_control:
                loop_var: server_entry
              vars:
                local_value: hello
        """,
        "tasks/nested/use.yml": """
            - ansible.builtin.debug:
                msg: "{{ server_entry }} {{ local_value }}"
        """,
    },
    "guarded_input": {"tasks/main.yml": """
        - ansible.builtin.debug:
            msg: "{{ app_message }}"
          when: app_message is defined
    """},
    "unknown_types": {"tasks/main.yml": """
        - ansible.builtin.debug:
            msg: "{{ app_config.port }} {{ server_entry }}"
          loop: "{{ app_servers }}"
          loop_control:
            loop_var: server_entry
    """},
    "template_scope": {
        "tasks/main.yml": """
            - ansible.builtin.set_fact:
                computed_value: hello
            - ansible.builtin.template:
                src: app.j2
                dest: "{{ runtime_output }}"
              vars:
                local_value: hello
        """,
        "templates/app.j2": """
            {% set template_local = 'hello' %}
            {% for server in app_servers %}{{ server }}{% endfor %}
            {{ template_local }} {{ local_value }} {{ computed_value }}
        """,
    },
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_generated_spec_preserves_working_role_execution(tmp_path, case):
    role = tmp_path / "roles" / case
    for name, content in CASES[case].items():
        path = role / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")
    playbook = tmp_path / "playbook.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "localhost",
                    "gather_facts": False,
                    "connection": "local",
                    "vars": {
                        "app_config": {"port": 8080},
                        "app_servers": ["alpha", "beta"],
                        "runtime_output": str(tmp_path / "rendered.conf"),
                    },
                    "roles": [case],
                }
            ]
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\n")
    env = dict(
        os.environ,
        ANSIBLE_CONFIG=str(config),
        ANSIBLE_LOCAL_TEMP=str(tmp_path / "controller_tmp"),
        ANSIBLE_REMOTE_TEMP=str(tmp_path / "target_tmp"),
        ANSIBLE_NOCOLOR="1",
    )
    command = [ANSIBLE_PLAYBOOK, "-i", "localhost,", str(playbook)]
    baseline = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=45
    )
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr

    gen = ArgumentSpecsGenerator(collection_mode=False)
    gen.process_single_role(str(role))
    gen.save_role_specs(str(role))
    generated = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=45
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr
    if case == "template_scope":
        assert (
            (tmp_path / "rendered.conf")
            .read_text()
            .strip()
            .endswith("hello hello hello")
        )
