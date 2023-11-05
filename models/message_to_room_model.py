from pydantic import BaseModel


class MessageToRoomModel(BaseModel):
    user_id: str
    message: str
    room_id: str
