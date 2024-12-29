#!/usr/bin/env python3
import ast
import asyncio
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Optional

import tomllib

# 全局路径定义
ROOT = Path(__file__).parent.parent.absolute()


class ConfigLoader:
    """
    配置加载器，用于加载和解析 pyproject.toml 配置文件。
    """

    @staticmethod
    def load_pytest_config() -> Dict:
        """
        加载 pyproject.toml 文件中的 pytest 配置。
        """
        try:
            with open("pyproject.toml", "rb") as f:
                return tomllib.load(f)["tool"]["pytest"]["individual_coverage"]
        except (FileNotFoundError, KeyError) as e:
            raise RuntimeError("Failed to load pyproject.toml or pytest configuration.") from e


class FileProcessor:
    """
    文件处理器，用于处理源文件和测试文件的匹配与分析。
    """

    @staticmethod
    def generate_exclusion_pattern(exclude_list: List[str]) -> re.Pattern:
        """
        根据排除列表生成正则表达式模式。
        """
        return re.compile("|".join(f"({fnmatch.translate(x)})" for x in exclude_list))

    @staticmethod
    def should_skip_init_file(file: Path) -> bool:
        """
        检查是否应该跳过 __init__.py 文件。
        """
        if file.name == "__init__.py":
            mod = ast.parse(file.read_text())
            return all(isinstance(stmt, (ast.ImportFrom, ast.Import, ast.Assign)) for stmt in mod.body)
        return False

    @staticmethod
    def map_to_test_file(file: Path) -> Path:
        """
        根据源文件路径生成对应的测试文件路径。
        """
        if file.name == "__init__.py":
            return Path("test") / file.parent.with_name(f"test_{file.parent.name}.py")
        return Path("test") / file.with_name(f"test_{file.name}")


class TestRunner:
    """
    测试运行器，用于执行测试并检查覆盖率。
    """

    def __init__(self, semaphore: asyncio.Semaphore):
        self.semaphore = semaphore

    async def run_test(self, file: Path, exclude_pattern: re.Pattern, should_fail: bool) -> None:
        """
        运行单个文件的测试，检查覆盖率。
        """
        if FileProcessor.should_skip_init_file(file):
            if should_fail:
                raise RuntimeError(f"Remove {file} from exclusion in pyproject.toml.")
            print(f"{file}: skip __init__.py file without logic")
            return

        test_file = FileProcessor.map_to_test_file(file)
        coverage_file = f".coverage-{str(file).replace('/', '-')}"

        async with self.semaphore:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "pytest",
                    "-qq",
                    "--disable-pytest-warnings",
                    "--cov",
                    str(file.with_suffix("")).replace("/", "."),
                    "--cov-fail-under",
                    "100",
                    "--cov-report",
                    "term-missing:skip-covered",
                    test_file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={
                        "COVERAGE_FILE": coverage_file,
                        **os.environ,
                    },
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            except asyncio.TimeoutError:
                raise RuntimeError(f"{file}: timeout")
            finally:
                Path(coverage_file).unlink(missing_ok=True)

            if should_fail:
                if proc.returncode != 0:
                    print(f"{file}: excluded")
                else:
                    raise RuntimeError(
                        f"{file} is now fully covered by {test_file}. Remove it from exclusion in pyproject.toml."
                    )
            else:
                if proc.returncode == 0:
                    print(f"{file}: ok")
                else:
                    raise RuntimeError(
                        f"{file} is not fully covered by {test_file}:\n{stdout.decode(errors='ignore')}\n{stderr.decode(errors='ignore')}"
                    )


async def main():
    """
    主函数：加载配置文件、检查文件并运行测试。
    """
    config = ConfigLoader.load_pytest_config()
    exclude_pattern = FileProcessor.generate_exclusion_pattern(config["exclude"])

    semaphore = asyncio.Semaphore(os.cpu_count() or 1)
    test_runner = TestRunner(semaphore)

    tasks = []
    for file in (ROOT / "mitmproxy").glob("**/*.py"):
        file = file.relative_to(ROOT)

        # 跳过空 __init__.py 文件
        if file.name == "__init__.py" and file.stat().st_size == 0:
            print(f"{file}: empty")
            continue

        # 添加测试任务
        tasks.append(
            asyncio.create_task(test_runner.run_test(file, exclude_pattern, should_fail=exclude_pattern.match(str(file))))
        )

    exit_code = 0
    for task in asyncio.as_completed(tasks):
        try:
            await task
        except RuntimeError as e:
            print(e)
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())

