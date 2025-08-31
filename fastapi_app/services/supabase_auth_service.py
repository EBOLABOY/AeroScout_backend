#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supabase 认证服务
使用 Supabase Auth 的完整功能，包括邮件验证、密码重置等
"""

import os
from typing import Dict, Any, Optional
from loguru import logger
from supabase import Client

from fastapi_app.config.supabase_config import get_supabase_client


class SupabaseAuthService:
    """Supabase 认证服务"""
    
    def __init__(self):
        """初始化 Supabase 认证服务"""
        # 使用 anon key 进行认证操作
        self.client: Optional[Client] = get_supabase_client(use_service_key=False)
        self.admin_client: Optional[Client] = get_supabase_client(use_service_key=True)
        
        # 网站配置
        self.site_url = os.getenv("SITE_URL", "https://ticketradar.izlx.de")
        self.redirect_url = f"{self.site_url}/auth/callback"
        
        logger.info("SupabaseAuthService 初始化完成")

    async def sign_up_with_email(
        self, 
        email: str, 
        password: str, 
        username: str,
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        使用邮箱注册用户（Supabase Auth）
        
        Args:
            email: 用户邮箱
            password: 密码
            username: 用户名
            user_metadata: 用户元数据
            
        Returns:
            注册结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            # 准备用户元数据
            metadata = user_metadata or {}
            metadata["username"] = username
            
            # 使用 Supabase Auth 注册
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": metadata,
                    "redirect_to": self.redirect_url
                }
            })
            
            if response.user:
                logger.info(f"用户注册成功: {email}, 需要邮箱验证")
                return {
                    "success": True,
                    "message": "注册成功，请检查邮箱确认注册",
                    "user": response.user,
                    "session": response.session,
                    "email_verification_required": True
                }
            else:
                logger.warning(f"用户注册失败: {email}")
                return {"success": False, "error": "注册失败"}
                
        except Exception as e:
            logger.error(f"用户注册异常: {e}")
            return {"success": False, "error": str(e)}

    async def sign_in_with_email(self, email: str, password: str) -> Dict[str, Any]:
        """
        使用邮箱登录
        
        Args:
            email: 邮箱
            password: 密码
            
        Returns:
            登录结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user and response.session:
                logger.info(f"用户登录成功: {email}")
                return {
                    "success": True,
                    "user": response.user,
                    "session": response.session
                }
            else:
                return {"success": False, "error": "登录失败，请检查邮箱和密码"}
                
        except Exception as e:
            logger.error(f"用户登录异常: {e}")
            return {"success": False, "error": str(e)}

    async def sign_out(self, access_token: str) -> Dict[str, Any]:
        """
        用户登出
        
        Args:
            access_token: 访问令牌
            
        Returns:
            登出结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            # 设置访问令牌
            self.client.auth.set_session(access_token, None)
            
            # 登出
            response = self.client.auth.sign_out()
            
            logger.info("用户登出成功")
            return {"success": True, "message": "登出成功"}
            
        except Exception as e:
            logger.error(f"用户登出异常: {e}")
            return {"success": False, "error": str(e)}

    async def verify_email(self, token: str, email: str) -> Dict[str, Any]:
        """
        验证邮箱
        
        Args:
            token: 验证令牌
            email: 邮箱地址
            
        Returns:
            验证结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            response = self.client.auth.verify_otp({
                "token": token,
                "type": "signup",
                "email": email
            })
            
            if response.user and response.session:
                logger.info(f"邮箱验证成功: {email}")
                return {
                    "success": True,
                    "message": "邮箱验证成功",
                    "user": response.user,
                    "session": response.session
                }
            else:
                return {"success": False, "error": "邮箱验证失败，令牌可能已过期"}
                
        except Exception as e:
            logger.error(f"邮箱验证异常: {e}")
            return {"success": False, "error": str(e)}

    async def resend_confirmation_email(self, email: str) -> Dict[str, Any]:
        """
        重新发送确认邮件
        
        Args:
            email: 邮箱地址
            
        Returns:
            发送结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            response = self.client.auth.resend({
                "type": "signup",
                "email": email,
                "options": {
                    "redirect_to": self.redirect_url
                }
            })
            
            logger.info(f"重新发送确认邮件: {email}")
            return {"success": True, "message": "确认邮件已重新发送"}
            
        except Exception as e:
            logger.error(f"重新发送确认邮件异常: {e}")
            return {"success": False, "error": str(e)}

    async def send_password_reset_email(self, email: str) -> Dict[str, Any]:
        """
        发送密码重置邮件
        
        Args:
            email: 邮箱地址
            
        Returns:
            发送结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            response = self.client.auth.reset_password_email(email, {
                "redirect_to": f"{self.site_url}/auth/reset-password"
            })
            
            logger.info(f"密码重置邮件发送成功: {email}")
            return {"success": True, "message": "密码重置邮件已发送"}
            
        except Exception as e:
            logger.error(f"发送密码重置邮件异常: {e}")
            return {"success": False, "error": str(e)}

    async def update_password(self, access_token: str, new_password: str) -> Dict[str, Any]:
        """
        更新密码
        
        Args:
            access_token: 访问令牌
            new_password: 新密码
            
        Returns:
            更新结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            # 设置访问令牌
            self.client.auth.set_session(access_token, None)
            
            response = self.client.auth.update_user({
                "password": new_password
            })
            
            if response.user:
                logger.info(f"密码更新成功: {response.user.email}")
                return {
                    "success": True,
                    "message": "密码更新成功",
                    "user": response.user
                }
            else:
                return {"success": False, "error": "密码更新失败"}
                
        except Exception as e:
            logger.error(f"密码更新异常: {e}")
            return {"success": False, "error": str(e)}

    async def update_email(self, access_token: str, new_email: str) -> Dict[str, Any]:
        """
        更新邮箱地址
        
        Args:
            access_token: 访问令牌
            new_email: 新邮箱地址
            
        Returns:
            更新结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            # 设置访问令牌
            self.client.auth.set_session(access_token, None)
            
            response = self.client.auth.update_user({
                "email": new_email
            })
            
            if response.user:
                logger.info(f"邮箱更新成功，需要验证新邮箱: {new_email}")
                return {
                    "success": True,
                    "message": "邮箱更新成功，请检查新邮箱验证邮件",
                    "user": response.user,
                    "email_verification_required": True
                }
            else:
                return {"success": False, "error": "邮箱更新失败"}
                
        except Exception as e:
            logger.error(f"邮箱更新异常: {e}")
            return {"success": False, "error": str(e)}

    async def send_magic_link(self, email: str) -> Dict[str, Any]:
        """
        发送魔法链接（无密码登录）
        
        Args:
            email: 邮箱地址
            
        Returns:
            发送结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            response = self.client.auth.sign_in_with_otp({
                "email": email,
                "options": {
                    "should_create_user": False,
                    "redirect_to": self.redirect_url
                }
            })
            
            logger.info(f"魔法链接发送成功: {email}")
            return {"success": True, "message": "魔法链接已发送到您的邮箱"}
            
        except Exception as e:
            logger.error(f"发送魔法链接异常: {e}")
            return {"success": False, "error": str(e)}

    async def verify_magic_link(self, token: str, email: str) -> Dict[str, Any]:
        """
        验证魔法链接
        
        Args:
            token: 验证令牌
            email: 邮箱地址
            
        Returns:
            验证结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            response = self.client.auth.verify_otp({
                "token": token,
                "type": "email",
                "email": email
            })
            
            if response.user and response.session:
                logger.info(f"魔法链接验证成功: {email}")
                return {
                    "success": True,
                    "message": "登录成功",
                    "user": response.user,
                    "session": response.session
                }
            else:
                return {"success": False, "error": "魔法链接验证失败"}
                
        except Exception as e:
            logger.error(f"魔法链接验证异常: {e}")
            return {"success": False, "error": str(e)}

    async def get_user_by_access_token(self, access_token: str) -> Dict[str, Any]:
        """
        根据访问令牌获取用户信息
        
        Args:
            access_token: 访问令牌
            
        Returns:
            用户信息
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            # 使用 Supabase 官方推荐方法：通过 REST API 验证token
            import httpx
            import os
            
            # 直接调用 Supabase Auth API
            url = f"{os.getenv('SUPABASE_URL')}/auth/v1/user"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "apikey": os.getenv("SUPABASE_ANON_KEY")
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    user_data = response.json()
                    
                    # 最佳实践：使用 Supabase 库提供的用户类型
                    # 创建一个与原始 Supabase User 兼容的对象
                    from types import SimpleNamespace
                    
                    # 将 JSON 转换为对象，确保所有字段都存在
                    user_obj = SimpleNamespace(**{
                        'id': user_data.get('id'),
                        'email': user_data.get('email'),
                        'user_metadata': user_data.get('user_metadata', {}),
                        'app_metadata': user_data.get('app_metadata', {}),
                        'created_at': user_data.get('created_at'),
                        'updated_at': user_data.get('updated_at'),
                        'email_confirmed_at': user_data.get('email_confirmed_at'),
                        'phone': user_data.get('phone'),
                        'phone_confirmed_at': user_data.get('phone_confirmed_at'),
                        'confirmation_sent_at': user_data.get('confirmation_sent_at'),
                        'recovery_sent_at': user_data.get('recovery_sent_at'),
                        'email_change_sent_at': user_data.get('email_change_sent_at'),
                        'new_email': user_data.get('new_email'),
                        'invited_at': user_data.get('invited_at'),
                        'action_link': user_data.get('action_link'),
                        'aud': user_data.get('aud'),
                        'role': user_data.get('role'),
                        'last_sign_in_at': user_data.get('last_sign_in_at'),
                        'confirmed_at': user_data.get('confirmed_at'),
                        'email_change': user_data.get('email_change'),
                        'phone_change': user_data.get('phone_change'),
                        'banned_until': user_data.get('banned_until')
                    })
                    
                    return {
                        "success": True,
                        "user": user_obj
                    }
                else:
                    return {"success": False, "error": f"Token验证失败: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Token验证异常: {e}")
            return {"success": False, "error": str(e)}

    async def sign_in_with_google(
        self, 
        redirect_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用Google OAuth登录
        
        Args:
            redirect_to: 登录成功后的跳转URL
            
        Returns:
            OAuth登录结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            # 构建重定向选项
            options = {}
            if redirect_to:
                options["redirectTo"] = redirect_to
            else:
                options["redirectTo"] = f"{self.site_url}/dashboard"
            
            # 发起Google OAuth登录
            response = self.client.auth.sign_in_with_oauth({
                "provider": "google",
                "options": options
            })
            
            if response.url:
                logger.info("Google OAuth登录URL生成成功")
                return {
                    "success": True,
                    "auth_url": response.url,
                    "message": "请跳转到授权URL完成Google登录"
                }
            else:
                return {"success": False, "error": "生成Google登录URL失败"}
                
        except Exception as e:
            logger.error(f"Google OAuth登录异常: {e}")
            return {"success": False, "error": str(e)}

    async def handle_oauth_callback(
        self, 
        code: str, 
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理OAuth回调
        
        Args:
            code: 授权码
            state: 状态参数
            
        Returns:
            回调处理结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            # 使用授权码交换token
            response = self.client.auth.exchange_code_for_session(code)
            
            if response.user and response.session:
                logger.info(f"Google OAuth回调处理成功: {response.user.email}")
                return {
                    "success": True,
                    "message": "Google登录成功",
                    "user": response.user,
                    "session": response.session
                }
            else:
                return {"success": False, "error": "OAuth回调处理失败"}
                
        except Exception as e:
            logger.error(f"OAuth回调处理异常: {e}")
            return {"success": False, "error": str(e)}

    async def get_google_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        获取Google用户信息
        
        Args:
            access_token: Google访问令牌
            
        Returns:
            用户信息
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            # 设置访问令牌并获取用户信息
            self.client.auth.set_session(access_token, None)
            response = self.client.auth.get_user()
            
            if response.user:
                # 提取Google特有的用户信息
                user_metadata = response.user.user_metadata or {}
                app_metadata = response.user.app_metadata or {}
                
                user_info = {
                    "id": response.user.id,
                    "email": response.user.email,
                    "email_verified": response.user.email_verified,
                    "phone": response.user.phone,
                    "created_at": response.user.created_at,
                    "updated_at": response.user.updated_at,
                    "last_sign_in_at": response.user.last_sign_in_at,
                    
                    # Google特有信息
                    "provider": "google",
                    "google_id": user_metadata.get("sub"),
                    "name": user_metadata.get("name"),
                    "given_name": user_metadata.get("given_name"),
                    "family_name": user_metadata.get("family_name"),
                    "picture": user_metadata.get("picture"),
                    "locale": user_metadata.get("locale"),
                    
                    # 原始元数据
                    "user_metadata": user_metadata,
                    "app_metadata": app_metadata
                }
                
                return {
                    "success": True,
                    "user_info": user_info
                }
            else:
                return {"success": False, "error": "获取用户信息失败"}
                
        except Exception as e:
            logger.error(f"获取Google用户信息异常: {e}")
            return {"success": False, "error": str(e)}

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        刷新访问令牌
        
        Args:
            refresh_token: 刷新令牌
            
        Returns:
            刷新结果
        """
        try:
            if not self.client:
                return {"success": False, "error": "Supabase 客户端未初始化"}
            
            response = self.client.auth.refresh_session(refresh_token)
            
            if response.session:
                logger.info("访问令牌刷新成功")
                return {
                    "success": True,
                    "session": response.session
                }
            else:
                return {"success": False, "error": "令牌刷新失败"}
                
        except Exception as e:
            logger.error(f"刷新访问令牌异常: {e}")
            return {"success": False, "error": str(e)}


# 全局服务实例
_supabase_auth_service: Optional[SupabaseAuthService] = None


def get_supabase_auth_service() -> SupabaseAuthService:
    """获取 Supabase 认证服务实例（单例模式）"""
    global _supabase_auth_service
    if _supabase_auth_service is None:
        _supabase_auth_service = SupabaseAuthService()
    return _supabase_auth_service