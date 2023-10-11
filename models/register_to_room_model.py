from pydantic import BaseModel


class RegisterToRoom(BaseModel):
    user_id: str
    room_id: str
