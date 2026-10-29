"""Pytest configuration for contract tests."""
import sys
from pathlib import Path

# Add project root and backend to Python path
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
src_path = project_root / "src"

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(src_path))