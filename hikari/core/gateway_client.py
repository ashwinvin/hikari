#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright © Nekoka.tt 2019-2020
#
# This file is part of Hikari.
#
# Hikari is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hikari is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Hikari. If not, see <https://www.gnu.org/licenses/>.
__all__ = ["GatewayClient"]

import asyncio
import inspect
import time
import typing

from hikari.core import dispatcher
from hikari.core import events
from hikari.core import gateway_config
from hikari.core import shard_client
from hikari.core import state
from hikari.core.dispatcher import EventCallbackT
from hikari.core.dispatcher import EventT
from hikari.internal_utilities import loggers
from hikari.net import shard


ShardT = typing.TypeVar("ShardT", bound=shard_client.ShardClient)


class GatewayClient(typing.Generic[ShardT], shard_client.WebsocketClientBase, dispatcher.EventDispatcher):
    def __init__(
        self,
        config: gateway_config.GatewayConfig,
        url: str,
        *,
        dispatcher_impl: typing.Optional[dispatcher.EventDispatcher] = None,
        shard_type: typing.Type[ShardT] = shard_client.ShardClient,
    ) -> None:
        self.logger = loggers.get_named_logger(self)
        self.config = config
        self.event_dispatcher = dispatcher_impl if dispatcher_impl is not None else dispatcher.EventDispatcherImpl()
        self._websocket_event_types = self._websocket_events()
        self.state = state.StatefulStateManagerImpl()
        self._is_running = False
        self.shards: typing.Dict[int, ShardT] = {
            shard_id: shard_type(shard_id, config, self._handle_websocket_event_later, url)
            for shard_id in config.shard_config.shard_ids
        }

    async def start(self) -> None:
        """Start all shards.

        This safely starts all shards at the correct rate to prevent invalid
        session spam. This involves starting each shard sequentially with a
        5 second pause between each.
        """
        self._is_running = True
        self.logger.info("starting %s shard(s)", len(self.shards))
        start_time = time.perf_counter()
        for i, shard_id in enumerate(self.config.shard_config.shard_ids):
            if i > 0:
                await asyncio.sleep(5)

            shard_obj = self.shards[shard_id]
            await shard_obj.start()
        finish_time = time.perf_counter()

        self.logger.info("started %s shard(s) in approx %.2fs", len(self.shards), finish_time - start_time)

    async def join(self) -> None:
        await asyncio.gather(*(shard_obj.join() for shard_obj in self.shards.values()))

    async def close(self, wait: bool = True) -> None:
        if self._is_running:
            self.logger.info("stopping %s shard(s)", len(self.shards))
            start_time = time.perf_counter()
            try:
                await asyncio.gather(*(shard_obj.close(wait) for shard_obj in self.shards.values()))
            finally:
                finish_time = time.perf_counter()
                self.logger.info("stopped %s shard(s) in approx %.2fs", len(self.shards), finish_time - start_time)
                self._is_running = False

    async def wait_for(
        self,
        event_type: typing.Type[dispatcher.EventT],
        *,
        predicate: dispatcher.PredicateT,
        timeout: typing.Optional[float],
    ) -> dispatcher.EventT:
        """Wait for the given event type to occur.

        Parameters
        ----------
        event_type : :obj:`typing.Type` [ :obj:`events.HikariEvent` ]
            The name of the event to wait for.
        timeout : :obj:`float`, optional
            The timeout to wait for before cancelling and raising an
            :obj:`asyncio.TimeoutError` instead. If this is `None`, this will
            wait forever. Care must be taken if you use `None` as this may
            leak memory if you do this from an event listener that gets
            repeatedly called. If you want to do this, you should consider
            using an event listener instead of this function.
        predicate : ``def predicate(event) -> bool`` or ``async def predicate(event) -> bool``
            A function that takes the arguments for the event and returns True
            if it is a match, or False if it should be ignored.
            This can be a coroutine function that returns a boolean, or a
            regular function.

        Returns
        -------
        :obj:`asyncio.Future`:
            A future to await. When the given event is matched, this will be
            completed with the corresponding event body.

            If the predicate throws an exception, or the timeout is reached,
            then this will be set as an exception on the returned future.
        """
        return await self.event_dispatcher.wait_for(event_type, predicate=predicate, timeout=timeout)

    def _handle_websocket_event_later(self, conn: shard.ShardConnection, event_name: str, payload: typing.Any) -> None:
        # Run this asynchronously so that we can allow awaiting stuff like state management.
        asyncio.get_event_loop().create_task(self._handle_websocket_event(conn, event_name, payload))

    async def _handle_websocket_event(self, _: shard.ShardConnection, event_name: str, payload: typing.Any) -> None:
        try:
            event_type = self._websocket_event_types[event_name]
        except KeyError:
            pass
        else:
            event_payload = event_type.deserialize(payload)
            await self.state.on_event(event_payload)
            await self.event_dispatcher.dispatch_event(event_payload)

    def _websocket_events(self):
        # Look for anything that has the ___raw_ws_event_name___ class attribute
        # to each corresponding class where appropriate to do so. This provides
        # a quick and dirty event lookup mechanism that can be extended quickly
        # and has O(k) lookup time.

        types = {}

        def predicate(member):
            return inspect.isclass(member) and hasattr(member, "___raw_ws_event_name___")

        for name, cls in inspect.getmembers(events, predicate):
            raw_name = cls.___raw_ws_event_name___
            types[raw_name] = cls
            self.logger.debug("detected %s as a web socket event to listen for", name)

        self.logger.debug("detected %s web socket events to register from %s", len(types), events.__name__)

        return types

    def add_listener(self, event_type: typing.Type[EventT], callback: EventCallbackT) -> EventCallbackT:
        return self.event_dispatcher.add_listener(event_type, callback)

    def remove_listener(self, event_type: typing.Type[EventT], callback: EventCallbackT) -> EventCallbackT:
        return self.event_dispatcher.remove_listener(event_type, callback)

    def dispatch_event(self, event: events.HikariEvent) -> ...:
        return self.event_dispatcher.dispatch_event(event)