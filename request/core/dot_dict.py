class DotDict(dict):
    """
    支持点符号访问的字典包装类
    """

    def __getattr__(self, item):
        # 优先从字典内容中取
        if item in self:
            return self[item]
        # 否则尝试获取类属性或方法（如 get, update 等）
        try:
            return object.__getattribute__(self, item)
        except AttributeError:
            raise AttributeError(f"'DotDict' object has no attribute '{item}'")

    def __setattr__(self, key, value):
        self[key] = value
