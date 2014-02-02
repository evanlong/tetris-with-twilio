#!/usr/bin/env python

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.escape
import uuid
import logging
import twilio
from twiliodec import dec_twilio_request
from tornado.options import define, options
import os.path
from httpchannel import BaseChannel
from settings import *
import model
from model import get_valid_phone_number

account = twilio.Account(AccountGuid, AuthToken)

class PrivateChannelSettings(BaseChannel): pass

class PrivateChannelPollHandler(PrivateChannelSettings):
    @tornado.web.asynchronous
    def post(self):
        error_message = {"messages":[{"cursor":str(uuid.uuid4()),
                                      "type":"error",
                                      "data":"invalid_user_token"}]}
        chan_id = self.get_cookie("private_chan_id")
        if chan_id is not None and \
                model.get_user_by_channel_id(chan_id) is not None:
            cursor = self.get_argument("cursor", None)
            user = model.get_user_by_channel_id(chan_id)            
            if cursor is None and \
                    user.get_state() == model.States.GAME_IN_PROGRESS:
                #This occurs when the user has hit F5. Which resets the game
                #but since they are still in the call it should just clear the
                #board (F5) and then start the game again
                msg = model.generate_message("game","start")
                #cursor will be None so subscribe won't send anything back
                #then a broadcast can tell the game to start
                self.subscribe(cursor, channel_name=chan_id)
                self.broadcast(msg, channel_name=chan_id)
                return

            self.subscribe(cursor, channel_name=chan_id)
        else:
            #this seems to be a rare case when the dev server is restarted
            #all the user ids go way (in memory db :( ) but the client has not
            #refreshed but it's still trying to poll and will start to
            #repeatedly poll the server over and over. 
            user = model.create_user()
            self.set_cookie("private_chan_id", user.channel_id)
            self.write(error_message)
            self.finish()

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        chan_id = self.get_cookie("private_chan_id")
        user = model.get_user_by_channel_id(chan_id)
        if user is None:
            user = model.create_user()
            self.set_cookie("private_chan_id", user.channel_id)
        self.render("index.html",
                    phone="" if user.caller_id is None else user.caller_id)

class SaveNumberHandler(tornado.web.RequestHandler):
    @model.dec_require_valid_user_token
    def post(self):
        chan_id = self.get_cookie("private_chan_id")
        user = model.get_user_by_channel_id(chan_id)
        phone = get_valid_phone_number(self.get_argument("phone", ""))

        #state: only accept new number in specific state
        if user.get_state() not in [model.States.WAIT_FOR_PHONE_NUMBER,
                                    model.States.WAIT_FOR_CALL]:
            logging.warn("SaveNumber State User: %s Phone: %s" % (chan_id,
                                                                  phone))
            self.write({"result":"Only saves when call not in progress"})
            return
        
        #error case: invalid phone number
        if not phone:
            logging.warn("SaveNumber Wrong # User: %s Phone: %s" % (chan_id,
                                                                  phone))
            self.write({"result":"Invalid phone number"})
            return

        #TODO: In the multi process scenario this breaks down. A real DB will
        #need to enforce uniqueness of the phone number per user
        #otherwise multi proc will have issues. Ignoring this issue for now.
        #Sample Issue:
        #1. User A and User B both enter a number P for the first time
        #then both could end up getting into the DB with same phone number
        #because both get past the check for duplicates then both are added.

        #check for duplicate phone numbers and remove them.
        #this really should never be more than one that needs to be removed
        #as each save number should remove the previous dupes.
        #remove all users with this phone number that don't have the same
        #private_channel_id
        
        #The main reason behind this is if a person uses a different computer
        #but specifies the same phone number we still want it to work and
        #not get get stuck with the old user getting the messages
        for u in model.get_all_users_with_caller_id(phone):
            #without this check they could remove themselves if they saved twice
            if u.channel_id != chan_id:
                model.remove_user(u)
        user.caller_id = phone

        logging.info("SaveNumber Success User: %s Phone: %s" % (chan_id, phone))
        
        self.write({"result":"success"})

class GameWonHandler(PrivateChannelSettings):
    @model.dec_require_valid_user_token
    def post(self):
        chan_id = self.get_cookie("private_chan_id")
        user = model.get_user_by_channel_id(chan_id)

        if user.get_state() != model.States.GAME_IN_PROGRESS:
            self.write({"result":"Game is not in progress"})
            return
        
        redirectUrl = "%sCalls/%s" % (ApiUrlBase, user.call_id)
        try:
            args = {
                "CurrentUrl":GameRedirectUrl,
                "CurrentMethod":"POST"
                }
            user.gameon = False
            self.broadcast(model.generate_message("game", "winner"),
                           channel_name=user.channel_id)
            account.request(redirectUrl, "POST", args)
        except Exception, e:
            logging.error(self.request)
            logging.error("Call redirect request failed: %s" % (call_id))
            logging.error("Url %s" % redirectUrl)
            logging.error(type(e))
            logging.error(e)
            self.write({"result":"Call redirect request failed"})
            return
        
        self.write({"result":"success"})

