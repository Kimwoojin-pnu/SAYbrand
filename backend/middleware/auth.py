from dataclasses import dataclass

from fastapi import HTTPException, Request


async def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "id": user_id,
        "name": request.session.get("user_name", ""),
        "email": request.session.get("user_email", ""),
        "avatar": request.session.get("user_avatar", ""),
        "subscription_status": request.session.get("subscription_status", "free"),
    }


@dataclass
class LoginUser:
    id: int
    name: str
    email: str


async def require_login(request: Request) -> LoginUser:
    """속성 접근(user.id)이 필요한 엔드포인트용 인증 의존성."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return LoginUser(
        id=int(user_id),
        name=request.session.get("user_name", ""),
        email=request.session.get("user_email", ""),
    )
