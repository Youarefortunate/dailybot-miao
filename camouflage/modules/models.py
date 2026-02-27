from typing import List, Optional
from pydantic import BaseModel


class CamouflageItem(BaseModel):
    """
    统一的伪装素材接口模型
    """

    # 素材唯一标识码 (如 commit_id)
    id: str
    # 素材所属来源记录 (如仓库路径、项目名称)
    source: str
    # 原始描述文本内容
    content: str
    # 来源平台标识 (如 gitlab, tapd)
    platform: str
    # 素材原始作者
    author: Optional[str] = None
    # 素材创建的具体时间
    created_at: Optional[str] = None

    @classmethod
    def builder(cls):
        return CamouflageItemBuilder()


class CamouflageItemBuilder:
    """
    CamouflageItem 的建造者类
    """

    def __init__(self):
        self._id = None
        self._source = None
        self._content = None
        self._platform = None
        self._author = None
        self._created_at = None

    def set_id(self, item_id: str):
        self._id = item_id
        return self

    def set_source(self, source: str):
        self._source = source
        return self

    def set_content(self, content: str):
        self._content = content
        return self

    def set_platform(self, platform: str):
        self._platform = platform
        return self

    def set_author(self, author: str):
        self._author = author
        return self

    def set_created_at(self, created_at: str):
        self._created_at = created_at
        return self

    def build(self) -> CamouflageItem:
        return CamouflageItem(
            id=self._id,
            source=self._source,
            content=self._content,
            platform=self._platform,
            author=self._author,
            created_at=self._created_at,
        )


class CamouflageHistory(BaseModel):
    """
    LRU 历史纪录模型，用于记录素材的使用轨迹
    """

    # 最后一次被用作素材的日期 (YYYY-MM-DD)
    last_used: str
    # 针对该素材已生成的 AI 润色变体列表
    variants: List[str]
