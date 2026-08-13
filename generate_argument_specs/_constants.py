"""
Constants used for filtering Ansible built-in and non-variable names.
"""

# True prefixes (anything starting with these is treated as built-in).
_BUILTIN_PREFIXES = [
    "ansible_",
]

# Magic / special variables that must match exactly (not as prefixes).
_BUILTIN_EXACT = {
    "hostvars",
    "group_names",
    "groups",
    "inventory_hostname",
    "inventory_hostname_short",
    "play_hosts",
    "omit",
    "item",
    "loop",
}

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

# Name substrings that strongly suggest secret values (for no_log).
_SECRET_NAME_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
    "access_key",
    "secret_key",
    "credentials",
    "auth_key",
)