class PrivateClearHandler(tornado.web.RequestHandler):
    def get(self):
        self.clear_cookie("private_chan_id")
        self.write("cookie cleared")
    
class TwilioHandler(PrivateChannelSettings):
    @dec_twilio_request
    @model.dec_require_phone_in_db
    def post(self):
        caller_id = get_valid_phone_number(self.get_argument("Caller", ''))
        user = model.get_user_by_caller_id(caller_id)

        call_status = self.get_argument("CallStatus", None)
        if call_status == "completed" and \
                user.get_state() == model.States.GAME_IN_PROGRESS:
            #VICTORY_CALL state will send it's completed call event to the
            #/redirect handler
            self.broadcast(model.generate_message("game", "hangup"),
                           channel_name=user.channel_id)
            user.call_id = None
            user.gameon = False
        elif user.get_state() == model.States.WAIT_FOR_CALL:
            user.call_id = self.get_argument("CallGuid")
            user.gameon = True
            self.broadcast(model.generate_message("game", "start"),
                           channel_name=user.channel_id)
            self.render("gather.xml")
        else:
            msg = "Unexpected user state %d" % user.get_state()
            logging.error(self.request)
            logging.error(msg)
            self.render("say.xml", say=msg)

    def get(self):
        self.post()

class GatherHandler(PrivateChannelSettings):
    @dec_twilio_request
    @model.dec_require_phone_in_db
    def post(self):
        caller_id = get_valid_phone_number(self.get_argument("Caller", ''))
        user = model.get_user_by_caller_id(caller_id)

        #error case: the channel no longer exists (should never happen)
        #logging this is a precautionary measure
        if not BaseChannel.has_named_channel(user.channel_id):
            logging.error(self.request)
            logging.error("Channel did not exist when gathering input")
            self.render("say.xml", say="Fatal Error processing input")
            return

        if self.get_argument("CallStatus") == "redirecting" and \
                user.get_state() == model.States.VICTORY_CALL:
            #expected message
            return

        #state: should be GAME_IN_PROGRESS
        if user.get_state() != model.States.GAME_IN_PROGRESS:
            logging.error(self.request)
            logging.error("User state should be GAME_IN_PROGRESS on gather")
            self.render("say.xml", say="Unexpected user state on gather")
            return

        #game is still going so send that data to the user
        #client is responsible for ignoring commands if the game is actually
        #done on their end
        digits = self.get_argument("Digits", '')
        self.broadcast(model.generate_message("data", digits),
                       channel_name=user.channel_id)
        self.render("gather.xml")

class RedirectCallHandler(PrivateChannelSettings):
    @dec_twilio_request
    @model.dec_require_phone_in_db
    def post(self):
        """
        Should only be hit when the game has been won on the client side.
        """
        caller_id = get_valid_phone_number(self.get_argument("Caller", ''))
        user = model.get_user_by_caller_id(caller_id)

        if user.get_state() != model.States.VICTORY_CALL:
            logging.error(self.request)
            logging.error("User state should be VICTORY_CALL on redirect")
            self.render("say.xml", say="Unexpected user state on redirect")
            return

        call_status = self.get_argument("CallStatus", None)
        if call_status == "completed":
            #send user back to the WAIT_FOR_CALL state
            user.call_id = None
            user.gameon = False
            return

        self.render("dialwinner.xml", 
                    name=CallOnWinnerName, 
                    phone=CallOnWinnerNumber)
    def get(self):
        self.post()

class ThanksHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("thanks.html", msg="You are a WINNER. Your phone should " \
                        "be calling me now.")

class QuitHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("thanks.html",
                    msg="Don't forget a winner will have their phone " \
                        "automatically call mine.")

class DebugHandler(tornado.web.RequestHandler):
    def get(self):
        chan_id = self.get_cookie("private_chan_id")
        self.write("<b>%s</b><br/>\n<br/>\n" % chan_id)
        for user in model._user_db:
            self.write("user.channel_id=%s<br/>\n" % user.channel_id)
            self.write("user.call_id=%s<br/>\n" % user.call_id)
            self.write("user.caller_id=%s<br/>\n" % user.caller_id)
            self.write("user.gameon=%s<br/>\n" % user.gameon)


define("port", default=9988, help="run on the given port", type=int)

if __name__ == "__main__":
    settings = {
        "template_path": os.path.join(os.path.dirname(__file__), "templates"),
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
        "debug": True
        }
    application = tornado.web.Application(handlers=[
            (r"/", MainHandler),
            (r"/savenumber", SaveNumberHandler),
            (r"/private/updates", PrivateChannelPollHandler),
            (r"/private/clear", PrivateClearHandler),
            (r"/twilio", TwilioHandler),
            (r"/gather", GatherHandler),
            (r"/winner", GameWonHandler),
            (r"/redirect", RedirectCallHandler),
            (r"/thanks", ThanksHandler),
            (r"/quit", QuitHandler),
            (r"/debug", DebugHandler),
            ], **settings)
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
