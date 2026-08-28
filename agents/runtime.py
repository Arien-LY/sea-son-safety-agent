"""Hello-Agents 教程运行时元数据。"""

from importlib.metadata import PackageNotFoundError, version


def runtime_info() -> dict[str, str]:
    """返回可公开展示的框架信息，不读取密钥或创建模型客户端。"""

    try:
        framework_version = version("hello-agents")
    except PackageNotFoundError:
        framework_version = "not-installed"
    return {
        "framework": "hello-agents",
        "framework_version": framework_version,
        "tutorial_baseline": "Hello-Agents V1.0.3",
    }

