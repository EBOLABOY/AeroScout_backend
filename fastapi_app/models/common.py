"""
通用Pydantic模型
"""
from typing import Optional, Any
from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """通用API响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    error_code: Optional[str] = Field(None, description="错误代码")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "操作成功",
                "data": {}
            }
        }