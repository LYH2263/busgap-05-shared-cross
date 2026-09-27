import os
import tempfile

# 测试用独立 SQLite 库，避免依赖 Postgres；须在导入 app 模块前设置
_db_dir = tempfile.mkdtemp(prefix="busgap-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'test.db')}"
