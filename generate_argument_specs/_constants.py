"""
Constants used for filtering Ansible built-in and non-variable names.
"""

_BUILTIN_PREFIXES = [
    "ansible_",
    "hostvars",
    "group_names",
    "groups",
    "inventory_hostname",
    "inventory_hostname_short",
    "play_hosts",
    "omit",
    "item",
    "loop",
]

_NON_VARIABLES = {
    "true",
    "false",
    "yes",
    "no",
    "on",
    "off",
    "null",
    "none",
    "and",
    "or",
    "not",
    "in",
    "is",
    "defined",
    "undefined",
    "version",
    "default",
    "production",
    "staging",
    "development",
    "undef",
    "loop_var",
    "outer_item",
    "vars",
    "playbook_dir",
    "role_path",
    "inventory_dir",
}
