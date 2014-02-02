"""
The design of this is based off of the tornadochat example which is distributed
as part of the tornado web framework which has the following license:

Tornado is an open source version of the scalable, non-blocking web server
and and tools that power FriendFeed. Documentation and downloads are
available at http://www.tornadoweb.org/

Tornado is licensed under the Apache Licence, Version 2.0
(http://www.apache.org/licenses/LICENSE-2.0.html).
"""

"""
Implementation Copyright (c) 2010 Evan Long
"""

import tornado.web

class BaseChannel(tornado.web.RequestHandler):
    """
    BaseChannel class logic
    """

    """
    _channel_data_store is a dict
    key: name of the channel
    value:     {'subscribers': [],
                'messages': [],
                'max_messages': int}

    messages must be a dictionary and the key "cursor" is reserved.
    An exception is raised if a message is broadcast which already contains this
    key.
    """
    _channel_data_store = {}

    def _required_attr_check(self):
        if not hasattr(self, "CHANNEL_NAME"):
            raise "Class must define an attribute: CHANNEL_NAME"

    def __init__(self, *args, **kwargs):
        tornado.web.RequestHandler.__init__(self, *args, **kwargs)
        if hasattr(self, "CHANNEL_NAME"):
            BaseChannel.create_named_channel(self.CHANNEL_NAME,
                                             getattr(self, "MAX_MESSAGES", 200))

    def broadcast(self, message, channel_name=None):
        if channel_name is None:
            self._required_attr_check()
            channel_name = self.CHANNEL_NAME

        chan_data = BaseChannel._channel_data_store[channel_name]

        for sub in chan_data["subscribers"]:
            sub([message])

        chan_data["subscribers"] = []

        chan_data["messages"].append(message)
        if len(chan_data["messages"]) > chan_data["max_messages"]:
            chan_data["messages"] = chan_data["messages"][
                -chan_data["max_messages"]:]

        return message

    def subscribe(self, cursor=None, callback=None, channel_name=None):
        """
        The purpose of the cursor is for the race condition which results
        if new messages arrive while subscriber is receiving messages and
        requests a new subscription. The subscriber sends back the cursor of the
        last message it received.

        callback must be wrapped in a tornado async_callback
        """
        if callback is None:
            callback = self.async_callback(self._subscribe_callback)

        if channel_name is None:
            self._required_attr_check()
            channel_name = self.CHANNEL_NAME

        chan_data = BaseChannel._channel_data_store[channel_name]
        #cursor None means it's the first time
        #empty list means we have no data to send the user
        #cursor at the end of the list means they have the most recent message
        #all these cases just need to be added as a subscriber
        if cursor is None or \
                len(chan_data["messages"]) == 0 or \
                chan_data["messages"][-1]["cursor"] == cursor:
            chan_data["subscribers"].append(callback)
            return

        len_messages = len(chan_data["messages"])
        index = -1
        for i in xrange(len_messages-1, -1, -1):
            if chan_data["messages"][i]["cursor"] == cursor:
                index = i
                break
            
        #cursor not in the list means send all messages back
        #cursor anywhere else means send them every message from that index to 
        #end
        callback(chan_data["messages"][index+1:])

    def _subscribe_callback(self, messages):
        if self.request.connection.stream.closed():
            return
        self.finish({"messages":messages})

    @classmethod
    def get_messages(cls, channel_name=None):
        if channel_name is None:
            channel_name = cls.CHANNEL_NAME
        chan_data = BaseChannel._channel_data_store.get(channel_name)
        if chan_data is not None:
            return chan_data["messages"]
        return []

    @classmethod
    def create_named_channel(cls, name, max_messages=200):
        if not BaseChannel._channel_data_store.has_key(name):
            BaseChannel._channel_data_store[name] = {
                "subscribers": [],
                "messages": [],
                "max_messages": max_messages
              }

    @classmethod
    def delete_named_channel(cls, name):
        if BaseChannel._channel_data_store.has_key(name):
            del(BaseChannel._channel_data_store[name])

    @classmethod
    def has_named_channel(cls, name):
        return BaseChannel._channel_data_store.has_key(name)
