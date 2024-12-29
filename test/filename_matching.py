#!/usr/bin/env python3
import glob
import os
import re
import sys
from typing import List, Tuple


class FileChecker:
    """
    文件检查器类，用于检查源文件和测试文件的一致性。
    """

    def __init__(self):
        # 定义排除目录列表
        self.excluded_src_dirs = [
            "mitmproxy/contrib/",
            "mitmproxy/io/proto/",
            "mitmproxy/proxy/layers/http",
            "mitmproxy/test/",
            "mitmproxy/tools/",
            "mitmproxy/platform/",
            "mitmproxy/utils/pyinstaller/",
        ]
        self.excluded_test_dirs = [
            "test/mitmproxy/data/",
            "test/mitmproxy/net/data/",
            "/tservers.py",
            "/conftest.py",
        ]

    def get_files(self, root: str, pattern: str, exclude_list: List[str]) -> List[str]:
        """
        获取指定目录中匹配模式的所有文件，并排除指定路径。

        :param root: 根目录
        :param pattern: 匹配模式
        :param exclude_list: 排除路径列表
        :return: 符合条件的文件列表
        """
        files = glob.glob(os.path.join(root, pattern), recursive=True)
        files = [f for f in files if os.path.basename(f) != "__init__.py"]
        files = [f for f in files if not any(os.path.normpath(p) in f for p in exclude_list)]
        return files

    def check_src_files_have_test(self) -> List[Tuple[str, str]]:
        """
        检查源文件是否都有对应的测试文件。

        :return: 缺少测试文件的源文件及预期的测试文件路径
        """
        missing_test_files = []
        src_files = self.get_files("mitmproxy", "**/*.py", self.excluded_src_dirs)

        for f in src_files:
            test_file = os.path.join("test", os.path.dirname(f), "test_" + os.path.basename(f))
            if not os.path.isfile(test_file):
                missing_test_files.append((f, test_file))

        return missing_test_files

    def check_test_files_have_src(self) -> List[Tuple[str, str]]:
        """
        检查测试文件是否都有对应的源文件。

        :return: 不匹配源文件的测试文件及预期的源文件路径
        """
        unknown_test_files = []
        test_files = self.get_files("test/mitmproxy", "**/*.py", self.excluded_test_dirs)

        for f in test_files:
            src_file = os.path.join(
                re.sub("^test/", "", os.path.dirname(f)),
                re.sub("^test_", "", os.path.basename(f)),
            )
            if not os.path.isfile(src_file):
                unknown_test_files.append((f, src_file))

        return unknown_test_files


def print_results(missing_files: List[Tuple[str, str]], unknown_files: List[Tuple[str, str]]) -> int:
    """
    打印检查结果并返回退出码。

    :param missing_files: 缺少测试文件的源文件列表
    :param unknown_files: 不匹配源文件的测试文件列表
    :return: 退出码
    """
    exitcode = 0

    if missing_files:
        exitcode += 1
        print("\nMissing Test Files:")
        for src, test in sorted(missing_files):
            print(f"  {src} MUST have a matching test file: {test}")

    if unknown_files:
        # TODO: 未来可以启用以下功能
        # exitcode += 1
        print("\nUnknown Test Files:")
        for test, src in sorted(unknown_files):
            print(f"  {test} DOES NOT MATCH a source file! Expected to find: {src}")

    return exitcode


def main():
    """
    主函数，执行文件检查。
    """
    checker = FileChecker()

    print("Checking for missing test files...")
    missing_test_files = checker.check_src_files_have_test()

    print("Checking for unmatched test files...")
    unknown_test_files = checker.check_test_files_have_src()

    exitcode = print_results(missing_test_files, unknown_test_files)

    sys.exit(exitcode)


if __name__ == "__main__":
    main()
