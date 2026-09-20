"""Regression tests for repository-root .env loading."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from providers import ENV_FILE, ROOT_DIR, load_project_environment, require_environment_variable


class EnvironmentLoadingTests(unittest.TestCase):
    def test_default_env_path_is_repository_root(self):
        self.assertEqual(ROOT_DIR, Path(__file__).resolve().parents[1])
        self.assertEqual(ENV_FILE, ROOT_DIR / ".env")

    def test_dotenv_loads_keys_without_shell_export(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "DEEPSEEK_API_KEY=dotenv-deepseek-test\n"
                "DASHSCOPE_API_KEY=dotenv-dashscope-test\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                self.assertTrue(load_project_environment(env_file))
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "dotenv-deepseek-test")
                self.assertEqual(os.environ["DASHSCOPE_API_KEY"], "dotenv-dashscope-test")

    def test_existing_shell_value_wins(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("DEEPSEEK_API_KEY=dotenv-value\n", encoding="utf-8")
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "shell-value"}, clear=True):
                load_project_environment(env_file)
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "shell-value")

    def test_missing_key_error_points_to_root_env(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, r"Missing DEEPSEEK_API_KEY.*root \.env"):
                require_environment_variable("DEEPSEEK_API_KEY")


if __name__ == "__main__":
    unittest.main()
