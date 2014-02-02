var GLOBALS = {
    "DROP_TIMEOUT": 500
};

var keymapping = {
    "w": 87,
    "a": 65,
    "s": 83,
    "d": 68,
    "up": 38,
    "left": 37,
    "down": 40,
    "right": 39,
    "enter": 13
};

function Block(game) {
    var self = this;
    var block_data = [
        [[0,0],[0,-1],[0,1],[0,2]], //I
        [[0,0],[-1,0],[1,0],[0,-1]], //T
        [[0,0],[1,0],[1,1],[0,1]], //box
        [[0,0],[1,0],[0,-1],[1,1]], //S
        [[0,0],[-1,1],[-1,0],[0,-1]], //Z
        [[0,0],[0,1],[0,-1],[1,-1]], //J
        [[0,0],[0,1],[0,-1],[-1,-1]] //L
    ];
    var game = game;
    self.x = parseInt(game.width/2);
    self.y = 1;
    
    self.prev_grid_coordinates = [];
    
    //IE just doesn't show the map love
    function map(lst, fun) {
        var new_lst = [];
        for(var i in lst) {
            new_lst.push(fun(lst[i]));
        }
        return new_lst;
    }

    function gen_block() {
        var idx = parseInt(Math.random()*block_data.length);
        if(idx == block_data.length) idx -= 1;

        return map(block_data[idx], function(d) {
            return [d[0],d[1]];
        });
    }
    var structure = gen_block();

    function do_legal_move(new_structure, new_x, new_y) {
        for(var i in new_structure) {
            var offset_x = new_structure[i][0]+new_x;
            var offset_y = new_structure[i][1]+new_y;
            
            if(offset_x < 0 || offset_y < 0 || 
               offset_x > game.width-1 || offset_y > game.height-1 ||
               game.grid[offset_x][offset_y]) {
                return;
            }
        }
        self.prev_grid_coordinates = self.grid_coordinates();
        structure = new_structure;
        self.x = new_x;
        self.y = new_y;
    }

    self.grid_coordinates = function() {
        return map(structure, function(d) {
            return [self.x+d[0], self.y+d[1]];
        });
    };

    self.left = function() {
        do_legal_move(structure, self.x-1, self.y);
    };

    self.right = function() {
        do_legal_move(structure, self.x+1, self.y);
    };

    self.down = function() {
        do_legal_move(structure, self.x, self.y+1);
    };

    self.rotate = function() {
        var tmp = map(structure, function(d) {
            return [-d[1],d[0]];
        });
        
        do_legal_move(tmp, self.x, self.y);
    };
}

