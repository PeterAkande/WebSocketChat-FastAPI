import traceback
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketException, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.exceptions import HTTPException

from connection_manager import ConnectionManager
from models.register_to_room_model import RegisterToRoom
from models.message_to_room_model import MessageToRoomModel

number_of_socket_connections = 0
connection_manager = ConnectionManager()

app = FastAPI()


@app.on_event("startup")
async def startup():
    print("Conneting to redis")
    await connection_manager.connect_broadcaster()
    print("Connected to redis")


@app.on_event("shutdown")
async def shutdown():
    print("Disconnecting from redis")
    await connection_manager.disconnect_broadcaster()
    print("Disconnected from redis")



@app.get("/")
async def get():
    return FileResponse("static/index.html")


@app.post("/register_to_room/")
async def register_user_to_room(body: RegisterToRoom):
    """
    This route would register a user to a route
    """

    is_added, message = await connection_manager.add_user_connection_to_room(user_id=body.user_id, room_id=body.room_id)

    print(connection_manager.user_connections)
    print(connection_manager.connections)
    # Do whatever you like with is_added later

    if not is_added:
        raise HTTPException(detail={"message": message}, status_code=400)

    return {
        "message": message
    }


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(user_id: str, websocket: WebSocket):
    await websocket.accept()
    global number_of_socket_connections

    # Add the user to the connection stack
    await connection_manager.save_user_connection_record(user_id=user_id, ws_connection=websocket)
    try:
        number_of_socket_connections += 1
        while True:
            data = await websocket.receive_json()

            room_id = data["room_id"]
            message_sent = data["message"]
            user_id = data["user_id"]

            message = MessageToRoomModel(message=message_sent, room_id=room_id, user_id=user_id)

            await connection_manager.send_message_to_room(message=message)
    except WebSocketDisconnect:
        # Remove the user from the connection stack
        connection_manager.remove_user_connection(user_id=user_id)

    except WebSocketException as e:
        traceback.print_exc()
        #

        print("An error occurred and i dont know the details")
