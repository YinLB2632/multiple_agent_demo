"""让测试能从项目根目录导入模块。"""
import os
import sys

# 把项目根目录加入 import 路径
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
