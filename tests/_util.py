"""测试共享工具：加载知识库引擎模块。"""
import importlib.machinery
import importlib.util
from pathlib import Path

ENGINE = (Path(__file__).parents[1] / "skills" / "mirror-fetch" / "scripts" / "mirror-fetch").resolve()
assert ENGINE.is_file(), ENGINE

# 引擎文件无 .py 后缀 → 必须显式 SourceFileLoader
_loader = importlib.machinery.SourceFileLoader("mirror_fetch_engine", str(ENGINE))
_spec = importlib.util.spec_from_loader("mirror_fetch_engine", _loader)
mf = importlib.util.module_from_spec(_spec)
_loader.exec_module(mf)
