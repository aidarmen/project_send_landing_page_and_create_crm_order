"""
Version tracking module for the project.
Reads version from VERSION file and provides version information.
"""
import os
from pathlib import Path

def get_version():
    """Read version from VERSION file"""
    version_file = Path(__file__).parent / "VERSION"
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            version = f.read().strip()
            return version
    return "unknown"

def log_version_update(version, description=""):
    """
    Log version update to CHANGELOG.md
    This is a helper function - actual updates should be done manually in CHANGELOG.md
    """
    changelog_path = Path(__file__).parent / "CHANGELOG.md"
    if not changelog_path.exists():
        return False
    
    # This function is mainly for reference - actual changelog updates should be manual
    # to maintain proper formatting and documentation
    return True

# Current version
__version__ = get_version()

