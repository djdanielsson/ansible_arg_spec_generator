# Test Suite for ansible-argument-spec-generator

This directory contains comprehensive tests for the ansible-argument-spec-generator package.

## Test Structure

### Test Files

- **`test_basic.py`** - Basic smoke tests to verify core functionality
- **`test_argument_spec.py`** - Tests for ArgumentSpec and EntryPointSpec classes
- **`test_generator_core.py`** - Tests for ArgumentSpecsGenerator core functionality
- **`test_variable_extraction.py`** - Tests for variable extraction and file parsing
- **`test_integration.py`** - Integration tests for complete workflows
- **`test_edge_cases.py`** - Edge cases and error handling tests
- **`test_type_inference.py`** - Tests for type inference and smart descriptions

### Support Files

- **`conftest.py`** - pytest configuration and shared fixtures
- **`test_runner.py`** - Custom test runner script
- **`README.md`** - This documentation

## Running Tests

### Prerequisites

Install test dependencies:

```bash
# Install with test dependencies
pip install -e ".[test]"

# Or install with development dependencies
pip install -e ".[dev]"
```

### Running All Tests

**Using pytest (recommended):**
```bash
# From project root
pytest tests/ -v

# With coverage
pytest tests/ --cov=generate_argument_specs --cov-report=html

# Run specific test file
pytest tests/test_basic.py -v
```

**Using the custom test runner:**
```bash
# From project root
python tests/test_runner.py

# Run only basic smoke tests
python tests/test_runner.py --basic
```

**Running tests directly:**
```bash
# Run basic tests directly
python tests/test_basic.py
```

### Test Categories

#### Smoke Tests (`test_basic.py`)
Quick verification that basic functionality works:
- Package imports correctly
- Classes can be instantiated
- Basic YAML generation works
- Core methods don't crash

Run these first to catch major issues:
```bash
python tests/test_runner.py --basic
```

#### Unit Tests
Detailed testing of individual components:
- **ArgumentSpec/EntryPointSpec** (`test_argument_spec.py`)
- **Generator core methods** (`test_generator_core.py`)  
- **Variable extraction** (`test_variable_extraction.py`)
- **Type inference** (`test_type_inference.py`)

#### Integration Tests (`test_integration.py`)
End-to-end testing of complete workflows:
- Collection mode processing
- Single role mode processing
- Command line interface
- File generation

#### Edge Cases (`test_edge_cases.py`)
Robustness testing:
- Malformed YAML files
- Unicode handling
- Large files
- Error recovery
- Performance edge cases

## Test Fixtures

The test suite uses comprehensive fixtures defined in `conftest.py`:

### Temporary Directories
- `temp_dir` - Clean temporary directory for each test
- Automatically cleaned up after each test

### Sample Structures
- `sample_collection_structure` - Complete Ansible collection with roles
- `sample_single_role` - Single role structure for testing
- Created with realistic defaults, tasks, and meta files

### Mock Data
- `sample_argument_spec` - Pre-configured ArgumentSpec for testing
- `sample_entry_point_spec` - Pre-configured EntryPointSpec for testing
- `mock_yaml_files` - Various YAML files (valid, invalid, empty)
- `complex_task_content` - Complex task file content for variable extraction

### Generators
- `generator` - Basic ArgumentSpecsGenerator instance
- `generator_verbose` - Generator with high verbosity for debugging

## Test Coverage

The test suite aims for comprehensive coverage of:

### Core Functionality
- ✅ Class initialization and configuration
- ✅ YAML generation and formatting
- ✅ File reading and parsing
- ✅ Variable extraction from tasks
- ✅ Type inference and smart descriptions
- ✅ Collection and role detection
- ✅ Metadata extraction
- ✅ Error handling and recovery

### File Handling
- ✅ Valid YAML files
- ✅ Invalid/malformed YAML
- ✅ Empty files
- ✅ Binary files
- ✅ Unicode content
- ✅ Large files
- ✅ Missing files
- ✅ Permission errors

### Variable Detection
- ✅ Jinja2 template variables
- ✅ Complex expressions with filters
- ✅ Conditional statements (when, failed_when)
- ✅ Assert statements
- ✅ Loop constructs
- ✅ Include/import statements
- ✅ Registered variable filtering
- ✅ Ansible built-in filtering

