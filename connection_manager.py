import asyncio
import traceback
from typing import Dict, Set, List, Tuple
from operator import itemgetter

from fastapi import WebSocket
from starlette.websockets import WebSocketState
from broadcaster import Broadcast

from models.message_to_room_model import MessageToRoomModel


class ConnectionManager:
    """
    This would handle all Message broadcast and all connections to the Service.
    """

    broadcaster = Broadcast("redis://localhost:6379")

    def __init__(self):
        """
        self.connections would be an in memory db of the users connected to a DB.
        It would function with an forward index like structure.

        Something like:
        {
            room_id: {user1, user2, user3},
            room_id_1: {user1, user3}
        }
        """
        self.connections: Dict[str, Set[str]] = {}  # The Room and the set of users connected
        self.user_connections: Dict[str, WebSocket] = {}  # the user connections

    async def connect_broadcaster(self):
        await self.broadcaster.connect()

    async def disconnect_broadcaster(self):
        await self.broadcaster.disconnect()

    async def save_user_connection_record(self, ws_connection: WebSocket, user_id: str):
        """
        This would save a user record to the Websocket connections that the connection manager is currently keeping
        """

        self.user_connections[user_id] = ws_connection
        await self._send_message_to_ws_connection(message="Connection successful", ws_connection=ws_connection)

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

        is_connection_active = await self._check_if_ws_connection_is_still_active(user_ws_connection)

        if not is_connection_active:
            self.user_connections.pop(user_id)
            return False, "Connection not Active"

        # Check if the room ID exists. If  it does not, create one and listen to it
        if room_id not in self.connections.keys():
            self.connections[room_id] = {user_id}

            # Now subscribe to the room
            # An error occurs here, the line to subscribe and listen always hold the connection.
            # So the fist request to subscribe to the room fails

            subscribe_n_listen_task = asyncio.create_task(self._subscribe_and_listen_to_channel(room_id=room_id))
            wait_for_subscribe_task = asyncio.create_task(asyncio.sleep(1))  # 1 Second delay

            # This coroutine would be exited when the time elaps, that should be anough time for the
            # Subscription task to be done
            await asyncio.wait([subscribe_n_listen_task, wait_for_subscribe_task], return_when=asyncio.FIRST_COMPLETED)
        else:
            self.connections[room_id].add(user_id)

        return True, "Connection Successful"

    async def _check_if_ws_connection_is_still_active(self, ws_connection: WebSocket, message=".") -> bool:
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

    async def _consume_events(self, message: MessageToRoomModel):
        """
        Function to consume a message and send to all connect clients
        """

        room_connections = self.connections.get(message.room_id, {})
        if len(room_connections) == 0:
            # No user has connected to this room.
            # The user has to connect to this room first, before sending message to the room
            return

        users_ws_connections = itemgetter(*room_connections)(self.user_connections)

        if type(users_ws_connections) is not tuple:
            # It wouldn't be a tuple if only a user is connected to the room
            users_ws_connections = [users_ws_connections]

        for connection in users_ws_connections:
            is_sent, sent_message_response_info = await self._send_message_to_ws_connection(
                message=f"Room {message.room_id} --> {message.message}", ws_connection=connection)

    async def _subscribe_and_listen_to_channel(self, room_id: str):
        """
        This function subscribes to a channel and listens to event in the channel
        """

        async with self.broadcaster.subscribe(channel=room_id) as subscriber:
            """
            Listen to every event from here
            """

            async for event in subscriber:
                print(event.message)
                message = MessageToRoomModel.model_validate_json(event.message)

                await self._consume_events(message=message)

    async def send_message_to_room(self, message: MessageToRoomModel):
        """
        Messages in this Program are Texts.
        the room id is the channel of the room
        # You just publish to the room
        """

        room_connections = self.connections.get(message.room_id, {})

        if len(room_connections) == 0:
            # No user has connected to this room.
            # The user has to connect to this room first, before sending message to the room
            return

        # Send events to the room
        await self.broadcaster.publish(channel=message.room_id, message=message.model_dump_json())

    async def _send_message_to_ws_connection(self, message: str, ws_connection: WebSocket) -> (bool, str):
        try:
            await ws_connection.send_text(message)
            return True, "Message sent!"
        except RuntimeError:
            return False, "Message Not Sent, Websocket is disconnected"

        except Exception as e:
            traceback.print_exc()

            return False, "Error Sending Message"

    def remove_user_connection(self, user_id):

        try:
            self.user_connections.pop(user_id)
        except KeyError:
            pass
