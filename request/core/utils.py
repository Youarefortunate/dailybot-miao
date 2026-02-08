import collections

def is_plain_object(obj):
    """
    判断是否为普通字典对象
    """
    return isinstance(obj, dict)

def for_each(collection, callback):
    """
    遍历集合
    """
    if isinstance(collection, dict):
        for key, value in collection.items():
            callback(value, key)
    elif isinstance(collection, (list, tuple)):
        for index, item in enumerate(collection):
            callback(item, index)
