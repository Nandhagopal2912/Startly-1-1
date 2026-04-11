"""Supabase OAuth and authentication handlers"""

import os
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from supabase_config import get_supabase_client, get_supabase_service_client
from redis_cache import cache_user_data, get_user_cache

load_dotenv()


class AuthHandler:
    """Handle authentication with Supabase"""
    
    @staticmethod
    def get_oauth_providers():
        """Get available OAuth providers"""
        return {
            "google": {
                "name": "Google",
                "icon": "google",
                "enabled": True
            },
            "github": {
                "name": "GitHub",
                "icon": "github",
                "enabled": True
            },
            "microsoft": {
                "name": "Microsoft",
                "icon": "microsoft",
                "enabled": True
            }
        }
    
    @staticmethod
    def get_oauth_url(provider: str) -> str:
        """Get OAuth URL for provider"""
        supabase = get_supabase_client()
        
        try:
            supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
            response = supabase.auth.sign_in_with_oauth({
                "provider": provider,
                "options": {
                    "redirectTo": f"{supabase_url}/auth/v1/callback"
                }
            })

            # Supabase Python may return a dict-like response or an object.
            oauth_url = None
            if isinstance(response, dict):
                oauth_url = response.get("url") or response.get("data", {}).get("url")
            else:
                oauth_url = getattr(response, "url", None)
                if oauth_url is None and hasattr(response, "data"):
                    oauth_url = response.data.get("url") if isinstance(response.data, dict) else None

            if not oauth_url:
                raise ValueError("Unable to resolve OAuth redirect URL from Supabase response")

            return oauth_url
        except Exception as e:
            print(f"Error getting OAuth URL: {e}")
            raise
    
    @staticmethod
    def handle_oauth_callback(provider: str, code: str) -> Dict[str, Any]:
        """Handle OAuth callback and create/update user"""
        supabase = get_supabase_client()
        
        try:
            # Exchange code for session
            response = supabase.auth.sign_in_with_code({
                "code": code,
                "provider": provider
            })
            
            session = response.session
            user = response.user
            
            if not session or not user:
                raise ValueError("Failed to authenticate")
            
            # Create/update user profile in database
            AuthHandler._upsert_user(user, provider)
            
            # Cache user data
            cache_user_data(user.id, {
                "id": user.id,
                "email": user.email,
                "provider": provider,
                "created_at": datetime.now().isoformat()
            })
            
            return {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "user_metadata": user.user_metadata or {}
                }
            }
        except Exception as e:
            print(f"OAuth callback error: {e}")
            raise
    
    @staticmethod
    def _upsert_user(user: Any, provider: str):
        """Create or update user in database"""
        supabase = get_supabase_service_client()
        
        try:
            # Extract metadata
            metadata = user.user_metadata or {}
            full_name = metadata.get("full_name", metadata.get("name", ""))
            avatar_url = metadata.get("avatar_url", "")
            
            # Try to insert, on conflict update
            supabase.table("users").upsert({
                "id": user.id,
                "email": user.email,
                "full_name": full_name,
                "avatar_url": avatar_url,
                "updated_at": datetime.now().isoformat()
            }).execute()
        except Exception as e:
            print(f"Error upserting user: {e}")
    
    @staticmethod
    def get_current_user(token: str) -> Optional[Dict[str, Any]]:
        """Get current user from Supabase JWT token"""
        supabase = get_supabase_client()
        service_supabase = get_supabase_service_client()

        try:
            # Verify token with Supabase (this validates the JWT)
            response = supabase.auth.get_user(token)
            user = response.user

            if not user:
                return None

            # Try to get from cache first
            cached = get_user_cache(user.id)
            if cached:
                return cached

            # Get from database
            user_data = service_supabase.table("users").select("*").eq("id", user.id).single().execute()

            if user_data.data:
                cache_user_data(user.id, user_data.data)
                return user_data.data

            metadata = user.user_metadata or {}
            full_name = metadata.get("full_name", metadata.get("name", ""))
            avatar_url = metadata.get("avatar_url", "")

            upsert_result = service_supabase.table("users").upsert({
                "id": user.id,
                "email": user.email,
                "full_name": full_name,
                "avatar_url": avatar_url,
                "updated_at": datetime.now().isoformat()
            }).execute()

            user_record = {
                "id": user.id,
                "email": user.email,
                "full_name": full_name,
                "avatar_url": avatar_url,
                "company": None
            }

            cache_user_data(user.id, user_record)
            return user_record
        except Exception as e:
            print(f"Error getting current user: {e}")
            return None
