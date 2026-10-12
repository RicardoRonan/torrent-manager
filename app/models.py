from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TorrentUpload(BaseModel):
    name: str = ""
    data: str


class AddRequest(BaseModel):
    magnets: List[str] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    torrents: List[TorrentUpload] = Field(default_factory=list)
    category: str = ""
    tags: List[str] = Field(default_factory=list)
    dir: str = ""


class BatchRequest(BaseModel):
    action: str
    gids: List[str] = Field(default_factory=list)
    category: str = ""
    tags: List[str] = Field(default_factory=list)


class FileSelection(BaseModel):
    index: int
    selected: bool = True
    priority: int = 1


class FilesRequest(BaseModel):
    files: List[FileSelection] = Field(default_factory=list)
    sequential: Optional[bool] = None


class OptionsRequest(BaseModel):
    options: Dict[str, str] = Field(default_factory=dict)


class CategoryIn(BaseModel):
    name: str
    path: str = ""


class ViewIn(BaseModel):
    name: str
    filters: Dict = Field(default_factory=dict)
    sort: Dict = Field(default_factory=dict)


class ActionRequest(BaseModel):
    gid: str
    fileIndex: Optional[int] = None
