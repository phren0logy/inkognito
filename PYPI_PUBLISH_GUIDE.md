# PyPI Publication Guide for Inkognito

## Current Status

✅ Package metadata added to pyproject.toml
✅ Entry point created (`inkognito = "server:main"`)
✅ Distribution files built successfully
✅ Local installation tested with uvx
✅ LICENSE file created

## Before Publishing to PyPI

1. **Update Author Information**
   - Edit `pyproject.toml` and replace:
     - `Your Name` with your actual name
     - `your.email@example.com` with your email
   - Update the LICENSE file copyright line

2. **Fix Test Failures (Optional but Recommended)**
   - Run `uv run pytest tests/` to see current test status
   - Many tests are passing, but some require fixes
   - Focus on critical functionality tests

3. **Version Check**
   - Current version: 0.1.0
   - Consider if this should be 0.0.1 for initial release

## Publishing Steps

1. **Create PyPI Account**
   - Register at https://pypi.org/account/register/
   - Enable 2FA (required for new accounts)

2. **Get API Token**
   - Go to https://pypi.org/manage/account/token/
   - Create a token with "Entire account" scope
   - Save it securely

3. **Configure uv for Publishing**
   ```bash
   # Set your PyPI token (replace with your actual token)
   export UV_PUBLISH_TOKEN="pypi-AgEIcHlwaS5vcmcC..."
   ```

4. **Publish to PyPI**
   ```bash
   # Clean build
   rm -rf dist/
   uv build
   
   # Publish
   uv publish
   ```

## Testing the Published Package

Once published, users can install via:

```bash
# With pip
pip install inkognito

# With uvx (recommended)
uvx inkognito

# In Claude Desktop config
{
  "mcpServers": {
    "inkognito": {
      "command": "uvx",
      "args": ["inkognito"]
    }
  }
}
```

## Post-Publication

1. **Create GitHub Release**
   - Tag version: `v0.1.0`
   - Include changelog
   - Attach wheel and sdist files

2. **Update README**
   - Add PyPI badge
   - Update installation instructions

3. **Monitor Issues**
   - Watch GitHub issues for user feedback
   - Be ready to release patches if needed

## Alternative: Test PyPI First

Consider publishing to Test PyPI first:

```bash
# Set Test PyPI token
export UV_PUBLISH_TOKEN="pypi-AgEIcHlwaS5vcmcC..."

# Publish to Test PyPI
uv publish --index-url https://test.pypi.org/legacy/

# Test installation
pip install --index-url https://test.pypi.org/simple/ inkognito
```

## Current Package Structure Note

The package currently uses a flat structure (Python files in root) rather than a nested package structure. This works but may need restructuring in future versions for better organization.