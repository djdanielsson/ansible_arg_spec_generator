"""CLI validation must preserve the constraints it is supposed to check."""

import pytest
import yaml

from generate_argument_specs import ArgumentSpecsGenerator, main


@pytest.mark.parametrize(
    "collection_mode", [False, True], ids=["single-role", "collection"]
)
@pytest.mark.parametrize(
    "invalid_fields",
    [
        {
            "options": {
                "app_config": {"type": "dict", "options": {"port": {"type": "invalid"}}}
            }
        },
        {
            "options": {
                "app_backends": {
                    "type": "list",
                    "elements": "dict",
                    "options": {"port": {"type": "invalid"}},
                }
            }
        },
        {"required_if": [["missing", "present", ["app_name"]]]},
        {"required_one_of": [["app_name", "missing"]]},
        {"mutually_exclusive": [["app_name", "missing"]]},
        {"required_together": [["app_name", "missing"]]},
        {"required_one_of": ""},
        {"options": {"app_name": {"type": "str", "required": "false"}}},
    ],
)
def test_cli_rejects_invalid_nested_specs_and_constraints(
    tmp_path, monkeypatch, collection_mode, invalid_fields
):
    entry = {"short_description": "Example", "options": {"app_name": {"type": "str"}}}
    entry.update(invalid_fields)
    specs_file = tmp_path / "meta/argument_specs.yml"
    if collection_mode:
        specs_file = tmp_path / "roles/example/meta/argument_specs.yml"
        (tmp_path / "roles/example/tasks").mkdir(parents=True)
    specs_file.parent.mkdir(parents=True)
    specs_file.write_text(yaml.safe_dump({"argument_specs": {"main": entry}}))
    argv = ["prog", "--validate-only"]
    argv += (
        ["--collection-path", str(tmp_path)]
        if collection_mode
        else ["--single-role", "--output", str(specs_file)]
    )
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1


@pytest.mark.parametrize(
    "document",
    [
        None,
        [],
        {},
        {"argument_specs": []},
        {"argument_specs": {"main": []}},
        {"argument_specs": {"main": {"options": []}}},
    ],
)
def test_cli_reports_malformed_documents_as_configuration_errors(
    tmp_path, monkeypatch, capsys, document
):
    path = tmp_path / "specs.yml"
    path.write_text(yaml.safe_dump(document))
    monkeypatch.setattr(
        "sys.argv", ["prog", "--single-role", "--validate-only", "-o", str(path)]
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "Could not load specs" in capsys.readouterr().out


def test_validation_accepts_valid_nested_lists_and_conditionals(tmp_path, monkeypatch):
    path = tmp_path / "specs.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "argument_specs": {
                    "main": {
                        "short_description": "Example",
                        "options": {
                            "app_name": {"type": "str"},
                            "app_backends": {
                                "type": "list",
                                "elements": "dict",
                                "options": {"port": {"type": "int"}},
                            },
                        },
                        "required_one_of": [["app_name", "app_backends"]],
                    }
                }
            }
        )
    )
    monkeypatch.setattr(
        "sys.argv", ["prog", "--single-role", "--validate-only", "-o", str(path)]
    )
    main()


def test_exclusion_removes_stale_argument_without_losing_curated_options(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks/main.yml").write_text("""- debug:
    msg: "{{ app_name }}"
""")
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta/argument_specs.yml").write_text(
        yaml.safe_dump(
            {
                "argument_specs": {
                    "main": {
                        "options": {
                            "package_entry": {"type": "str", "required": True},
                            "manual_option": {
                                "type": "int",
                                "description": "Curated",
                                "choices": [1, 2],
                            },
                        }
                    }
                }
            }
        )
    )
    gen = ArgumentSpecsGenerator(
        collection_mode=False, exclude_variables=["package_entry"]
    )
    gen.process_single_role(str(tmp_path))
    opts = gen.entry_points["main"].options
    assert set(opts) == {"app_name", "manual_option"}
    assert opts["manual_option"].description == "Curated"
    assert opts["manual_option"].choices == [1, 2]
    assert "package_entry" not in gen.generate_yaml()


def test_cli_exclusions_are_repeatable_and_apply_to_new_and_existing_options(
    tmp_path, monkeypatch
):
    role = tmp_path / "roles/example"
    (role / "tasks").mkdir(parents=True)
    (role / "tasks/main.yml").write_text(
        '- debug:\n    msg: "{{ app_name }} {{ excluded_new }}"\n'
    )
    (role / "meta").mkdir()
    (role / "meta/argument_specs.yml").write_text("""argument_specs:
  main:
    options:
      stale_loop_var:
        type: str
        required: true
""")
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--collection-path",
            str(tmp_path),
            "--exclude-variable",
            "stale_loop_var",
            "--exclude-variable",
            "excluded_new",
        ],
    )
    main()
    data = yaml.safe_load((role / "meta/argument_specs.yml").read_text())
    assert set(data["argument_specs"]["main"]["options"]) == {"app_name"}
    assert len(list((role / "meta").glob("argument_specs.yml.*.bak"))) == 1
