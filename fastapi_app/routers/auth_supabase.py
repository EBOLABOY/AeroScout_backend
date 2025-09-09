"""
基于 Supabase Auth 的认证辅助路由
仅提供被动验证后的基本查询接口
"""
from fastapi import APIRouter, Depends
from fastapi_app.models.auth import UserInfo
from fastapi_app.models.common import APIResponse
from fastapi_app.dependencies.auth import get_current_active_user
from fastapi_app.dependencies.permissions import get_user_permissions_info, require_user_read_permission
from fastapi_app.services.user_service import get_user_service, FastAPIUserService


router = APIRouter()


@router.get("/me", response_model=APIResponse)
async def me(current_user: UserInfo = Depends(get_current_active_user)):
    return APIResponse(success=True, message="获取用户信息成功", data=current_user.dict())


@router.get("/permissions", response_model=APIResponse)
async def get_current_user_permissions(
    permissions_info: dict = Depends(get_user_permissions_info)
):
    return APIResponse(success=True, message="获取权限信息成功", data=permissions_info)


@router.get("/users/{user_id}", response_model=APIResponse)
async def get_user_by_id(
    user_id: str,
    current_user: UserInfo = Depends(require_user_read_permission),
    user_service: FastAPIUserService = Depends(get_user_service)
):
    user_data = await user_service.get_user_by_id(user_id)
    if not user_data:
        return APIResponse(success=False, message="用户不存在", data={})
    user_info = UserInfo(
        id=user_data['id'],
        username=user_data.get('username', ''),
        email=user_data.get('email', ''),
        is_admin=user_data.get('is_admin', False),
        created_at=user_data.get('created_at', '')
    )
    return APIResponse(success=True, message="获取用户信息成功", data=user_info.dict())

