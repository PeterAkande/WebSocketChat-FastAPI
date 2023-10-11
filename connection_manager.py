import traceback
from typing import Dict, Set, List, Tuple
from operator import itemgetter

from fastapi import WebSocket
from starlette.websockets import WebSocketState


class ConnectionManager:
    """
    This would handle all Message broadcast and all connections to the Service.
    """

    def __init__(self):
        self.connections: Dict[str, Set[str]] = {}  # The Room and the set of users connected
        self.user_connections: Dict[str, WebSocket] = {}  # the user connections

    async def save_user_connection_record(self, ws_connection: WebSocket, user_id: str):
        """
        This would save a user record to the Websocket connections that the connection manager is currently keeping
        """

        self.user_connections[user_id] = ws_connection
        await self.send_message_to_ws_connection(message="Connection successful", ws_connection=ws_connection)

    async def add_user_connection_to_room(self, room_id: str, user_id: str) -> (bool, str):
        """
        This function would add a user to a Room
        This user id would be added to the ids of the users that are listening to a room
        """

        # Try to get the user details from the dictionary of connections
        # It's a HashMap, so the Time Complexity is O(1)

        user_ws_connection = self.user_connections.get(user_id, None)

        if user_ws_connection is None:
            return False, "User Not Found"

        # The user connection was gotten.

        is_connection_active = await self.check_if_ws_connection_is_still_active(user_ws_connection)

        if not is_connection_active:
            self.user_connections.pop(user_id)
            return False, "Connection not Active"

        # Check if the room ID exists. If  it does not, create one.
        if room_id not in self.connections.keys():
            self.connections[room_id] = {user_id}
        else:
            self.connections[room_id].add(user_id)

        return True, "Connection Successful"

    async def check_if_ws_connection_is_still_active(self, ws_connection: WebSocket, message=".") -> bool:
        """
        This function would check if the connection is still active. It tries to send a message
        """

        if not (
                ws_connection.application_state == WebSocketState.CONNECTED and ws_connection.client_state == WebSocketState.CONNECTED):
            return False

        # Try to send a message
        try:
            await ws_connection.send_text(message)
        except RuntimeError:
            return False

        except Exception as e:
            traceback.print_exc()
            return False

        return True

    async def send_message_to_room(self, room_id: str, message: str):
        """
        Messages in this Program are Texts.
        """

        room_connections = self.connections.get(room_id, {})
        if len(room_connections) == 0:
            return
        users_ws_connections = itemgetter(*room_connections)(self.user_connections)

        print(users_ws_connections)
        if type(users_ws_connections) is not tuple:
            users_ws_connections = [users_ws_connections]

        for connection in users_ws_connections:
            is_sent, sent_message_response_info = await self.send_message_to_ws_connection(
                message=f"{message} from room: {room_id}", ws_connection=connection)

            # It can be chosen to remove the connection from the self.user_connections if is_sent is False.

    async def send_message_to_ws_connection(self, message: str, ws_connection: WebSocket) -> (bool, str):
        try:
            await ws_connection.send_text(message)
            return True, "Message sent!"
        except RuntimeError:
            return False, "Message Not Sent, Websocket is disconnected"

        except Exception as e:
            traceback.print_exc()

            return False, "Error Sending Message"

    def remove_user_connection(self, user_id):
        self.user_connections.pop(user_id)
