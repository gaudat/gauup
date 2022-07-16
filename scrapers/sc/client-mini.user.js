// ==UserScript==
// @name         Soundcloud mini ripper
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @match        https://m.soundcloud.com/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=soundcloud.com
// @grant        GM_registerMenuCommand
// ==/UserScript==

(function () {
    'use strict';

    let endpoint = "http://localhost:22000";

    let setRank = (el, rank, color = null, badColor = null) => {
        if (color !== null && badColor === null) {
            el.style.backgroundColor = color;
            return;
        }
        if (rank > 0) {
            if (color !== null) {
                el.style.backgroundColor = color;
            } else {

                el.style.backgroundColor = "#dfd";
            }
        } else if (rank < 0) {
            if (badColor !== null) {
                el.style.backgroundColor = badColor;
            } else {

                el.style.backgroundColor = "#fdd";
            }
        } else {
            el.style.backgroundColor = "";
        }
    }

    let getRank = (el) => {
        switch (el.style.backgroundColor) {
            case "#dfd":
                return 1;
            case "#fdd":
                return -1;
            default:
                return 0;
        }
    }

    let lastState = null;
    let focusChecker = {
        check: () => {
            let hasFocus = document.hasFocus();
            if (hasFocus != lastState) {
                console.log(new Date(), `Focus: ${hasFocus}`);
                lastState = hasFocus;
            }
        }
    };

    let onThumbsUp = () => {
        let url = window.location.href.match(/\/\/.*?.soundcloud.com\/(.*)(\?.*)?$/)[1];
        fetch(endpoint + `/1/${url}`).then();
        console.log('Good', url);
        let innerBar = document.querySelector(`div[class^="MiniPlayer_MiniPlayerLink__"]`);
        setRank(innerBar, 1);

    };

    let onThumbsDown = () => {
        let url = window.location.href.match(/\/\/.*?.soundcloud.com\/(.*)(\?.*)?$/)[1];
        fetch(endpoint + `/-1/${url}`).then();
        console.log('Bad', url);

        let innerBar = document.querySelector(`div[class^="MiniPlayer_MiniPlayerLink__"]`);
        setRank(innerBar, -1);

    };

    let buttons = null;

    let makeButtons = () => {
        let ret = [];
        // Good
        let el = document.createElement('button');
        el.innerHTML = '👍';
        el.classList.add('playControls__control');
        el.style.position = 'absolute';
        el.style.width = '60px';
        el.style.height = '60px';
        el.style.right = '0px';
        el.style.overflow = 'visible';
        el.addEventListener('click', onThumbsUp);
        ret.push(el);
        // Bad
        el = document.createElement('button');
        el.innerHTML = '👎';
        el.classList.add('playControls__control');
        el.style.position = 'absolute';
        el.style.width = '60px';
        el.style.height = '60px';
        el.style.right = '60px';
        el.style.overflow = 'visible';
        el.addEventListener('click', onThumbsDown);
        ret.push(el);
        return ret;
    };

    let resetRankOnNewTrack = (playbackBar) => {
        let innerBar = playbackBar.querySelector(`div[class^="MiniPlayer_MiniPlayerLink__"]`);

        let mo = new MutationObserver((mutations) => {
            console.log(innerBar);
            let url = window.location.href.match(/\/\/.*?.soundcloud.com\/(.*)(\?.*)?$/)[1];
            fetch(endpoint + `/q/${url}`).then(r => r.json()).then(r => {
                let foo = r.rank;
                if ((typeof foo === "number") && Math.floor(foo) === foo) {
                    setRank(innerBar, foo);
                }
            });
        });

        console.log(innerBar);
        mo.observe(innerBar, { characterData: true, subtree: true });
        console.log("MO started");
    };

    let addButtons = () => {
        let playbackBar = document.querySelector(`div[aria-label="SoundCloud Mini Player"]`);
        if (playbackBar === null) {
            return;
        }
        if (buttons === null) {
            buttons = makeButtons();
        };
        if (!playbackBar.classList.contains("_setup_done")) {
            let firstChild = playbackBar.children[0];
            for (let el in buttons) {
                playbackBar.appendChild(buttons[el]);
            }

            resetRankOnNewTrack(playbackBar);

            playbackBar.classList.add("_setup_done");
        }
    };

    let lastLoc = null;

    let classifyUrl = (url) => {
        if (url.match(/^.*?soundcloud\.com\/([^\/])+(\/(popular-tracks|tracks|albums|sets|reposts))?$/)) {
            console.log("New location is user");
            return "user";
        }
        else if (url.match(/^.*?soundcloud\.com\/([^\/])+\/sets\/[^\/]+$/)) {
            console.log("New location is set");
            return "set";
        }
        else if (url.match(/^.*?soundcloud\.com\/([^\/])+\/([^\/]+)\?in=/)) {
            console.log("New location is set song");
            return "set_song";
        }
        else if (url.match(/^.*?soundcloud\.com\/([^\/])+\/([^\/]+)$/)) {
            console.log("New location is song");
            return "song";
        }
        else {
            console.log("Unknown new location");
            return "unk";
        }
    }

    let watchNav = () => {
        let loc = window.location.href;
        if (loc != lastLoc) {
            console.log("New location: ", loc);
            let urlType = classifyUrl(loc);
            if (urlType === "set") {
                //setSetup();
            } else if (urlType === "user") {
                //userSetup();
            } else if (urlType === "song") {
                //songSetup();
            } else if (urlType === "set_song") {
                //setSongSetup();
            }
            lastLoc = loc;
        }
    };

    let loop = () => {
        addButtons();
        watchNav();
    };

    let timer = setInterval(loop, 1000);

    //let timer = setInterval(focusChecker.check, 500);

    // Your code here...
})();