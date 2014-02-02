"""
In python memory DB models and decorators for tornado requests to ensure
specific states of the program
"""

import logging
import uuid
from httpchannel import BaseChannel

#database
_user_db = []

#states
class States:
    UNKNOWN = -1
    NON_USER = 0
    WAIT_FOR_PHONE_NUMBER = 1
    WAIT_FOR_CALL = 2
    GAME_IN_PROGRESS = 3
    VICTORY_CALL = 4

#model
class User(object):
    def __init__(self, channel_id):
        self.channel_id = channel_id
        self.call_id = None
        self.caller_id = None
        self.gameon = False
        BaseChannel.create_named_channel(channel_id)

    def get_state(self):
        if self.channel_id is not None and \
                self.call_id is None and \
                self.caller_id is None and \
                self.gameon is False:
            return States.WAIT_FOR_PHONE_NUMBER
        elif self.channel_id is not None and \
                self.call_id is None and \
                self.caller_id is not None and \
                self.gameon is False:
            return States.WAIT_FOR_CALL
        elif self.channel_id is not None and \
                self.call_id is not None and \
                self.caller_id is not None and \
                self.gameon is True:
            return States.GAME_IN_PROGRESS
        elif self.channel_id is not None and \
                self.call_id is not None and \
                self.caller_id is not None and \
                self.gameon is False:
            return States.VICTORY_CALL
        elif self.channel_id is None and \
                self.call_id is None and \
                self.caller_id is None and \
                self.gameon is False:
            return States.NON_USER
        else:
            return States.UNKNOWN

def create_user():
    u = User(str(uuid.uuid4()))
    _user_db.append(u)
    return u

def get_user_by_channel_id(channel_id):
    for u in _user_db:
        if u.channel_id == channel_id:
            return u
    return None

def get_user_by_twilio_call_id(call_id):
    for u in _user_db:
        if u.call_id == call_id:
            return u
    return None

def get_user_by_caller_id(caller_id):
    for u in _user_db:
        if u.caller_id == caller_id:
            return u
    return None

def get_all_users_with_caller_id(caller_id):
    result = []
    for u in _user_db:
        if u.caller_id == caller_id:
            result.append(u)
    return result

def remove_user(u):
    if u in _user_db:
        _user_db.remove(u)

#model utility methods
def get_valid_phone_number(input):
    """
    Will strip out the non-digits and make sure it's 10 numbers long. None is
    returned for input that does not contain exactly 10 digits
    >>> get_valid_phone_number('123')
    None
    >>> get_valid_phone_number('1231231234')
    '1231231234'
    >>> get_valid_phone_number('12(31##2asd31asdf234')
    '1231231234'
    """
    input = ''.join([c for c in input if c.isdigit()])
    if len(input) == 10:
        return input
    else:
        return None
        
#decs
def dec_require_valid_user_token(fun):
    def new_fun(self, *args, **kwargs):
        channel_id = self.get_cookie("private_chan_id")
        if channel_id is None or get_user_by_channel_id(channel_id) is None:
            self.clear_cookie("private_chan_id")
            self.write({"result":"Require valid user token"})
            return
        return fun(self, *args, **kwargs)
    return new_fun

def dec_require_phone_in_db(fun):
    def new_fun(self, *args, **kwargs):
        caller_id = get_valid_phone_number(self.get_argument("Caller", ''))
        user = get_user_by_caller_id(caller_id)
        #state: WAIT_FOR_PHONE_NUMBER
        if user is None:
            logging.warn("Phone not in DB Caller ID: %s" % (caller_id))
            self.set_header("Content-Type", "text/xml")
            self.render("say.xml",
                        say="Please enter phone number at the homepage")
            return
        return fun(self, *args, **kwargs)
    return new_fun

#private channel messages
def generate_message(ty, data):
    message = {
        "cursor": str(uuid.uuid4()),
        "type": ty,
        "data": data,
        }
    return message
