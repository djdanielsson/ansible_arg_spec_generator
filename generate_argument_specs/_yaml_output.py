"""
Mixin class for YAML generation and file output.
"""

import os
from pathlib import Path

import yaml


class YamlOutputMixin:
    """Methods for generating YAML output and saving to files."""

    def generate_yaml(self) -> str:
        """Generate the YAML content for argument_specs.yml"""
        if not self.entry_points:
            return "---\nargument_specs: {}\n...\n"

        specs = {
            "argument_specs": {
                name: entry_point.to_dict()
                for name, entry_point in self.entry_points.items()
            }
        }

        class CustomDumper(yaml.SafeDumper):
            def write_line_break(self, data=None):
                super().write_line_break(data)
                if len(self.indents) == 1:
                    super().write_line_break()

            def increase_indent(self, flow=False, indentless=False):
                return super().increase_indent(flow, False)

            def ignore_aliases(self, data):
                return True

        yaml_content = yaml.dump(
            specs,
            Dumper=CustomDumper,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
            width=120,
            allow_unicode=True,
        )

        return f"---\n{yaml_content}...\n"

    def save_to_file(self, output_file: str):
        """Save the generated specs to a file"""
        yaml_content = self.generate_yaml()

        if self.dry_run:
            self.log_info(
                f"Dry run: would write to {output_file}", role_prefix=False
            )
            return

        dir_name = os.path.dirname(output_file)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(output_file, "w") as f:
            f.write(yaml_content)

        self.log_info(f"Argument specs saved to: {output_file}", role_prefix=False)

    def save_role_specs(self, role_path: str, role_name: str = None):
        """Save argument specs for a single role"""
        if role_name is None:
            role_name = Path(role_path).name

        if not self.entry_points:
            self.log_verbose(f"No entry points found for role {role_name}")
            return

        output_file = Path(role_path) / "meta" / "argument_specs.yml"
        yaml_content = self.generate_yaml()

        if self.dry_run:
            self.log_verbose(f"Dry run: would write to {output_file}")
            return

        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w") as f:
                f.write(yaml_content)

            self.log_verbose(f"Saved argument specs to: {output_file}")

        except Exception as e:
            self.log_error(f"Error saving specs for role {role_name}: {e}")

    def save_all_role_specs(self, collection_path: str = "."):
        """Save argument specs for all processed roles"""
        for role_name in self.processed_roles:
            role_path = Path(collection_path) / "roles" / role_name
            self.save_role_specs(str(role_path), role_name)
