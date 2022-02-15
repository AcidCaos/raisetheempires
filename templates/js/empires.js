zynga = {
	"ads": {
		"WatchToEarn": {
			"service": {
				"available": function () {
					console.log("W2E avail");
					return false;
				},
				"initializeFlash": function (oid, a, b, c) {
					console.log("initF " + oid + ", " + a + ", " + b + ", " + c);
					return false;
				}
			}
		}
	}
}

statTracker = {
	"logWorldObjectCount": function () {
		console.log("World Count");
		return;
	}
}

ZYFrameManager = {
	"reloadApp": function () {
		console.log("Reload App");
		window.location.reload();
		return;
	},
	"navigateTo": function (a, b, c) {
		console.log("Navigate To" + a + " - " + b + " - " + c);
		return;
	},
	"openTab": function (a, b, c) {
		console.log("Open Tab" + a + " - " + b + " - " + c);
		return;
	},
	"switchToTab": function (a) {
		console.log("Switch To Tab" + a);
		return;
	}

}

function inner_getUserInfo() {
	document.getElementById("loading_message").innerHTML= "Loading User info...";
	document.getElementById("inner_progress_bar").style.width = "30%";
	document.getElementById("flash_enabler").style.display = "none";
}

function inner_getFriendData() {
	document.getElementById("inner_progress_bar").style.width = "50%";
	document.getElementById("loading_message").innerHTML= "Loading Friends data...";
}

function inner_getAppFriendIds() {
	document.getElementById("inner_progress_bar").style.width = "70%";
}

function inner_onGameLoaded(seen, popp, canvas) {
	document.getElementById("inner_progress_bar").style.width = "100%";
	// Hide Loading div
	document.getElementById("loading_game").style.display = "none";
}

function openInAppPurchaseAPI(gid, snid, snuid, cid, a, b, c) {
	console.log("Purchase " + gid + ", " + snid + ", " + snuid + ", " + cid + ", " + a + ", " + b + ", " + c)
	return;
}

function hasPermission(perm, snuid, name) {
	console.log("Perm " + perm + ", " + snuid + ", " + name)
	return;
}

function showPermissions(d) {
	console.log("Show Perm " + d)
	return;
}