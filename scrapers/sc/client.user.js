// ==UserScript==
// @name         Soundcloud ripper
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @match        https://soundcloud.com/*
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
        let url = document.querySelector('a.playbackSoundBadge__titleLink').href.match(/\/\/*soundcloud.com\/(.*)(\?.*)?$/)[1];
        fetch(endpoint + `/1/${url}`).then();
        console.log('Good', url);
        setRank(document.querySelector('div.playbackSoundBadge'), 1);
    };

    let onThumbsDown = () => {
        let url = document.querySelector('a.playbackSoundBadge__titleLink').href.match(/\/\/*soundcloud.com\/(.*)(\?.*)?$/)[1];
        fetch(endpoint + `/-1/${url}`).then();
        console.log('Bad', url);
        setRank(document.querySelector('div.playbackSoundBadge'), -1);
    };

    let buttons = null;

    let makeButtons = () => {
        let ret = [];
        // Good
        let el = document.createElement('button');
        el.innerHTML = '👍';
        el.classList.add('playControls__control');
        el.addEventListener('click', onThumbsUp);
        ret.push(el);
        // Bad
        el = document.createElement('button');
        el.innerHTML = '👎';
        el.classList.add('playControls__control');
        el.addEventListener('click', onThumbsDown);
        ret.push(el);
        return ret;
    };

    let resetRankOnNewTrack = () => {
        let mo = new MutationObserver((mutations) => {
            let url = document.querySelector('a.playbackSoundBadge__titleLink').href.match(/\/\/*soundcloud.com\/(.*)(\?.*)?$/)[1];
            fetch(endpoint + `/q/${url}`).then(r => r.json()).then(r => {
                let foo = r.rank;
                if ((typeof foo === "number") && Math.floor(foo) === foo) {
                    setRank(document.querySelector('div.playbackSoundBadge'), foo);
                }
            });
        });

        mo.observe(document.querySelector('div.playbackSoundBadge'), { childList: true, subtree: true });
        console.log("MO started");
    };

    let addButtons = () => {
        let playbackBar = document.querySelector("div.playControls__elements");
        if (buttons === null) {
            buttons = makeButtons();
        };
        if (!playbackBar.classList.contains("_setup_done")) {
            let firstChild = playbackBar.children[0];
            for (let el in buttons) {
                playbackBar.insertBefore(buttons[el], firstChild);
            }

            resetRankOnNewTrack();

            playbackBar.classList.add("_setup_done");
        }
    };

    let setSongLineSetup = (line) => {

        if (line.querySelector('a.trackItem__trackTitle') === null) {
            setTimeout(() => { setSongLineSetup(line) }, 100);
            return;
        }

        let url = line.querySelector('a.trackItem__trackTitle').href.match(/\/\/.*?soundcloud.com\/(.*)(\?.*)?$/)[1];

        let el = document.createElement('button');
        el.innerHTML = '👍';
        el.style.position = 'absolute';
        el.style['z-index'] = '1';
        el.style['margin-left'] = '-30px';
        el.addEventListener('click', (ev) => {
            fetch(endpoint + `/1/${url}`).then();
            setRank(line, 1);
        });
        if (line.children !== undefined) {
            line.parentElement.insertBefore(el, line);
        }

        el = document.createElement('button');
        el.innerHTML = '👎';
        el.style.position = 'absolute';
        el.style['z-index'] = '1';
        el.style['margin-left'] = '-60px';
        el.addEventListener('click', (ev) => {
            fetch(endpoint + `/-1/${url}`).then();
            setRank(line, -1);
        });
        if (line.children !== undefined) {
            line.parentElement.insertBefore(el, line);
        }
        fetch(endpoint + `/q/${url}`).then(r => r.json()).then(r => {

            let foo = r.rank;
            if ((typeof foo === "number") && Math.floor(foo) === foo) {
                setRank(line, foo);
            }
        });
    };

    let addGlobalThumbs = (title) => {


        let url = window.location.href.match(/\/\/.*?soundcloud.com\/(.*)(\?.*)?$/)[1];


        let el = document.createElement('button');
        el.innerHTML = '👍';
        el.addEventListener('click', (ev) => {
            console.log("Good", window.location.href);
            fetch(endpoint + `/1/${url}`).then();
            setRank(title, 1, "#060");
        });

        title.parentElement.appendChild(el);

        el = document.createElement('button');
        el.innerHTML = '👎';
        el.addEventListener('click', (ev) => {
            console.log("Bad", window.location.href);
            fetch(endpoint + `/-1/${url}`).then();
            setRank(title, -1, "#600");
        });

        title.parentElement.appendChild(el);


        fetch(endpoint + `/q/${url}`).then(r => r.json()).then(r => {

            let foo = r.rank;
            if ((typeof foo === "number") && Math.floor(foo) === foo) {
                setRank(title, foo, "#060", "#600");
            }
        });
    };

    let userSetup = () => {
        let title = document.querySelector('h2');
        if (!title.classList.contains('_user_setup_done')) {
            addGlobalThumbs(title);
            title.classList.add('_user_setup_done');
        };
    }

    let songSetup = () => {
        let title = document.querySelector('h1');
        if (!title.classList.contains('_song_setup_done')) {
            addGlobalThumbs(title);
            title.classList.add('_song_setup_done');
        };
    }

    let setSongSetup = () => {
        let url = window.location.href.match(/\/\/.*?soundcloud.com\/(.*)(\?.*)?$/)[1];


        let title = document.querySelector('div.inPlaylist__body');
        if (!title.classList.contains('_set_song_setup_done')) {

            let container = document.querySelector('div.fullHero__parentLink');

            let el = document.createElement('button');
            el.innerHTML = '👍';
            el.style.position = 'absolute';
            el.addEventListener('click', (ev) => {
                console.log("Good", window.location.href);
                fetch(endpoint + `/1/${url}`).then();
                setRank(title, 1, "#060");
            });

            container.appendChild(el);

            el = document.createElement('button');
            el.innerHTML = '👎';
            el.style.position = 'absolute';
            el.style['margin-left'] = '30px';
            el.addEventListener('click', (ev) => {
                console.log("Bad", window.location.href);
                fetch(endpoint + `/-1/${url}`).then();

                setRank(title, -1, "#600");
            });

            container.appendChild(el);


            fetch(endpoint + `/q/${url}`).then(r => r.json()).then(r => {

                let foo = r.rank;
                if ((typeof foo === "number") && Math.floor(foo) === foo) {
                    setRank(title, foo, "#060", "#600");
                }
            });

            title.classList.add('_set_song_setup_done');
        };
    }

    let setSetup = () => {

        let songList = document.querySelector("ul.trackList__list");
        if (!songList.classList.contains('_set_setup_done')) {


            let title = document.querySelector('h1');

            addGlobalThumbs(title);

            let songListTI = songList.querySelectorAll("div.trackItem");

            songListTI.forEach(el => setSongLineSetup(el));

            let mo = new MutationObserver((mutations) => {
                mutations.forEach((mut) => {
                    mut.addedNodes.forEach((an) => {
                        if (an.tagName == "LI") {
                            setSongLineSetup(an.querySelector("div.trackItem"));
                            console.log(an);
                        }

                    });
                });
            });
            mo.observe(songList, { childList: true, subtree: true });
            console.log("Set MO started");
            songList.classList.add('_set_setup_done');
        }
    }

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
                setSetup();
            } else if (urlType === "user") {
                userSetup();
            } else if (urlType === "song") {
                songSetup();
            } else if (urlType === "set_song") {
                setSongSetup();
            }
            lastLoc = loc;
        }
    };

    let loop = () => {
        addButtons();
        watchNav();
    };

    let timer = setInterval(loop, 1000);

    // Your code here...
})();