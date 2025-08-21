# Python Version Management

This project uses a **single authoritative script** for Python version management:

## 📍 Single Source of Truth

**`scripts/check_python_versions.py`** is the only script that determines:
- ✅ What Python versions should be supported
- ✅ Updates `pyproject.toml` when new versions are available  
- ✅ Provides version lists for CI/CD

## 🔧 Usage

### For CI/CD (Automated)
```bash
# Get JSON array for GitHub Actions matrix
python3 scripts/check_python_versions.py --format=json --exclude-old
# Output: ["3.8", "3.9", "3.10", "3.11", "3.12", "3.13"]

# Get latest version for single-version jobs
python3 scripts/check_python_versions.py --format=latest --exclude-old  
# Output: 3.13

# Get CI-specific format (used by GitHub Actions)
python3 scripts/check_python_versions.py --format=ci --exclude-old
# Output: 
# versions=["3.8", "3.9", "3.10", "3.11", "3.12", "3.13"]
# latest=3.13
```

### For Maintenance (Manual)
```bash
# Check what updates are available
python3 scripts/check_python_versions.py --check-only

# See what would be updated (dry run)
python3 scripts/check_python_versions.py --dry-run

# Actually update pyproject.toml  
python3 scripts/check_python_versions.py
```

## 🎯 How It Works

1. **🌐 Checks Python.org** for stable releases (x.y.0 versions only)
2. **🔍 Filters to supported versions** (currently 3.8+ since 3.6/3.7 are EOL)
3. **📋 Compares with pyproject.toml** classifiers
4. **✏️  Updates pyproject.toml** if new versions are available
5. **📤 Provides version lists** for CI/CD consumption

## 🤖 Automated Updates

- **📅 Monthly Check**: GitHub Action runs monthly to check for new Python versions
- **🔄 Auto-PR**: Creates pull requests when new versions are available
- **🧪 CI Integration**: Test matrix automatically includes all supported versions

## 🛡️ Fallback Mode

The script works even without internet access:
- **🌐 Online**: Queries Python.org for latest releases
- **📴 Offline**: Uses built-in fallback list of known stable versions

## 🔧 Integration Points

- **`.github/workflows/test.yml`**: Uses the script for test matrix
- **`.github/workflows/update-python-versions.yml`**: Monthly update automation
- **`pyproject.toml`**: Updated by the script when new versions are available

**No more manual Python version management!** 🚀
