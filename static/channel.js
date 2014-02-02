/*
  Channel
  required args:
  pollPath - url of the channel to long poll on
  newMessagePath - url of the channel on which the server receives messages
  optional args:
  dictionary{
  onopen - event called when connection is opened to the server
  onmessage - event is called when message is received from the server
  onerror - event is called when an error occurs while long polling

  Depends on jQuery
  }
*/

function Channel(pollPath, newMessagePath, optionalArgsObject) {
    var self = this;
    self.pollPath = pollPath;
    self.newMessagePath = newMessagePath;
    self.onopen = function() {};
    self.onmessage = function(message) {};
    self.onerror = function() {};
    self.onbroadcastresponse = function(resp) {};
    
    if(optionalArgsObject.onopen != undefined)
        self.onopen = optionalArgsObject.onopen;
    if(optionalArgsObject.onmessage != undefined)
        self.onmessage = optionalArgsObject.onmessage;
    if(optionalArgsObject.onerror != undefined)
        self.onerror = optionalArgsObject.onerror;
    if(optionalArgsObject.onbroadcastresponse != undefined)
        self.onbroadcastresponse = optionalArgsObject.onbroadcastresponse;

    self.isOpen = false;
    self.cursor = null;
    var pollXHR = null;

    /*
      Opens a connection to the pollPath specified when the Channel object was 
      created
      return: true if connection was open false if it could not be opened or
      if the connection was already opened
    */
    self.open = function() {
        if(self.isOpen) return false;
        self.isOpen = true;
        self.onopen();
        longPoll();
    };

    /*
      Sends a message off to the newMessagePath.
      args:
      message - dictionary of key value pairs
    */
    self.broadcast = function(message) {
        $.post(newMessagePath, message, function(resp){
            self.onbroadcastresponse(resp);
        }, "json");
    };

    /*
      Stops the long polling of pollPath.
    */
    self.close = function() {
        self.isOpen = false;
        if(pollXHR != null) pollXHR.abort();
    };

    /*
      
     */
    function longPoll() {
        var postData = {};
        if(self.cursor != null) {
            postData["cursor"] = self.cursor;
        }
        pollXHR = $.ajax({
            type: "POST",
            url: pollPath,
            dataType: "json",
            data: postData,
            success: function(data) {
                self.onmessage(data);
                self.cursor = data.messages[data.messages.length-1].cursor;
                longPoll();
            },
            error: function(requestObj, textStatus, errorThrown) {
                //timeout just means we need to keep long polling
                if(textStatus == "timeout") {
                    longPoll();
                }
                else {
                    //http codes for timeout
                    if(requestObj.status == 504 || requestObj.status == 408) {
                        longPoll();
                    }
                    else {
                        //this even happens when user navigates away from
                        //the page
                        self.close();
                        self.onerror();
                    }
                }
            }
        });
    }
}
