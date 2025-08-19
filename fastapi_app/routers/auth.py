"""
FastAPI认证路由
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from loguru import logger

from fastapi_app.models.auth import (
    UserLogin,
    UserRegister,
    UserInfo,
    TokenResponse,
    PasswordChange,
    PasswordResetRequest,
    PasswordResetConfirm
)
from fastapi_app.models.common import APIResponse
from fastapi_app.dependencies.auth import (
    get_current_active_user,
    create_access_token,
    verify_password,
    get_password_hash,
    SecurityConfig
)
from fastapi_app.services.user_service import get_user_service, FastAPIUserService
from fastapi_app.services.supabase_service import get_supabase_service
from fastapi_app.services.password_reset_service import get_password_reset_service
from fastapi_app.dependencies.permissions import (
    get_user_permissions_info,
    require_user_read_permission,
    require_user_write_permission,
    require_system_admin_permission
)

# 创建路由器
router = APIRouter()
security = HTTPBearer()


@router.post("/login", response_model=APIResponse)
async def login(user_login: UserLogin):
    """
    用户登录
    """
    try:
        db_service = await get_supabase_service()
        
        # 查找用户（支持用户名或邮箱登录）
        user_data = await db_service.get_user_by_username(user_login.username)
        if not user_data:
            user_data = await db_service.get_user_by_email(user_login.username)
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 验证密码
        if not verify_password(user_login.password, user_data['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 创建访问令牌
        access_token = create_access_token(
            user_id=user_data['id'],
            expires_delta=timedelta(days=1)
        )
        
        # 构建用户信息
        user_info = UserInfo(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            is_admin=user_data.get('is_admin', False),
            created_at=user_data['created_at']
        )
        
        # 构建Token响应
        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=86400,  # 24小时
            user_info=user_info
        )
        
        logger.info(f"用户登录成功: {user_data['username']}")
        
        return APIResponse(
            success=True,
            message="登录成功",
            data=token_response.dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录服务异常"
        )


@router.post("/register", response_model=APIResponse)
async def register(user_register: UserRegister):
    """
    用户注册
    """
    try:
        # 验证密码确认
        if user_register.password != user_register.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="两次输入的密码不一致"
            )

        # 验证密码强度
        if not SecurityConfig.validate_password(user_register.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码长度必须在{SecurityConfig.MIN_PASSWORD_LENGTH}-{SecurityConfig.MAX_PASSWORD_LENGTH}字符之间"
            )

        # 验证用户名格式
        if not SecurityConfig.validate_username(user_register.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"用户名长度必须在{SecurityConfig.MIN_USERNAME_LENGTH}-{SecurityConfig.MAX_USERNAME_LENGTH}字符之间"
            )
        
        db_service = await get_supabase_service()
        
        # 检查用户名是否已存在
        existing_user = await db_service.get_user_by_username(user_register.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 检查邮箱是否已存在
        existing_email = await db_service.get_user_by_email(user_register.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
        
        # 创建新用户
        user_data = {
            'username': user_register.username,
            'email': user_register.email,
            'password_hash': get_password_hash(user_register.password),
            'is_active': True,
            'is_verified': False,
            'email_verified': False,
            'created_at': datetime.now().isoformat()
        }
        
        new_user = await db_service.create_user(user_data)
        
        logger.info(f"新用户注册成功: {new_user['username']}")
        
        return APIResponse(
            success=True,
            message="注册成功，请登录",
            data={"username": new_user['username']}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册服务异常"
        )


@router.get("/me", response_model=APIResponse)
async def get_current_user_info(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取当前用户信息
    """
    try:
        return APIResponse(
            success=True,
            message="获取用户信息成功",
            data=current_user.dict()
        )
        
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )


@router.post("/change-password", response_model=APIResponse)
async def change_password(
    password_change: PasswordChange,
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    修改密码
    """
    try:
        # 验证新密码确认
        if password_change.new_password != password_change.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="两次输入的新密码不一致"
            )
        
        db_service = await get_supabase_service()
        
        # 获取当前用户完整信息
        user_data = await db_service.get_user_by_id(current_user.id)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 验证旧密码
        if not verify_password(password_change.old_password, user_data['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="原密码错误"
            )
        
        # 更新密码
        update_data = {
            'password_hash': get_password_hash(password_change.new_password)
        }
        await db_service.update_user(current_user.id, update_data)
        
        logger.info(f"用户 {current_user.username} 修改密码成功")
        
        return APIResponse(
            success=True,
            message="密码修改成功",
            data={}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="修改密码服务异常"
        )


@router.post("/forgot-password", response_model=APIResponse)
async def forgot_password(password_reset: PasswordResetRequest):
    """
    忘记密码 - 发送重置邮件
    """
    try:
        password_reset_service = await get_password_reset_service()
        result = await password_reset_service.create_reset_token(password_reset.email)

        return APIResponse(
            success=result["success"],
            message=result["message"],
            data={}
        )

    except Exception as e:
        logger.error(f"忘记密码失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务异常，请稍后重试"
        )


@router.post("/reset-password", response_model=APIResponse)
async def reset_password(password_reset: PasswordResetConfirm):
    """
    重置密码 - 使用token重置密码
    """
    try:
        # 验证新密码强度
        if not SecurityConfig.validate_password(password_reset.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码长度必须在{SecurityConfig.MIN_PASSWORD_LENGTH}-{SecurityConfig.MAX_PASSWORD_LENGTH}字符之间"
            )

        password_reset_service = await get_password_reset_service()
        result = await password_reset_service.reset_password(
            password_reset.token,
            password_reset.password
        )

        if result["success"]:
            return APIResponse(
                success=True,
                message=result["message"],
                data={}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置密码失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务异常，请稍后重试"
        )


@router.post("/logout", response_model=APIResponse)
async def logout(current_user: UserInfo = Depends(get_current_active_user)):
    """
    用户登出

    注意：JWT是无状态的，真正的登出需要在客户端删除token
    这个接口主要用于记录日志和清理服务端资源
    """
    try:
        logger.info(f"用户登出: {current_user.username}")

        return APIResponse(
            success=True,
            message="登出成功",
            data={}
        )

    except Exception as e:
        logger.error(f"登出失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出服务异常"
        )








@router.get("/permissions", response_model=APIResponse)
async def get_current_user_permissions(
    permissions_info: dict = Depends(get_user_permissions_info)
):
    """
    获取当前用户权限信息
    """
    return APIResponse(
        success=True,
        message="获取权限信息成功",
        data=permissions_info
    )


@router.get("/users/{user_id}", response_model=APIResponse)
async def get_user_by_id(
    user_id: str,
    current_user: UserInfo = Depends(require_user_read_permission),
    user_service: FastAPIUserService = Depends(get_user_service)
):
    """
    根据ID获取用户信息（需要用户读取权限）
    """
    try:
        user_data = await user_service.get_user_by_id(user_id)

        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        user_info = UserInfo(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            is_admin=user_data.get('is_admin', False),
            created_at=user_data['created_at']
        )

        return APIResponse(
            success=True,
            message="获取用户信息成功",
            data=user_info.dict()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )
