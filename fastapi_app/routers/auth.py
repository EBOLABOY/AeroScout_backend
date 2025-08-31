"""
FastAPI认证路由 - 纯Supabase认证
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer
from loguru import logger

from fastapi_app.models.auth import (
    UserLogin,
    UserRegister,
    UserInfo,
    UserLevel,
    TokenResponse,
    UserLevelUpdate,
    UserPermissions,
    PasswordChange,
    PasswordResetRequest,
    PasswordResetConfirm
)
from fastapi_app.models.common import APIResponse
from fastapi_app.dependencies.auth import (
    get_current_active_user,
    SecurityConfig
)
from fastapi_app.services.user_level_service import get_user_level_service
from fastapi_app.services.supabase_service import get_supabase_service
from fastapi_app.services.supabase_auth_service import SupabaseAuthService, get_supabase_auth_service
from fastapi_app.dependencies.permissions import (
    get_user_permissions_info,
    check_permission,
    Permission
)
from fastapi_app.services.quota_service import get_quota_service, QuotaType
from fastapi_app.services.usage_stats_service import get_usage_stats_service

# 创建路由器
router = APIRouter()
security = HTTPBearer()


@router.post("/login", response_model=APIResponse)
async def login(user_login: UserLogin):
    """
    用户登录 - 纯Supabase认证
    """
    try:
        # 使用Supabase认证服务
        auth_service = get_supabase_auth_service()
        result = await auth_service.sign_in_with_email(user_login.username, user_login.password)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["error"]
            )
        
        supabase_user = result["user"]
        supabase_session = result["session"]
        
        # 同步用户数据到业务表
        db_service = await get_supabase_service()
        await db_service.sync_user_from_supabase_auth(supabase_user)
        
        # 构建用户信息
        user_info = UserInfo(
            id=supabase_user.id,
            username=supabase_user.user_metadata.get("username") or supabase_user.email.split("@")[0],
            email=supabase_user.email,
            is_admin=supabase_user.app_metadata.get("is_admin", False),
            user_level_id=supabase_user.user_metadata.get("user_level_id"),
            user_level_name=supabase_user.user_metadata.get("user_level_name", "user"),
            created_at=supabase_user.created_at
        )
        
        # 构建Token响应
        token_response = TokenResponse(
            access_token=supabase_session.access_token,
            token_type="bearer",
            expires_in=supabase_session.expires_in or 3600,
            user_info=user_info
        )
        
        logger.info(f"用户登录成功: {supabase_user.email}")
        
        return APIResponse(
            success=True,
            message="登录成功",
            data=token_response.model_dump()
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
    获取当前用户信息 - Supabase认证
    """
    try:
        return APIResponse(
            success=True,
            message="获取用户信息成功",
            data=current_user.model_dump()
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


# ==================== Supabase 认证API ====================

@router.post("/supabase/register", response_model=APIResponse)
async def supabase_register(user_register: UserRegister):
    """
    使用Supabase Auth注册用户（包含邮件验证）
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
        
        # 使用Supabase Auth服务注册
        auth_service = get_supabase_auth_service()
        result = await auth_service.sign_up_with_email(
            email=user_register.email,
            password=user_register.password,
            username=user_register.username,
            user_metadata={
                "username": user_register.username,
                "registration_date": datetime.now().isoformat()
            }
        )
        
        if result["success"]:
            logger.info(f"Supabase用户注册成功: {user_register.username}")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={
                    "username": user_register.username,
                    "email": user_register.email,
                    "email_verification_required": result.get("email_verification_required", True)
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Supabase注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册服务异常"
        )


@router.post("/supabase/verify-email", response_model=APIResponse)
async def verify_email(
    token: str = Query(..., description="验证令牌"),
    email: str = Query(..., description="邮箱地址")
):
    """
    验证邮箱地址
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.verify_email(token, email)
        
        if result["success"]:
            logger.info(f"邮箱验证成功: {email}")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={
                    "email": email,
                    "verified": True,
                    "user": result.get("user"),
                    "session": result.get("session")
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"邮箱验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="邮箱验证服务异常"
        )


@router.post("/supabase/resend-confirmation", response_model=APIResponse)
async def resend_confirmation_email(
    email: str = Query(..., description="邮箱地址")
):
    """
    重新发送确认邮件
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.resend_confirmation_email(email)
        
        if result["success"]:
            logger.info(f"重新发送确认邮件成功: {email}")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={"email": email}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新发送确认邮件失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="邮件发送服务异常"
        )


@router.post("/supabase/send-magic-link", response_model=APIResponse)
async def send_magic_link(
    email: str = Query(..., description="邮箱地址")
):
    """
    发送魔法链接（无密码登录）
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.send_magic_link(email)
        
        if result["success"]:
            logger.info(f"魔法链接发送成功: {email}")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={"email": email}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送魔法链接失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="魔法链接发送服务异常"
        )


@router.post("/supabase/verify-magic-link", response_model=APIResponse)
async def verify_magic_link(
    token: str = Query(..., description="验证令牌"),
    email: str = Query(..., description="邮箱地址")
):
    """
    验证魔法链接
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.verify_magic_link(token, email)
        
        if result["success"]:
            logger.info(f"魔法链接验证成功: {email}")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={
                    "email": email,
                    "user": result.get("user"),
                    "session": result.get("session")
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"魔法链接验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="魔法链接验证服务异常"
        )


@router.post("/supabase/send-reset-password", response_model=APIResponse)
async def supabase_send_reset_password(
    email: str = Query(..., description="邮箱地址")
):
    """
    发送Supabase密码重置邮件
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.send_password_reset_email(email)
        
        if result["success"]:
            logger.info(f"Supabase密码重置邮件发送成功: {email}")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={"email": email}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送Supabase密码重置邮件失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码重置邮件发送服务异常"
        )


@router.post("/supabase/update-password", response_model=APIResponse)
async def supabase_update_password(
    access_token: str = Query(..., description="Supabase访问令牌"),
    new_password: str = Query(..., description="新密码")
):
    """
    更新Supabase用户密码
    """
    try:
        # 验证密码强度
        if not SecurityConfig.validate_password(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"密码长度必须在{SecurityConfig.MIN_PASSWORD_LENGTH}-{SecurityConfig.MAX_PASSWORD_LENGTH}字符之间"
            )
        
        auth_service = get_supabase_auth_service()
        result = await auth_service.update_password(access_token, new_password)
        
        if result["success"]:
            logger.info("Supabase密码更新成功")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={"user": result.get("user")}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Supabase密码更新失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码更新服务异常"
        )


@router.post("/supabase/update-email", response_model=APIResponse)
async def supabase_update_email(
    access_token: str = Query(..., description="Supabase访问令牌"),
    new_email: str = Query(..., description="新邮箱地址")
):
    """
    更新Supabase用户邮箱
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.update_email(access_token, new_email)
        
        if result["success"]:
            logger.info(f"Supabase邮箱更新成功: {new_email}")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={
                    "new_email": new_email,
                    "email_verification_required": result.get("email_verification_required", True),
                    "user": result.get("user")
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Supabase邮箱更新失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="邮箱更新服务异常"
        )


@router.get("/supabase/user", response_model=APIResponse)
async def get_supabase_user(
    access_token: str = Query(..., description="Supabase访问令牌")
):
    """
    获取Supabase用户信息
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.get_user_by_access_token(access_token)
        
        if result["success"]:
            return APIResponse(
                success=True,
                message="获取用户信息成功",
                data={"user": result["user"]}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Supabase用户信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息服务异常"
        )


# ==================== 用户设置管理API ====================

