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

isFlashEnabled();