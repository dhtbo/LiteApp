import logging
import sys

def setup_logger(name: str = "liteapp") -> logging.Logger:
    """
    配置并获取全局统一格式的 Logger 实例
    
    :param name: 日志记录器名称
    :returns: 配置完成的 Logger 对象
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger

logger: logging.Logger = setup_logger()