@router.get("/settings/notifications", response_model=APIResponse)
async def get_notification_settings(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取用户的通知设置 - Supabase认证
    """
    try:
        db_service = await get_supabase_service()
        user_data = await db_service.get_user_by_id(current_user.id)
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 获取用户元数据中的通知设置
        user_metadata = user_data.get('user_metadata', {})
        notification_settings = user_metadata.get('notification_settings', {})
        
        # 返回通知设置（不包含敏感信息如完整的token）
        safe_settings = {
            'email_notifications': notification_settings.get('email_notifications', False),
            'price_alerts': notification_settings.get('price_alerts', True),
            'pushplus_configured': bool(notification_settings.get('pushplus_token')),
            'pushplus_token_preview': notification_settings.get('pushplus_token', '')[:8] + '...' if notification_settings.get('pushplus_token') else None
        }
        
        return APIResponse(
            success=True,
            message="获取通知设置成功",
            data=safe_settings
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取通知设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取通知设置失败"
        )


@router.put("/settings/notifications", response_model=APIResponse)
async def update_notification_settings(
    settings: Dict[str, Any],
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    更新用户的通知设置 - Supabase认证
    """
    try:
        db_service = await get_supabase_service()
        user_data = await db_service.get_user_by_id(current_user.id)
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 获取现有的用户元数据
        user_metadata = user_data.get('user_metadata', {})
        notification_settings = user_metadata.get('notification_settings', {})
        
        # 更新通知设置
        if 'email_notifications' in settings:
            notification_settings['email_notifications'] = bool(settings['email_notifications'])
        
        if 'price_alerts' in settings:
            notification_settings['price_alerts'] = bool(settings['price_alerts'])
        
        if 'pushplus_token' in settings:
            # 验证PushPlus token格式（如果提供）
            token = settings['pushplus_token'].strip() if settings['pushplus_token'] else None
            if token and len(token) < 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PushPlus token格式无效"
                )
            notification_settings['pushplus_token'] = token
        
        # 更新用户元数据
        user_metadata['notification_settings'] = notification_settings
        
        # 保存到数据库
        success = await db_service.update_user(current_user.id, {
            'user_metadata': user_metadata
        })
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存设置失败"
            )
        
        logger.info(f"用户 {current_user.username} 更新通知设置成功")
        
        return APIResponse(
            success=True,
            message="通知设置更新成功",
            data={
                'pushplus_configured': bool(notification_settings.get('pushplus_token')),
                'email_notifications': notification_settings.get('email_notifications', False),
                'price_alerts': notification_settings.get('price_alerts', True)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新通知设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新通知设置失败"
        )


# ==================== Google OAuth 认证API ====================

@router.post("/google/signin", response_model=APIResponse)
async def google_signin(
    redirect_to: Optional[str] = Query(None, description="登录成功后的跳转URL")
):
    """
    Google OAuth登录 - 获取授权URL
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.sign_in_with_google(redirect_to)
        
        if result["success"]:
            logger.info("Google OAuth URL生成成功")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={
                    "auth_url": result["auth_url"],
                    "provider": "google"
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google登录服务异常"
        )


@router.post("/google/callback", response_model=APIResponse)
async def google_callback(
    code: str = Query(..., description="Google授权码"),
    state: Optional[str] = Query(None, description="状态参数")
):
    """
    Google OAuth回调处理
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.handle_oauth_callback(code, state)
        
        if result["success"]:
            logger.info("Google OAuth回调处理成功")
            
            # 提取用户信息
            user = result.get("user")
            session = result.get("session")
            
            return APIResponse(
                success=True,
                message=result["message"],
                data={
                    "user": user,
                    "session": session,
                    "provider": "google",
                    "access_token": session.access_token if session else None,
                    "refresh_token": session.refresh_token if session else None
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth回调处理失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google回调处理服务异常"
        )


@router.get("/google/user", response_model=APIResponse)
async def get_google_user_info(
    access_token: str = Query(..., description="Google访问令牌")
):
    """
    获取Google用户详细信息
    """
    try:
        auth_service = get_supabase_auth_service()
        result = await auth_service.get_google_user_info(access_token)
        
        if result["success"]:
            return APIResponse(
                success=True,
                message="获取Google用户信息成功",
                data={
                    "user_info": result["user_info"],
                    "provider": "google"
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Google用户信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取Google用户信息服务异常"
        )


@router.post("/social/unified-callback", response_model=APIResponse)
async def unified_social_callback(
    provider: str = Query(..., description="社交登录提供商"),
    code: str = Query(..., description="授权码"),
    state: Optional[str] = Query(None, description="状态参数")
):
    """
    统一的社交登录回调处理（支持扩展其他提供商）
    """
    try:
        auth_service = get_supabase_auth_service()
        
        # 目前只支持Google，后续可扩展支持GitHub、Facebook等
        if provider.lower() == "google":
            result = await auth_service.handle_oauth_callback(code, state)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的社交登录提供商: {provider}"
            )
        
        if result["success"]:
            logger.info(f"{provider} OAuth回调处理成功")
            
            # 提取并规范化用户信息
            user = result.get("user")
            session = result.get("session")
            
            # 统一的响应格式
            unified_data = {
                "provider": provider.lower(),
                "user": user,
                "session": session,
                "tokens": {
                    "access_token": session.access_token if session else None,
                    "refresh_token": session.refresh_token if session else None
                },
                "login_timestamp": datetime.now().isoformat()
            }
            
            return APIResponse(
                success=True,
                message=f"{provider}登录成功",
                data=unified_data
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"{provider} OAuth回调处理失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{provider}回调处理服务异常"
        )








@router.get("/permissions", response_model=APIResponse)
async def get_current_user_permissions(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取当前用户权限信息
    """
    permissions_info = await get_user_permissions_info(current_user)
    return APIResponse(
        success=True,
        message="获取权限信息成功",
        data=permissions_info
    )


@router.get("/users/{user_id}", response_model=APIResponse)
async def get_user_by_id(
    user_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
    auth_service: SupabaseAuthService = Depends(get_supabase_auth_service)
):
    """
    根据ID获取用户信息（需要用户读取权限）
    """
    try:
        # 检查权限
        if not check_permission(current_user, Permission.USER_READ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="缺少用户读取权限"
            )
        
        user_data = await auth_service.get_user_by_id(user_id)

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
            user_level_id=user_data.get('user_level_id'),
            user_level_name=user_data.get('user_level_name', 'user'),
            created_at=user_data['created_at']
        )

        return APIResponse(
            success=True,
            message="获取用户信息成功",
            data=user_info.model_dump()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )


# ==================== 用户等级管理API ====================

@router.get("/levels", response_model=APIResponse)
async def get_user_levels():
    """
    获取所有用户等级列表
    """
    try:
        level_service = await get_user_level_service()
        levels = await level_service.get_all_user_levels()
        
        return APIResponse(
            success=True,
            message="获取用户等级列表成功",
            data=levels
        )
        
    except Exception as e:
        logger.error(f"获取用户等级列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户等级列表失败"
        )


@router.get("/levels/{level_name}", response_model=APIResponse)
async def get_user_level_info(level_name: str):
    """
    获取指定等级的详细信息和权益
    """
    try:
        level_service = await get_user_level_service()
        level_info = await level_service.get_user_level_benefits(level_name)
        
        if not level_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户等级不存在: {level_name}"
            )
        
        return APIResponse(
            success=True,
            message="获取等级信息成功",
            data=level_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取等级信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取等级信息失败"
        )


@router.put("/users/{user_id}/level", response_model=APIResponse)
async def update_user_level(
    user_id: str,
    level_update: UserLevelUpdate,
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    更新用户等级（需要管理员权限）
    """
    try:
        # 检查权限
        if not check_permission(current_user, Permission.USER_WRITE):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="缺少用户写入权限"
            )
        
        level_service = await get_user_level_service()
        
        # 验证等级是否存在
        level_info = await level_service.get_user_level_by_name(level_update.level_name)
        if not level_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"用户等级不存在: {level_update.level_name}"
            )
        
        # 更新用户等级
        success = await level_service.update_user_level(user_id, level_update.level_name)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="更新用户等级失败"
            )
        
        logger.info(f"管理员 {current_user.username} 将用户 {user_id} 等级更新为 {level_update.level_name}")
        
        return APIResponse(
            success=True,
            message="用户等级更新成功",
            data={"level_name": level_update.level_name}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户等级失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户等级失败"
        )


