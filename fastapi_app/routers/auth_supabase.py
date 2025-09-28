"""
基于 Supabase Auth 的认证辅助路由
仅提供被动验证后的基本查询接口
"""

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi_app.dependencies.auth import get_current_active_user
from fastapi_app.dependencies.permissions import (
    Permission,
    PermissionChecker,
    get_user_permissions_info,
)
from fastapi_app.models.auth import UserInfo
from fastapi_app.models.common import APIResponse
from fastapi_app.services.user_service import FastAPIUserService, get_user_service

router = APIRouter()


@router.get("/me", response_model=APIResponse)
async def me(current_user: UserInfo = Depends(get_current_active_user)):
    return APIResponse(success=True, message="获取用户信息成功", data=current_user.dict())


@router.get("/permissions", response_model=APIResponse)
async def get_current_user_permissions(current_user: UserInfo = Depends(get_current_active_user)):
    permissions_info = await get_user_permissions_info(current_user)
    return APIResponse(success=True, message="获取权限信息成功", data=permissions_info)


@router.get("/permissions/detailed", response_model=APIResponse)
async def get_current_user_permissions_detailed(current_user: UserInfo = Depends(get_current_active_user)):
    """
    返回与 /permissions 相同的数据结构，便于前端对接。
    如需扩展，可在 data 中加入更细粒度的权限来源、说明等。
    """
    permissions_info = await get_user_permissions_info(current_user)
    return APIResponse(success=True, message="获取权限详细信息成功", data=permissions_info)


@router.get("/users/{user_id}", response_model=APIResponse)
async def get_user_by_id(
    user_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
    user_service: FastAPIUserService = Depends(get_user_service),
):
    # 权限校验：需要 user:read
    if not PermissionChecker.has_permission(current_user, Permission.USER_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少权限: user:read")
    user_data = await user_service.get_user_by_id(user_id)
    if not user_data:
        return APIResponse(success=False, message="用户不存在", data={})
    user_info = UserInfo(
        id=user_data['id'],
        username=user_data.get('username', ''),
        email=user_data.get('email', ''),
        is_admin=user_data.get('is_admin', False),
        created_at=user_data.get('created_at', ''),
    )
    return APIResponse(success=True, message="获取用户信息成功", data=user_info.dict())