function Game(board_id, size_width, size_height) {
    var self = this;
    self.board_id = board_id
    self.width = size_width;
    self.height = size_height;
    self.block_size = 10;
    $(board_id).css("height", self.height*self.block_size);
    $(board_id).css("width", self.width*self.block_size);

    var div_grid;
    self.grid = function() {
        var result = [];
        div_grid = [];
        for(var i=0; i<self.width; i++) {
            result.push([]);
            div_grid.push([]);
            for(var j=0; j<self.height; j++) {
                result[i].push(false);
                var div = $(document.createElement("div"))
                    .addClass("segment")
                    .css("visibility", "hidden")
                    .css("top", j * self.block_size)
                    .css("left", i * self.block_size)
                    .append(" ");
                $(board_id).append(div);
                div_grid[i].push(div);
            }
        }
        return result;
    }();

    var dropTimerId = null;
    self.lines_cleared = 0;

    self.current_block = null;

    function start_block() {
        var tmp_block = new Block(self);
        var coor = tmp_block.grid_coordinates();
        for(var i in coor) {
            var point_x = coor[i][0];
            var point_y = coor[i][1];
            if(self.grid[point_x][point_y]) {
                //collision so clear out all the lines
                //reset the count
                self.lines_cleared = 0;
                self.clear_board();
                self.line_cleared_event();
            }
        }
        return tmp_block;
    }

    function clear_lines() {
        for(var y=0; y<self.height; y++) {
            var count = 0;
            for(var x=0; x<self.width; x++) {
                if(self.grid[x][y]) {
                    count++;
                }
            }
            
            if(count == self.width) {
                for(var x=0; x<self.width; x++) {
                    self.grid[x].splice(y,1);
                    self.grid[x].splice(0,0,false);
                }
                self.lines_cleared += 1;
                self.line_cleared_event();
            }
        }
    }

    //render should only be called from "action" methods
    function render() {
        $(".segment").css("visibility", "hidden");
        for(var x in self.grid) {
            for(var y in self.grid[x]) {
                if(self.grid[x][y]) {
                    div_grid[x][y].css("background", "rgb(0,255,0)")
                        .css("visibility", "visible");
                }
            }
        }

        if(self.current_block != null)
        {
            var coor = self.current_block.grid_coordinates();
            for(var i in coor) {
                div_grid[coor[i][0]][coor[i][1]]
                    .css("background", "rgb(255,0,0)")
                    .css("visibility", "visible");
            }
        }
    }

    function start_drop_timer() {
        dropTimerId = setInterval(function() {
            self.moveDown();
        }, GLOBALS.DROP_TIMEOUT);
    }

    self.line_cleared_event = function() { };

    //actions
    self.start = function() {
        self.current_block = start_block();
        render();
        start_drop_timer();
    };

    self.stop = function() {
        clearInterval(dropTimerId);
        self.current_block = null;
        render();
    };

    self.clear_board = function() {
        for(var x in self.grid) {
            for(var y in self.grid[x]) {
                self.grid[x][y] = false;
            }
        }
        render();
    };

    self.moveLeft = function() {
        if(self.current_block != null) self.current_block.left();
        render();
    };

    self.moveRight = function() {
        if(self.current_block != null) self.current_block.right();
        render();
    };

    self.moveDown = function() {
        if(self.current_block != null) {
            //check to see if we are at the bottom
            var coor = self.current_block.grid_coordinates();
            for(var i in coor) {
                var point_x = coor[i][0];
                var point_y = coor[i][1];
                
                if(point_y == self.height-1 || 
                   self.grid[point_x][point_y+1]) {
                    
                    for(var j in coor) {
                        self.grid[coor[j][0]][coor[j][1]] = true;
                    }
                    self.current_block = null;
                    
                    clear_lines();
                    
                    self.current_block = start_block();
                    
                    render();
                    return;
                }
            }
            
            self.current_block.down();
            render();
        }
    };

    self.rotate = function() {
        if(self.current_block != null) self.current_block.rotate();
        render();
    };
}

var game = new Game("#board", 14, 28);

function end_game() {
    game.stop();
    game.clear_board();
    $.post("/winner",{},function(data){},"json");
}

game.line_cleared_event = function() {
    $("#lines_cleared").text(game.lines_cleared);
    if(game.lines_cleared == 5) {
        end_game();
    }
};

$(window).keydown(function(event) {
    if(event.keyCode == keymapping["up"]) {
        game.rotate();
    }
    else if(event.keyCode == keymapping["down"]) {
        game.moveDown();
    }
    else if(event.keyCode == keymapping["left"]) {
        game.moveLeft();
    }
    else if(event.keyCode == keymapping["right"]) {
        game.moveRight();
    }
});

$("#submit_phone").click(function() {
    $.post("/savenumber", {"phone":$("#phone").val()}, function(data) {
        if(data.result != "success") {
            $("#phone").val("");
            $("#submit_error").css("display", "inline");
            return;
        }
        $("#submit_error").css("display", "none");
    }, "json");
});
$("#phone").keydown(function(event){
    if(event.keyCode == keymapping["enter"]) {
        $("#submit_phone").trigger("click");
    }
});

var chan = new Channel(
    "/private/updates",
    "",
    {
        onmessage: function(data) {
            for(var idx in data.messages) {
                var msg = data.messages[idx];
                var msg_type = msg.type;
                if(msg_type == "data") {
                    var input = parseInt(msg.data);
                    if(input != NaN) {
                        if(input == "2") { //up
                            game.rotate();
                        }
                        else if(input == "5") { //down
                            game.moveDown();
                        }
                        else if(input == "4") { //left
                            game.moveLeft();
                        }
                        else if(input == "6") { //right
                            game.moveRight();
                        }
                    }
                }
                else if(msg_type == "game") {
                    if(msg.data == "start") {
                        game.start();
                    }
                    else if(msg.data == "winner") {
                        game.stop();
                        window.location = "/thanks";
                    }
                    else if(msg.data == "hangup") {
                        game.stop();
                        window.location = "/quit";
                    }
                }
                else if(msg_type == "error") {
                    if (msg.data == "invalid_user_token") {
                        //safe to ignore because the server should be
                        //resetting our user token at this point
                    }
                }
            }
        },
        onerror: function() {
            game.stop();
        }
    });
chan.open();