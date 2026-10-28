from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

import pytest

from hatch.utils.fs import Path
from hatch.utils.structures import EnvVars
from hatchling.builders.app import AppBuilder
from hatchling.builders.binary import BinaryBuilder
from hatchling.builders.plugin.interface import BuilderInterface

pytestmark = [pytest.mark.requires_cargo, pytest.mark.requires_internet]


class ExpectedEnvVars:
    def __init__(self, env_vars: dict):
        self.env_vars = env_vars

    def __eq__(self, other):
        return all(not (key not in other or other[key] != value) for key, value in self.env_vars.items())

    def __hash__(self):  # no cov
        return hash(self.env_vars)


def cargo_install(*args: Any, **_kwargs: Any) -> subprocess.CompletedProcess:
    executable_name = "pyapp.exe" if sys.platform == "win32" else "pyapp"
    install_command: list[str] = args[0]
    repo_path = os.environ.get("PYAPP_REPO", "")
    if repo_path:
        temp_dir = install_command[install_command.index("--target-dir") + 1]

        build_target = os.environ.get("CARGO_BUILD_TARGET", "")
        if build_target:
            executable = Path(temp_dir, build_target, "release", executable_name)
        else:
            executable = Path(temp_dir, "release", executable_name)

        executable.parent.ensure_dir_exists()
        executable.touch()
    else:
        temp_dir = install_command[install_command.index("--root") + 1]

        executable = Path(temp_dir, "bin", executable_name)
        executable.parent.ensure_dir_exists()
        executable.touch()

    return subprocess.CompletedProcess(install_command, returncode=0, stdout=None, stderr=None)


def test_class():
    assert issubclass(BinaryBuilder, BuilderInterface)


def test_class_legacy():
    assert issubclass(AppBuilder, BinaryBuilder)


def test_default_versions(isolation):
    builder = BinaryBuilder(str(isolation))

    assert builder.get_default_versions() == ["bootstrap"]


class TestScripts:
    def test_unset(self, isolation):
        config = {"project": {"name": "My.App", "version": "0.1.0"}}
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.scripts == builder.config.scripts == []

    def test_default(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
                "scripts": {"b": "foo.bar.baz:cli", "a": "baz.bar.foo:cli"},
            }
        }
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.scripts == ["a", "b"]

    def test_specific(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
                "scripts": {"b": "foo.bar.baz:cli", "a": "baz.bar.foo:cli"},
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"scripts": ["a", "a"]}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.scripts == ["a"]

    def test_not_array(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
                "scripts": {"b": "foo.bar.baz:cli", "a": "baz.bar.foo:cli"},
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"scripts": 9000}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        with pytest.raises(TypeError, match="Field `tool.hatch.build.targets.binary.scripts` must be an array"):
            _ = builder.config.scripts

    def test_script_not_string(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
                "scripts": {"b": "foo.bar.baz:cli", "a": "baz.bar.foo:cli"},
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"scripts": [9000]}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        with pytest.raises(
            TypeError, match="Script #1 of field `tool.hatch.build.targets.binary.scripts` must be a string"
        ):
            _ = builder.config.scripts

    def test_unknown_script(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
                "scripts": {"b": "foo.bar.baz:cli", "a": "baz.bar.foo:cli"},
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"scripts": ["c"]}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        with pytest.raises(ValueError, match="Unknown script in field `tool.hatch.build.targets.binary.scripts`: c"):
            _ = builder.config.scripts


class TestPythonVersion:
    def test_default_no_source(self, isolation):
        config = {"project": {"name": "My.App", "version": "0.1.0"}}
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.python_version == builder.config.python_version == builder.config.SUPPORTED_VERSIONS[0]

    def test_default_explicit_source(self, isolation):
        config = {"project": {"name": "My.App", "version": "0.1.0"}}
        builder = BinaryBuilder(str(isolation), config=config)

        with EnvVars({"PYAPP_DISTRIBUTION_SOURCE": "url"}):
            assert builder.config.python_version == builder.config.python_version == ""

    def test_set(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"python-version": "4.0"}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.python_version == "4.0"

    def test_not_string(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"python-version": 9000}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        with pytest.raises(TypeError, match="Field `tool.hatch.build.targets.binary.python-version` must be a string"):
            _ = builder.config.python_version

    def test_compatibility(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
                "requires-python": "<3.11",
            },
        }
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.python_version == "3.10"

    def test_incompatible(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
                "requires-python": ">9000",
            },
        }
        builder = BinaryBuilder(str(isolation), config=config)

        with pytest.raises(
            ValueError, match="Field `project.requires-python` is incompatible with the known distributions"
        ):
            _ = builder.config.python_version