### Type Inference
- ✅ Path detection (_path, _dir, _file)
- ✅ Boolean detection (_enabled, debug_, force_)
- ✅ Numeric types (int, float)
- ✅ Collection types (list, dict)
- ✅ Smart descriptions based on patterns

### Output Quality
- ✅ Valid YAML structure
- ✅ Alphabetical sorting
- ✅ No reference anchors
- ✅ Unicode handling
- ✅ Data type preservation
- ✅ Proper document markers (--- and ...)

## Writing New Tests

### Test Naming Convention
- Test files: `test_<component>.py`
- Test functions: `test_<functionality>`
- Test classes: `Test<Component>`

### Using Fixtures
```python
def test_my_functionality(sample_collection_structure, generator):
    """Test description"""
    # Use the fixtures
    analysis = generator.analyze_role_structure(str(sample_collection_structure))
    assert analysis is not None
```

### Testing Error Conditions
```python
def test_handles_invalid_yaml(temp_dir):
    """Test graceful handling of invalid YAML"""
    # Create invalid file
    invalid_file = temp_dir / "invalid.yml"
    with open(invalid_file, "w") as f:
        f.write("invalid: yaml: content")
    
    generator = ArgumentSpecsGenerator()
    
    # Should not crash
    result = generator.extract_variables_from_task_file(invalid_file)
    assert isinstance(result, set)  # Should return empty set
```

### Testing Output
```python
def test_yaml_output_format(generator):
    """Test YAML output formatting"""
    # Set up generator with data
    entry_point = EntryPointSpec(name="test")
    generator.add_entry_point(entry_point)
    
    # Generate and verify
    yaml_content = generator.generate_yaml()
    
    assert yaml_content.startswith("---")
    assert yaml_content.endswith("...\n")
    
    # Parse to verify structure
    import yaml
    parsed = yaml.safe_load(yaml_content)
    assert "argument_specs" in parsed
```

## Debugging Tests

### Verbose Output
```bash
# Run with verbose pytest output
pytest tests/ -v -s

# Run specific test with output
pytest tests/test_basic.py::test_package_import -v -s
```

### Using Test Generator Verbosity
```python
def test_with_debug_output(capsys):
    """Test with debug output"""
    generator = ArgumentSpecsGenerator(verbosity=3)  # Max verbosity
    
    generator.log_debug("Debug message")
    
    captured = capsys.readouterr()
    assert "Debug message" in captured.out
```

### Inspecting Fixtures
```python
def test_inspect_fixture(sample_collection_structure):
    """Inspect what the fixture creates"""
    print(f"Collection path: {sample_collection_structure}")
    
    roles_dir = sample_collection_structure / "roles"
    for role_dir in roles_dir.iterdir():
        print(f"Role: {role_dir.name}")
        
        defaults_file = role_dir / "defaults" / "main.yml"
        if defaults_file.exists():
            with open(defaults_file) as f:
                print(f"  Defaults: {f.read()}")
```

## Continuous Integration

The test suite is designed to work in CI/CD environments:

### GitHub Actions Example
```yaml
- name: Install dependencies
  run: |
    pip install -e ".[test]"
    
- name: Run tests
  run: |
    pytest tests/ --cov=generate_argument_specs --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

### Test Performance
- Basic tests: < 5 seconds
- Full suite: < 60 seconds
- Tests are designed to be fast and parallelizable

## Contributing

When adding new functionality:

1. **Write tests first** (TDD approach recommended)
2. **Add both unit and integration tests**
3. **Test error conditions** and edge cases
4. **Update this README** if adding new test categories
5. **Ensure tests pass** before submitting PR

### Test Checklist
- [ ] Tests pass locally
- [ ] New functionality has tests
- [ ] Error conditions are tested
- [ ] Documentation is updated
- [ ] No linting errors
- [ ] Test coverage doesn't decrease

## Troubleshooting

### Common Issues

**Import errors:**
```bash
# Make sure package is installed in development mode
pip install -e .
```

**Fixture not found:**
```bash
# Make sure you're running from project root
cd /path/to/ansible_arg_spec_generator
pytest tests/
```

**Tests hanging:**
- Check for infinite loops in test data
- Use `pytest -v` to see which test is running
- Add timeouts if needed

**Permission errors:**
- Ensure temp directories are writable
- Check file permissions in test fixtures

For more help, see the main project README or open an issue on GitHub.
