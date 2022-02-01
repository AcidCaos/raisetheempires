function isFlashEnabled() {
    var flash = false;
    try {
        var fo = new ActiveXObject('ShockwaveFlash.ShockwaveFlash');
        if(fo) flash = true;
    } catch (e) {
        if (navigator.mimeTypes && navigator.mimeTypes['application/x-shockwave-flash'] != undefined &&
        navigator.mimeTypes['application/x-shockwave-flash'].enabledPlugin) {
            flash = true;
        }
    }
    return flash;
}

function loadingScreenUpdate() {
    if (! isFlashEnabled()) {
        document.getElementById("loading_gif").style.display = "none";
        document.getElementById("loading_message").innerHTML= '<b>Flash is not enabled.</b><br>Please, enable flash and <a href="javascript: document.location.reload()">refresh</a>.';
        //document.getElementById("flash_enabler").style.display = "block";
    }
    else {
        document.getElementById("loading_message").innerHTML = 'Loading game...';
        document.getElementById("inner_progress_bar").style.width = "10%";
    }
}