class TestPyAppVersion:
    def test_default(self, isolation):
        config = {"project": {"name": "My.App", "version": "0.1.0"}}
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.pyapp_version == builder.config.pyapp_version == ""

    def test_set(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"pyapp-version": "9000"}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.pyapp_version == "9000"

    def test_not_string(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"pyapp-version": 9000}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        with pytest.raises(TypeError, match="Field `tool.hatch.build.targets.binary.pyapp-version` must be a string"):
            _ = builder.config.pyapp_version


class TestAuditable:
    def test_default(self, isolation):
        config = {"project": {"name": "My.App", "version": "0.1.0"}}
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.auditable is builder.config.auditable is False

    def test_set(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"auditable": True}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        assert builder.config.auditable is True

    def test_not_boolean(self, isolation):
        config = {
            "project": {
                "name": "My.App",
                "version": "0.1.0",
            },
            "tool": {"hatch": {"build": {"targets": {"binary": {"auditable": 9000}}}}},
        }
        builder = BinaryBuilder(str(isolation), config=config)

        with pytest.raises(TypeError, match="Field `tool.hatch.build.targets.binary.auditable` must be a boolean"):
            _ = builder.config.auditable


class TestBuildBootstrap:
    def test_default(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd():
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "binary" / ("my-app-0.1.0.exe" if sys.platform == "win32" else "my-app-0.1.0")).is_file()

    def test_default_build_target(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd({"CARGO_BUILD_TARGET": "target"}):
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (
            build_path / "binary" / ("my-app-0.1.0-target.exe" if sys.platform == "win32" else "my-app-0.1.0-target")
        ).is_file()

    def test_scripts(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0", "scripts": {"foo": "bar.baz:cli"}},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd():
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({
                "PYAPP_PROJECT_NAME": "my-app",
                "PYAPP_PROJECT_VERSION": "0.1.0",
                "PYAPP_EXEC_SPEC": "bar.baz:cli",
            }),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "binary" / ("foo-0.1.0.exe" if sys.platform == "win32" else "foo-0.1.0")).is_file()

    def test_scripts_build_target(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0", "scripts": {"foo": "bar.baz:cli"}},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd({"CARGO_BUILD_TARGET": "target"}):
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({
                "PYAPP_PROJECT_NAME": "my-app",
                "PYAPP_PROJECT_VERSION": "0.1.0",
                "PYAPP_EXEC_SPEC": "bar.baz:cli",
            }),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (
            build_path / "binary" / ("foo-0.1.0-target.exe" if sys.platform == "win32" else "foo-0.1.0-target")
        ).is_file()

    def test_custom_cargo(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd({"CARGO": "cross"}):
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cross", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "binary" / ("my-app-0.1.0.exe" if sys.platform == "win32" else "my-app-0.1.0")).is_file()

    def test_no_cargo(self, hatch, temp_dir, mocker):
        mocker.patch("shutil.which", return_value=None)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        with pytest.raises(OSError, match="Executable `cargo` could not be found on PATH"), project_path.as_cwd():
            next(builder.build())

    def test_python_version(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"], "python-version": "4.0"}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd():
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({
                "PYAPP_PROJECT_NAME": "my-app",
                "PYAPP_PROJECT_VERSION": "0.1.0",
                "PYAPP_PYTHON_VERSION": "4.0",
            }),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "binary" / ("my-app-0.1.0.exe" if sys.platform == "win32" else "my-app-0.1.0")).is_file()

    def test_pyapp_version(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"], "pyapp-version": "9000"}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd():
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "install", "pyapp", "--force", "--root", mocker.ANY, "--version", "9000"],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "binary" / ("my-app-0.1.0.exe" if sys.platform == "win32" else "my-app-0.1.0")).is_file()

    def test_verbosity(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd({"HATCH_QUIET": "1"}):
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "binary" / ("my-app-0.1.0.exe" if sys.platform == "win32" else "my-app-0.1.0")).is_file()

    def test_local_build_with_build_target(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd({"PYAPP_REPO": "test-path", "CARGO_BUILD_TARGET": "target"}):
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "build", "--release", "--target-dir", mocker.ANY],
            cwd="test-path",
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (
            build_path / "binary" / ("my-app-0.1.0-target.exe" if sys.platform == "win32" else "my-app-0.1.0-target")
        ).is_file()

    def test_local_build_no_build_target(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd({"PYAPP_REPO": "test-path"}):
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "build", "--release", "--target-dir", mocker.ANY],
            cwd="test-path",
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "binary" / ("my-app-0.1.0.exe" if sys.platform == "win32" else "my-app-0.1.0")).is_file()

    def test_auditable_custom_cargo_pyapp_version(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {
                        "targets": {"binary": {"versions": ["bootstrap"], "auditable": True, "pyapp-version": "9000"}}
                    },
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"
        cargo_path = str(temp_dir / "rust tools" / ("cargo.exe" if sys.platform == "win32" else "cargo"))

        with project_path.as_cwd({"CARGO": cargo_path}):
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            [cargo_path, "auditable", "install", "pyapp", "--force", "--root", mocker.ANY, "--version", "9000"],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "binary" / ("my-app-0.1.0.exe" if sys.platform == "win32" else "my-app-0.1.0")).is_file()

    def test_auditable_local_build_with_build_target(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"], "auditable": True}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd({"PYAPP_REPO": "test-path", "CARGO_BUILD_TARGET": "target"}):
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "auditable", "build", "--release", "--target-dir", mocker.ANY],
            cwd="test-path",
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (
            build_path / "binary" / ("my-app-0.1.0-target.exe" if sys.platform == "win32" else "my-app-0.1.0-target")
        ).is_file()

    @pytest.mark.parametrize("cross_name", ["cross", "cross.exe", "absolute"])
    def test_auditable_cross(self, hatch, temp_dir, mocker, cross_name):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"], "auditable": True}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        cargo_path = str(temp_dir / "rust tools" / "cross") if cross_name == "absolute" else cross_name

        with (
            pytest.raises(
                ValueError,
                match="The `auditable` option cannot be used if the `CARGO` environment variable refers to `cross`",
            ),
            project_path.as_cwd({"CARGO": cargo_path, "PYAPP_REPO": "test-path"}),
        ):
            next(builder.build())

        subprocess_run.assert_not_called()

    def test_auditable_compilation_failed_quiet(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], returncode=101, stdout=b"error: no such command: `auditable`"),
        )

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"binary": {"versions": ["bootstrap"], "auditable": True}}},
                },
            },
        }
        builder = BinaryBuilder(str(project_path), config=config)

        with (
            pytest.raises(
                OSError,
                match=r"Compilation failed \(code 101\)\. The `auditable` option requires cargo-auditable to be installed",
            ),
            project_path.as_cwd({"HATCH_QUIET": "1"}),
        ):
            next(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "auditable", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def test_legacy(self, hatch, temp_dir, mocker):
        subprocess_run = mocker.patch("subprocess.run", side_effect=cargo_install)

        project_name = "My.App"

        with temp_dir.as_cwd():
            result = hatch("new", project_name)

        assert result.exit_code == 0, result.output

        project_path = temp_dir / "my-app"
        config = {
            "project": {"name": project_name, "version": "0.1.0"},
            "tool": {
                "hatch": {
                    "build": {"targets": {"app": {"versions": ["bootstrap"]}}},
                },
            },
        }
        builder = AppBuilder(str(project_path), config=config)

        build_path = project_path / "dist"

        with project_path.as_cwd():
            artifacts = list(builder.build())

        subprocess_run.assert_called_once_with(
            ["cargo", "install", "pyapp", "--force", "--root", mocker.ANY],
            cwd=mocker.ANY,
            env=ExpectedEnvVars({"PYAPP_PROJECT_NAME": "my-app", "PYAPP_PROJECT_VERSION": "0.1.0"}),
        )

        assert len(artifacts) == 1
        expected_artifact = artifacts[0]

        build_artifacts = list(build_path.iterdir())
        assert len(build_artifacts) == 1
        assert expected_artifact == str(build_artifacts[0])
        assert (build_path / "app" / ("my-app-0.1.0.exe" if sys.platform == "win32" else "my-app-0.1.0")).is_file()
