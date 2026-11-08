"""让 PyMySQL 作为 MySQLdb 的替代实现，供 DB_ENGINE=mysql 时使用。"""

try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # 仅使用 SQLite 时可以不安装 PyMySQL
    pass