@router.get("/permissions/detailed", response_model=APIResponse)
async def get_detailed_permissions(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取当前用户的详细权限信息（包括等级权益）
    """
    try:
        level_service = await get_user_level_service()
        
        # 获取用户等级权益
        level_benefits = await level_service.get_user_level_benefits(
            current_user.user_level_name
        )
        
        # 获取基本权限信息
        from fastapi_app.dependencies.permissions import get_user_permissions_info
        permissions_info = await get_user_permissions_info(current_user)
        
        # 合并信息
        detailed_info = {
            **permissions_info,
            "level_benefits": level_benefits.get("benefits", {}),
            "level_info": level_benefits.get("level", {})
        }
        
        return APIResponse(
            success=True,
            message="获取详细权限信息成功",
            data=detailed_info
        )
        
    except Exception as e:
        logger.error(f"获取详细权限信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取详细权限信息失败"
        )


# ==================== 配额管理API ====================

async def get_user_quota_info(current_user: UserInfo = Depends(get_current_active_user)) -> Dict[str, Any]:
    """获取用户配额信息依赖"""
    quota_service = await get_quota_service()
    
    # 获取所有配额类型的状态
    quota_info = {}
    quota_types = [QuotaType.SEARCH, QuotaType.AI_SEARCH, QuotaType.MONITOR, QuotaType.EXPORT]
    
    for quota_type in quota_types:
        quota_info[quota_type] = await quota_service.get_user_quota_status(current_user, quota_type)
    
    return {
        "user_id": current_user.id,
        "user_level": current_user.user_level_name,
        "quotas": quota_info,
        "reset_time": "00:00:00 UTC",
        "timezone": "UTC"
    }


@router.get("/quota", response_model=APIResponse)
async def get_user_quota_status(
    quota_info: dict = Depends(get_user_quota_info)
):
    """
    获取当前用户的配额使用情况
    """
    return APIResponse(
        success=True,
        message="获取配额信息成功",
        data=quota_info
    )


@router.get("/quota/{quota_type}", response_model=APIResponse)
async def get_quota_by_type(
    quota_type: str,
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取指定类型的配额信息
    """
    try:
        # 验证配额类型
        valid_quota_types = [QuotaType.SEARCH, QuotaType.AI_SEARCH, QuotaType.MONITOR, QuotaType.EXPORT]
        if quota_type not in valid_quota_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的配额类型: {quota_type}"
            )
        
        quota_service = await get_quota_service()
        quota_status = await quota_service.get_user_quota_status(current_user, quota_type)
        
        return APIResponse(
            success=True,
            message=f"获取{quota_type}配额信息成功",
            data=quota_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配额信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取配额信息失败"
        )


