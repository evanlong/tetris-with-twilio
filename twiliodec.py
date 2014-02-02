"""
twilio decorator and util functions for use with the tornado web framework
"""

import logging
import urllib
import twilio
from settings import *

_validator = twilio.Utils(AccountGuid, AuthToken)

def _valid_twilio_request(request):
    params = request.body
    elements = params.split("&")

    #not using request.arguments because we need to preserve the arguments
    #that have empty values as well for the validator
    args = {}
    for e in elements:
        tmp = e.split("=")
        #params need to have one key and one value
        #if request.body was empty this will catch it
        if len(tmp) != 2:
            return False
        args[tmp[0]] = urllib.unquote_plus(tmp[1])

    uri = request.protocol + "://" + request.host + request.uri
    return _validator.validateRequest(uri, 
                                      args,
                                      request.headers.get("X-Twilio-Signature"))

def dec_twilio_request(fun):
    """
    Ensures the request is from twilio and sets the output type to text/xml
    """
    def new_fun(self, *args, **kwargs):
        self.set_header("Content-Type", "text/xml")
        if _valid_twilio_request(self.request):
            return fun(self, *args, **kwargs)
        else:
            logging.info("Twilio request not from twilio")
            self.render("say.xml", say="Not a valid twilio request")
            return
    return new_fun

