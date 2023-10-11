import traceback
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketException, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.exceptions import HTTPException

from connection_manager import ConnectionManager
from models.register_to_room_model import RegisterToRoom

number_of_socket_connections = 0
connection_manager = ConnectionManager()

app = FastAPI()

# this would be the In memory Db. It would house all the websocket connections in soma kind of inverted index
# Structure.
# So it would be like
rooms_hash_map: Dict[str, Set] = {}


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
            message = data["message"]

            await connection_manager.send_message_to_room(message=message, room_id=room_id)
    except WebSocketDisconnect:
        # Remove the user from the connection stack
        connection_manager.remove_user_connection(user_id=user_id)

    except WebSocketException as e:
        traceback.print_exc()

        print("An error occurred and i dont know the details")
