"use strict";

(() => {
    const INDEX_URL = "data/index.json?v=20261013";
    const FETCH_TIMEOUT = 15000;
    const MEDIA_TIMEOUT = 20000;
    const BACKUP_BASE = "https://cdn.jsdelivr.net/gh/wangqi0821/uni-calendar-china@f4d34b3543439f40cc093c0ffa57c65e8b23303d/";
    const input = document.getElementById("dateInput");
    const result = document.getElementById("result");
    const status = document.getElementById("status");
    const range = document.getElementById("archiveRange");
    const navigation = document.querySelector(".date-navigation");
    const previousButton = document.getElementById("previousDate");
    const nextButton = document.getElementById("nextDate");
    const monthCache = new Map();
    let archive;
    let dateSet;
    let selection = 0;
    let mediaCleanup = [];

    function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function button(text, action) {
        const node = element("button", "quiet-button", text);
        node.type = "button";
        node.addEventListener("click", action);
        return node;
    }

    function validDate(value) {
        if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000")) return false;
        const parsed = new Date(value + "T00:00:00Z");
        return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
    }

    function dateFromURL() {
        const values = new URL(window.location.href).searchParams.getAll("date");
        return values.length === 1 && validDate(values[0]) ? values[0] : null;
    }

    function updateURL(date, mode) {
        if (mode === "none") return;
        const url = new URL(window.location.href);
        if (url.searchParams.get("date") === date && url.searchParams.getAll("date").length === 1) return;
        url.searchParams.set("date", date);
        window.history[mode === "replace" ? "replaceState" : "pushState"]({}, "", url);
    }

    function localMediaPath(value) {
        return typeof value === "string" && /^(?:media|media\.plus)\/[A-Za-z0-9_-][A-Za-z0-9._-]*$/.test(value) ? value : null;
    }

    function sourceURL(value) {
        try {
            const url = new URL(value);
            return ["https:", "http:"].includes(url.protocol) ? url.href : null;
        } catch { return null; }
    }

    async function fetchJSON(url) {
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT);
        try {
            const response = await fetch(url, { signal: controller.signal });
            if (!response.ok) throw new Error("HTTP " + response.status);
            return await response.json();
        } finally {
            window.clearTimeout(timeout);
        }
    }

    function validateIndex(data) {
        if (!data || data.version !== 1 || !Array.isArray(data.dates) || !data.dates.length || !data.months) throw new Error("Invalid index");
        const dates = [...new Set(data.dates)];
        if (!dates.every(validDate)) throw new Error("Invalid dates");
        dates.sort();
        if (data.firstDate !== dates[0] || data.lastDate !== dates[dates.length - 1]) throw new Error("Invalid range");
        for (const date of dates) {
            const month = date.slice(0, 7);
            const path = data.months[month];
            if (typeof path !== "string" || !/^data\/\d{4}-\d{2}\.[A-Za-z0-9_-]+\.json$/.test(path) || !path.startsWith("data/" + month + ".")) throw new Error("Invalid month path");
        }
        return { ...data, dates };
    }

    function getMonth(month) {
        if (!monthCache.has(month)) {
            const pending = fetchJSON(archive.months[month]).then(data => {
                if (!data || typeof data.days !== "object" || data.days === null || Array.isArray(data.days)) throw new Error("Invalid month data");
                return data.days;
            }).catch(error => {
                monthCache.delete(month);
                throw error;
            });
            monthCache.set(month, pending);
        }
        return monthCache.get(month);
    }

    function clearResult() {
        mediaCleanup.forEach(cleanup => cleanup());
        mediaCleanup = [];
        result.replaceChildren();
    }

    function announce(message) { status.textContent = message; }

    function showError(message, retry) {
        clearResult();
        result.setAttribute("aria-busy", "false");
        const notice = element("div", "notice notice-error");
        notice.append(element("p", "notice-title", message), element("p", "", "请检查网络连接，再试一次。"), button("重新加载", retry));
        result.append(notice);
        announce(message);
    }

    function adjacentDates(date) {
        let lower = 0;
        let upper = archive.dates.length;
        while (lower < upper) {
            const middle = (lower + upper) >>> 1;
            if (archive.dates[middle] < date) lower = middle + 1;
            else upper = middle;
        }
        const found = archive.dates[lower] === date;
        return { previous: archive.dates[lower - 1], next: archive.dates[lower + (found ? 1 : 0)] };
    }

    function updateNavigation(date) {
        const adjacent = validDate(date) ? adjacentDates(date) : {};
        previousButton.disabled = !adjacent.previous;
        nextButton.disabled = !adjacent.next;
        previousButton.onclick = adjacent.previous ? () => selectDate(adjacent.previous) : null;
        nextButton.onclick = adjacent.next ? () => selectDate(adjacent.next) : null;
        previousButton.setAttribute("aria-label", adjacent.previous ? "上一个有记录日，" + adjacent.previous : "没有更早的记录");
        nextButton.setAttribute("aria-label", adjacent.next ? "下一个有记录日，" + adjacent.next : "没有更晚的记录");
    }

    function showEmptyDate(date) {
        const notice = element("div", "notice");
        const outside = date < archive.firstDate || date > archive.lastDate;
        notice.append(element("p", "notice-title", date + " 还没有记录"));
        notice.append(element("p", "", outside ? "这个日期在当前归档范围之外。日历不会自动更新新的内容。" : "已保留你选择的日期，可以翻到附近有记录的日子。"));
        const adjacent = adjacentDates(date);
        const actions = element("div", "notice-actions");
        if (adjacent.previous) actions.append(button("← " + adjacent.previous, () => selectDate(adjacent.previous)));
        if (adjacent.next) actions.append(button(adjacent.next + " →", () => selectDate(adjacent.next)));
        notice.append(actions);
        result.append(notice);
        announce(date + " 没有记录，日期已保留。");
    }

    function setDimensions(media, frame, node) {
        if (Number.isInteger(media.width) && media.width > 0 && Number.isInteger(media.height) && media.height > 0) {
            node.width = media.width;
            node.height = media.height;
            frame.style.aspectRatio = media.width + " / " + media.height;
        }
    }

    function renderMedia(media, date, index, firstImage) {
        const item = element("div", "media-item");
        const path = localMediaPath(media && media.src);
        if (!path || !["image", "video"].includes(media.type)) {
            item.append(element("p", "media-error", "这项媒体暂时无法显示。"));
            return item;
        }
        const isVideo = media.type === "video";
        const frame = element("div", "media-frame" + (isVideo ? " video-frame" : ""));
        const node = element(isVideo ? "video" : "img");
        const errors = element("div", "media-error");
        errors.hidden = true;
        errors.setAttribute("role", "status");
        let timer;
        let imageObserver;
        let disposed = false;
        let generation = 0;
        let currentSource = path;
        const clearTimer = () => window.clearTimeout(timer);
        setDimensions(media, frame, node);
        item.append(frame, errors);
        frame.append(node);

        function showMediaError() {
            if (disposed) return;
            clearTimer();
            if (isVideo) node.pause();
            const text = isVideo ? "视频暂时无法加载。" : "图片暂时无法加载。";
            const actions = element("div", "media-actions");
            actions.append(button("重试", () => start(currentSource, isVideo, true)));
            if (currentSource === path) actions.append(button("尝试备用来源", () => start(new URL(path, BACKUP_BASE).href, isVideo, true)));
            errors.replaceChildren(element("p", "", text), actions);
            errors.hidden = false;
        }

        function beginTimeout() {
            clearTimer();
            timer = window.setTimeout(showMediaError, MEDIA_TIMEOUT);
        }

        function loaded() {
            clearTimer();
            if (imageObserver) imageObserver.disconnect();
            errors.hidden = true;
        }

        function start(src, userPlay = false, manual = false) {
            if (disposed) return;
            generation += 1;
            const attempt = generation;
            currentSource = src;
            errors.hidden = true;
            if (isVideo) {
                startButton.hidden = true;
                node.controls = true;
                node.removeAttribute("aria-hidden");
                node.tabIndex = 0;
                node.src = src;
                node.load();
                beginTimeout();
                if (userPlay) {
                    node.focus({ preventScroll: true });
                    const playing = node.play();
                    if (playing) playing.catch(error => {
                        if (disposed || attempt !== generation || error.name === "AbortError") return;
                        if (error.name === "NotAllowedError") {
                            clearTimer();
                            errors.replaceChildren(element("p", "", "视频已准备好，请点击视频中的播放按钮。"));
                            errors.hidden = false;
                        } else showMediaError();
                    });
                }
            } else {
                node.src = src;
                if (firstImage || src !== path || manual) beginTimeout();
            }
        }

        let startButton;
        if (isVideo) {
            node.preload = "none";
            node.playsInline = true;
            node.tabIndex = -1;
            node.setAttribute("aria-hidden", "true");
            node.setAttribute("aria-label", date + " 的第 " + index + " 项媒体，Uni 视频");
            const poster = localMediaPath(media.poster);
            if (poster) node.poster = poster;
            startButton = element("button", "video-start");
            startButton.type = "button";
            startButton.append(element("span", "", "▶ 播放视频"), element("small", "", "点击后加载"));
            startButton.addEventListener("click", () => start(path, true));
            frame.append(startButton);
            node.addEventListener("loadeddata", loaded);
            node.addEventListener("playing", loaded);
            node.addEventListener("waiting", beginTimeout);
            node.addEventListener("pause", clearTimer);
            node.addEventListener("error", showMediaError);
        } else {
            node.alt = date + " 的第 " + index + " 项媒体，Uni 照片";
            node.decoding = "async";
            node.loading = firstImage ? "eager" : "lazy";
            node.fetchPriority = firstImage ? "high" : "auto";
            node.addEventListener("load", loaded);
            node.addEventListener("error", showMediaError);
            start(path);
            if (!firstImage && "IntersectionObserver" in window) {
                imageObserver = new IntersectionObserver(entries => {
                    if (entries.some(entry => entry.isIntersecting)) {
                        imageObserver.disconnect();
                        if (node.complete && node.naturalWidth > 0) loaded();
                        else beginTimeout();
                    }
                }, { rootMargin: "200px" });
                imageObserver.observe(node);
            }
        }
        mediaCleanup.push(() => {
            disposed = true;
            clearTimer();
            if (imageObserver) imageObserver.disconnect();
            if (isVideo && node.hasAttribute("src")) {
                node.pause();
                node.removeAttribute("src");
                node.load();
            } else if (!isVideo) {
                node.removeAttribute("src");
            }
        });
        return item;
    }

    function renderPosts(date, posts) {
        const heading = element("h2", "date-heading");
        heading.append(element("span", "date-badge", "📅 " + date + " 共有 " + posts.length + " 条帖子"));
        result.append(heading);
        let imageCount = 0;
        let mediaIndex = 0;
        for (const post of posts) {
            if (!post || typeof post !== "object") throw new Error("Invalid post");
            const article = element("article", "post");
            article.append(element("h3", "post-description", typeof post.description === "string" && post.description ? post.description : "暂无描述"));
            const grid = element("div", "media-grid");
            const mediaList = Array.isArray(post.media) ? post.media : [];
            for (const media of mediaList) {
                mediaIndex += 1;
                const firstImage = media && media.type === "image" && imageCount++ === 0;
                grid.append(renderMedia(media, date, mediaIndex, firstImage));
            }
            article.append(grid);
            const original = sourceURL(post.source);
            if (original) {
                const link = element("a", "source-link", "🔗 查看原始 Instagram 帖子");
                link.href = original;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                article.append(link);
            }
            result.append(article);
        }
        announce(date + "，共有 " + posts.length + " 条帖子。");
    }

    async function selectDate(date, historyMode = "push") {
        const requested = ++selection;
        clearResult();
        updateNavigation(date);
        if (!validDate(date)) {
            result.setAttribute("aria-busy", "false");
            result.append(element("p", "notice", "请选择一个有效日期。"));
            announce("请选择一个有效日期。");
            return;
        }
        input.value = date;
        updateURL(date, historyMode);
        document.title = date + " · Uni 日历";
        if (!dateSet.has(date)) {
            result.setAttribute("aria-busy", "false");
            showEmptyDate(date);
            return;
        }
        result.setAttribute("aria-busy", "true");
        result.append(element("p", "loading-message", "正在加载 " + date + " 的记录…"));
        announce("正在加载 " + date + " 的记录。");
        try {
            const days = await getMonth(date.slice(0, 7));
            if (requested !== selection) return;
            const posts = days[date];
            if (!Array.isArray(posts) || posts.length === 0) throw new Error("Missing day data");
            clearResult();
            renderPosts(date, posts);
            result.setAttribute("aria-busy", "false");
        } catch {
            if (requested !== selection) return;
            monthCache.delete(date.slice(0, 7));
            showError("这一天的记录暂时没有加载成功。", () => selectDate(date, "none"));
        }
    }

    async function loadArchive() {
        clearResult();
        result.setAttribute("aria-busy", "true");
        result.append(element("p", "loading-message", "正在加载日历…"));
        announce("正在加载日历。");
        try {
            archive = validateIndex(await fetchJSON(INDEX_URL));
            dateSet = new Set(archive.dates);
            range.textContent = "当前归档：" + archive.firstDate + " 至 " + archive.lastDate + "；历史归档，暂不更新。";
            input.disabled = false;
            navigation.hidden = false;
            const defaultDate = dateSet.has("2020-06-10") ? "2020-06-10" : archive.firstDate;
            await selectDate(dateFromURL() || defaultDate, "replace");
        } catch {
            range.textContent = "暂时无法读取归档范围。";
            showError("日历暂时没有加载成功。", loadArchive);
        }
    }

    input.addEventListener("change", () => selectDate(input.value));
    window.addEventListener("popstate", () => {
        if (archive) selectDate(dateFromURL() || (dateSet.has("2020-06-10") ? "2020-06-10" : archive.firstDate), "none");
    });
    loadArchive();
})();
