"""Task and analysis data management"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4
from supabase_config import get_supabase_service_client


class TaskManager:
    """Manage user tasks and analyses"""
    
    @staticmethod
    def create_task(
        user_id: str,
        keyword: str,
        location_name: str,
        search_volume: Optional[int] = None,
        ctr_percentage: Optional[float] = None,
        zero_click_risk: Optional[float] = None,
        commercial_intent: Optional[float] = None,
        traffic_opportunity: Optional[float] = None,
        verdict: Optional[str] = None,
        full_results: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Create a new task/analysis record"""
        supabase = get_supabase_service_client()
        
        try:
            task_data = {
                "id": str(uuid4()),
                "user_id": user_id,
                "keyword": keyword,
                "location_name": location_name,
                "search_volume": search_volume,
                "ctr_percentage": ctr_percentage,
                "zero_click_risk": zero_click_risk,
                "commercial_intent": commercial_intent,
                "traffic_opportunity": traffic_opportunity,
                "verdict": verdict,
                "full_results": full_results,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = supabase.table("tasks").insert(task_data).execute()
            return result.data[0] if result.data else task_data
        except Exception as e:
            print(f"Error creating task: {e}")
            raise
    
    @staticmethod
    def get_user_tasks(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all tasks for a user"""
        supabase = get_supabase_service_client()
        
        try:
            result = supabase.table("tasks").select("*") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .range(offset, offset + limit - 1) \
                .execute()
            return result.data or []
        except Exception as e:
            print(f"Error fetching user tasks: {e}")
            return []
    
    @staticmethod
    def get_task(task_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get specific task (with user verification)"""
        supabase = get_supabase_service_client()
        
        try:
            result = supabase.table("tasks").select("*") \
                .eq("id", task_id) \
                .eq("user_id", user_id) \
                .single() \
                .execute()
            return result.data
        except Exception as e:
            print(f"Error fetching task: {e}")
            return None
    
    @staticmethod
    def update_task(task_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a task"""
        supabase = get_supabase_service_client()
        
        try:
            updates["updated_at"] = datetime.now().isoformat()
            result = supabase.table("tasks").update(updates) \
                .eq("id", task_id) \
                .eq("user_id", user_id) \
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating task: {e}")
            raise
    
    @staticmethod
    def delete_task(task_id: str, user_id: str) -> bool:
        """Delete a task"""
        supabase = get_supabase_service_client()
        
        try:
            supabase.table("tasks").delete() \
                .eq("id", task_id) \
                .eq("user_id", user_id) \
                .execute()
            return True
        except Exception as e:
            print(f"Error deleting task: {e}")
            return False
    
    @staticmethod
    def get_user_stats(user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        supabase = get_supabase_service_client()
        
        try:
            # Get total tasks
            tasks_result = supabase.table("tasks").select("id", count="exact") \
                .eq("user_id", user_id) \
                .execute()
            total_tasks = tasks_result.count or 0
            
            # Get average traffic opportunity
            tasks = supabase.table("tasks").select("traffic_opportunity") \
                .eq("user_id", user_id) \
                .execute()
            
            opportunities = [t.get("traffic_opportunity") for t in tasks.data if t.get("traffic_opportunity")]
            avg_opportunity = sum(opportunities) / len(opportunities) if opportunities else 0
            
            return {
                "total_analyses": total_tasks,
                "average_traffic_opportunity": round(avg_opportunity, 2),
                "recent_tasks": TaskManager.get_user_tasks(user_id, limit=5)
            }
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {
                "total_analyses": 0,
                "average_traffic_opportunity": 0,
                "recent_tasks": []
            }
    
    @staticmethod
    def search_tasks(user_id: str, keyword: str) -> List[Dict[str, Any]]:
        """Search user's tasks by keyword"""
        supabase = get_supabase_service_client()
        
        try:
            result = supabase.table("tasks").select("*") \
                .eq("user_id", user_id) \
                .ilike("keyword", f"%{keyword}%") \
                .order("created_at", desc=True) \
                .execute()
            return result.data or []
        except Exception as e:
            print(f"Error searching tasks: {e}")
            return []
