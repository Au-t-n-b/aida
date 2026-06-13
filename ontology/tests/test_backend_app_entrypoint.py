import importlib
import unittest


class BackendAppEntrypointTests(unittest.TestCase):
    def test_can_import_backend_app_from_repo_root(self):
        module = importlib.import_module("backend_app")
        self.assertTrue(hasattr(module, "create_app"))
        self.assertTrue(callable(module.create_app))


if __name__ == "__main__":
    unittest.main()
