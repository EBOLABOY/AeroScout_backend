"""
认证相关的Pydantic模型
"""
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class UserLogin(BaseModel):
    """用户登录模型"""
    username: str = Field(..., description="用户名或邮箱", min_length=3, max_length=50)
    password: str = Field(..., description="密码", min_length=6, max_length=128)
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin",
                "password": "password123"
            }
        }


class UserRegister(BaseModel):
    """用户注册模型"""
    username: str = Field(..., description="用户名", min_length=3, max_length=50)
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码", min_length=6, max_length=128)
    confirm_password: str = Field(..., description="确认密码", alias="confirmPassword")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "username": "newuser",
                "email": "user@example.com",
                "password": "password123",
                "confirmPassword": "password123"
            }
        }


class UserLevel(BaseModel):
    """用户等级模型"""
    id: int = Field(..., description="等级ID")
    name: str = Field(..., description="等级名称")
    display_name: str = Field(..., description="显示名称")
    description: str = Field(..., description="等级描述")
    sort_order: int = Field(..., description="排序")
    is_active: bool = Field(True, description="是否启用")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 2,
                "name": "user",
                "display_name": "普通用户",
                "description": "注册用户，可以使用基础功能",
                "sort_order": 2,
                "is_active": True
            }
        }


class UserInfo(BaseModel):
    """用户信息模型"""
    id: str = Field(..., description="用户ID (UUID)")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱地址")
    is_admin: bool = Field(False, description="是否管理员")
    user_level_id: Optional[int] = Field(None, description="用户等级ID")
    user_level_name: str = Field("user", description="用户等级名称")
    user_level: Optional[UserLevel] = Field(None, description="用户等级详细信息")
    created_at: str = Field(..., description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "987c5515-b439-43f0-a178-3c49ca154bb1",
                "username": "admin",
                "email": "admin@example.com",
                "is_admin": True,
                "user_level_id": 2,
                "user_level_name": "user",
                "user_level": {
                    "id": 2,
                    "name": "user",
                    "display_name": "普通用户",
                    "description": "注册用户，可以使用基础功能",
                    "sort_order": 2,
                    "is_active": True
                },
                "created_at": "2024-01-01 00:00:00"
            }
        }


class TokenResponse(BaseModel):
    """Token响应模型"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")
    user_info: UserInfo = Field(..., description="用户信息")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "user_info": {
                    "id": "987c5515-b439-43f0-a178-3c49ca154bb1",
                    "username": "admin",
                    "email": "admin@example.com",
                    "is_admin": True,
                    "created_at": "2024-01-01 00:00:00"
                }
            }
        }


class PasswordResetRequest(BaseModel):
    """密码重置请求模型"""
    email: EmailStr = Field(..., description="邮箱地址")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class PasswordResetConfirm(BaseModel):
    """密码重置确认模型"""
    token: str = Field(..., description="重置token", min_length=1)
    password: str = Field(..., description="新密码", min_length=6, max_length=128)

    class Config:
        json_schema_extra = {
            "example": {
                "token": "abc123def456",
                "password": "newpassword123"
            }
        }


class PasswordChange(BaseModel):
    """密码修改模型"""
    old_password: str = Field(..., description="旧密码", alias="oldPassword")
    new_password: str = Field(..., description="新密码", min_length=6, max_length=128, alias="newPassword")
    confirm_password: str = Field(..., description="确认新密码", alias="confirmPassword")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "oldPassword": "oldpassword123",
                "newPassword": "newpassword123",
                "confirmPassword": "newpassword123"
            }
        }


class UserLevelUpdate(BaseModel):
    """用户等级更新模型"""
    user_id: str = Field(..., description="用户ID")
    level_name: str = Field(..., description="新等级名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "987c5515-b439-43f0-a178-3c49ca154bb1",
                "level_name": "plus"
            }
        }


class UserPermissions(BaseModel):
    """用户权限信息模型"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    role: str = Field(..., description="用户角色")
    level: UserLevel = Field(..., description="用户等级")
    permissions: list[str] = Field(..., description="权限列表")
    is_admin: bool = Field(False, description="是否管理员")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "987c5515-b439-43f0-a178-3c49ca154bb1",
                "username": "testuser",
                "role": "user",
                "level": {
                    "id": 2,
                    "name": "user",
                    "display_name": "普通用户",
                    "description": "注册用户，可以使用基础功能",
                    "sort_order": 2,
                    "is_active": True
                },
                "permissions": [
                    "flight:search",
                    "travel:plan:create",
                    "travel:plan:read"
                ],
                "is_admin": False
            }
        }
