"""Master Test Runner for RouteRanker Backend."""

import os
import sys
import unittest
from pathlib import Path

# Set Python path to backend directory
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

if __name__ == "__main__":
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(start_dir=str(backend_dir / "tests"), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    sys.exit(0 if result.wasSuccessful() else 1)