@router.post("/quota/{quota_type}/consume", response_model=APIResponse)
async def consume_user_quota(
    quota_type: str,
    amount: int = 1,
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    消费用户配额（用于测试或手动调整）
    """
    try:
        # 验证输入参数
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="消费数量必须大于0"
            )
        
        if amount > 100:  # 防止一次消费过多
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="单次消费数量不能超过100"
            )
        
        # 验证配额类型
        valid_quota_types = [QuotaType.SEARCH, QuotaType.AI_SEARCH, QuotaType.MONITOR, QuotaType.EXPORT]
        if quota_type not in valid_quota_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的配额类型: {quota_type}"
            )
        
        quota_service = await get_quota_service()
        success = await quota_service.consume_quota(current_user, quota_type, amount)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="配额不足或消费失败"
            )
        
        # 获取更新后的配额状态
        quota_status = await quota_service.get_user_quota_status(current_user, quota_type)
        
        return APIResponse(
            success=True,
            message=f"成功消费{amount}个{quota_type}配额",
            data=quota_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"消费配额失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="消费配额失败"
        )


# ==================== 使用统计API ====================

@router.get("/stats/daily", response_model=APIResponse)
async def get_daily_usage_stats(
    target_date: Optional[str] = Query(None, description="目标日期 (YYYY-MM-DD)"),
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取用户每日使用统计
    """
    try:
        stats_service = await get_usage_stats_service()
        
        from datetime import date
        if target_date:
            try:
                target = date.fromisoformat(target_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="日期格式不正确，请使用 YYYY-MM-DD 格式"
                )
        else:
            target = date.today()
        
        stats = await stats_service.get_user_daily_stats(current_user.id, target)
        
        return APIResponse(
            success=True,
            message=f"获取{target}使用统计成功",
            data=stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取日统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取使用统计失败"
        )


@router.get("/stats/weekly", response_model=APIResponse)
async def get_weekly_usage_stats(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取用户近7天使用统计
    """
    try:
        stats_service = await get_usage_stats_service()
        stats = await stats_service.get_user_weekly_stats(current_user.id)
        
        return APIResponse(
            success=True,
            message="获取周使用统计成功",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"获取周统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取使用统计失败"
        )


@router.get("/stats/monthly", response_model=APIResponse)
async def get_monthly_usage_stats(
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份 (1-12)"),
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取用户月度使用统计
    """
    try:
        if month and (month < 1 or month > 12):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="月份必须在1-12之间"
            )
        
        stats_service = await get_usage_stats_service()
        stats = await stats_service.get_user_monthly_stats(current_user.id, year, month)
        
        return APIResponse(
            success=True,
            message=f"获取{stats['period']}月度统计成功",
            data=stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取月统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取使用统计失败"
        )


@router.get("/stats/summary", response_model=APIResponse)
async def get_system_stats_summary(
    current_user: UserInfo = Depends(get_current_active_user)
):
    """
    获取系统整体统计摘要（管理员功能）
    """
    try:
        # 检查权限
        if not check_permission(current_user, Permission.SYSTEM_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="缺少系统管理权限"
            )
        
        stats_service = await get_usage_stats_service()
        summary = await stats_service.get_system_stats_summary()
        
        return APIResponse(
            success=True,
            message="获取系统统计摘要成功",
            data=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取系统统计摘要失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取系统统计摘要失败"
        )
