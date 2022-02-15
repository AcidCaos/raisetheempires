/* debug websocket connection */

var socket = io();
socket.on('connect', function () {
    socket.emit('my event', {data: 'I\'m connected!'});

    $('#delete_save').click(function(event) {
        console.log('deleting save');
        // event.preventDefault();

        socket.emit('delete_save', "Deleting save game");

        console.log('deleting cookie');
        // $.cookie("session", null, { path: '/' });
        // $.removeCookie('the_cookie', { path: '/' });

    });

});
socket.on('tutorial_step', function (msg) {
    console.log(msg);
    // $('#tutorial_step').prepend('<div>' + JSON.stringify(msg) + '</div>');
    $('#tutorial_step').prepend('<div><span class="req'+msg[6] + ' ' + (parseInt(msg[6].substring(1)) % 2 == 0 ? 'req_even' : 'req_odd' ) + '">' + msg[5] + ': </span><span class="tooltiplink">' + msg[0] + '<span class="tooltip">' + JSON.stringify(msg[3], null, 4).replace(/\n/g, "<br>").replace(/[ ]/g, "&nbsp;") + '</span></span>'
        + (msg[1] || msg[2] ? ' &rarr; ' : '') + (msg[1] ? '<span class="tooltiplink response">' + JSON.stringify(msg[1]) + '<span class="tooltip">' + JSON.stringify(msg[4], null, 4).replace(/\n/g, "<br>").replace(/[ ]/g, "&nbsp;") + '</span></span>' : '') +
        (msg[1] && msg[2] ? ', ' : '') + (msg[2] ? JSON.stringify(msg[2]) : '') + '</div>');
    $('#tutorial_step').scrollTop(0)
});

socket.on('world_log', function (msg) {
    console.log(msg);
    $('#world_log').prepend('<div><span class="req'+msg[4] + ' ' + (parseInt(msg[4].substring(1)) % 2 == 0 ? 'req_even' : 'req_odd' ) + '">' + msg[3] + ': </span><span class="tooltiplink">' + msg[0] + '<span class="tooltip">' + JSON.stringify(msg[2], null, 4).replace(/\n/g, "<br>").replace(/[ ]/g, "&nbsp;") +
        '</span></span>' + (msg[1] || msg[1] == 0 ? ' &rarr; <span class="tooltiplink response">' + msg[1] + '<span class="tooltip">' + JSON.stringify(msg[8], null, 4).replace(/\n/g, "<br>").replace(/[ ]/g, "&nbsp;") + '</span></span>' + (msg[5] ? ', <span class="tooltiplink response">' + JSON.stringify(msg[5]) + '<span class="tooltip">'+ JSON.stringify(msg[7], null, 4).replace(/\n/g, "<br>").replace(/[ ]/g, "&nbsp;") + '</span></span>' : '') + (msg[6] ? ', ' + JSON.stringify(msg[6]) :'')  : '') + '</div>');
    $('#world_log').scrollTop(0)
});
    socket.on('other_log', function (msg) {
    console.log(msg);
    $('#other_log').prepend('<div><span class="req'+ msg[4] + ' ' + (parseInt(msg[4].substring(1)) % 2 == 0 ? 'req_even' : 'req_odd' ) + '">' + msg[3] + ': </span><span class="tooltiplink">' + msg[0] + '<span class="tooltip">' + JSON.stringify(msg[2], null, 4).replace(/\n/g, "<br>").replace(/[ ]/g, "&nbsp;") +
        '</span></span>' + (msg[1] ? ' &rarr; <span class="tooltiplink response">response<span class="tooltip">' + JSON.stringify(msg[1], null, 4).replace(/\n/g, "<br>").replace(/[ ]/g, "&nbsp;") + '</span></span>' : '')
        + '</div>');
    $('#other_log').scrollTop(0)
});

socket.on('battle_log', function (msg) {
    console.log(msg);
    $('#world_log').prepend('<div>' + msg + '</div>');
    $('#world_log').scrollTop(0)
});
