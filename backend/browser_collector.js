/**
 * This script extracts membership emojis from YouTube.
 * It uses exhaustive JSON state extraction and DOM scanning.
 * 
 * Instructions:
 * 1. Open a YouTube live stream or video page.
 * 2. Click the emoji icon in chat or the "Join" button (if not a member yet).
 * 3. Run this script in the console.
 */
(function () {
    console.log("%c[YouTube Emoji Collector] Starting exhaustive scan...", "color: #ff0000; font-weight: bold; font-size: 14px;");

    const emojis = {};
    let channelId = null;
    let channelName = null;

    // --- Helper: Normalize URL ---
    function normalizeUrl(url) {
        if (!url) return null;
        let clean = url;
        // Strip out size constraints to get high quality (s128)
        if (clean.includes('=w')) {
            clean = clean.replace(/=w\d+-h\d+.*$/, '=s128-c-k-nd');
        } else if (clean.includes('=s')) {
            clean = clean.replace(/=s\d+.*$/, '=s128-c-k-nd');
        }
        return clean;
    }

    // --- Method 1: Exhaustive JSON State Extraction ---
    function scanRecursively(obj, depth = 0) {
        if (!obj || typeof obj !== 'object' || depth > 50) return;

        // Pattern A: Standard emoji object (shortcuts + image)
        if (obj.shortcuts && Array.isArray(obj.shortcuts) && (obj.image || obj.thumbnails)) {
            const shortcut = obj.shortcuts[0];
            const thumbnails = (obj.image && obj.image.thumbnails) || obj.thumbnails;

            if (shortcut && shortcut.startsWith(':') && shortcut.endsWith(':') && thumbnails) {
                const url = normalizeUrl(thumbnails[thumbnails.length - 1].url);
                if (url && (url.includes('yt3.ggpht.com') || url.includes('googleusercontent.com'))) {
                    emojis[shortcut] = url;
                }
            }
        }

        // Pattern B: Flat emoji mapping (label + thumbnail)
        if (obj.accessibility && obj.accessibility.accessibilityData && obj.accessibility.accessibilityData.label) {
            const label = obj.accessibility.accessibilityData.label;
            const thumbnails = obj.thumbnails || (obj.image && obj.image.thumbnails);
            if (label.startsWith(':') && label.endsWith(':') && thumbnails) {
                const url = normalizeUrl(thumbnails[thumbnails.length - 1].url);
                if (url && (url.includes('yt3.ggpht.com') || url.includes('googleusercontent.com'))) {
                    emojis[label] = url;
                }
            }
        }

        // Recurse
        for (const key in obj) {
            try {
                const val = obj[key];
                if (val && typeof val === 'object') {
                    scanRecursively(val, depth + 1);
                }
            } catch (e) { }
        }
    }

    console.log("Deep scanning internal data...");
    [window.ytInitialData, window.ytInitialPlayerResponse].forEach(data => {
        if (data) scanRecursively(data);
    });

    // --- Method 2: DOM Scanning (Comprehensive) ---
    function scanDOM(root) {
        // Find all images
        const imgs = Array.from(root.querySelectorAll('img'));

        // Check shadow DOMs
        const all = root.querySelectorAll('*');
        for (const el of all) {
            if (el.shadowRoot) {
                imgs.push(...scanDOM(el.shadowRoot));
            }
        }

        // Check iframes (chat)
        if (root === document) {
            const iframes = document.querySelectorAll('iframe#chatframe');
            for (const iframe of iframes) {
                try {
                    const doc = iframe.contentDocument || iframe.contentWindow.document;
                    imgs.push(...scanDOM(doc));
                } catch (e) { }
            }
        }
        return imgs;
    }

    console.log("Scanning page elements...");
    const allImages = scanDOM(document);
    allImages.forEach(img => {
        const shortcut = img.getAttribute('aria-label') ||
            img.getAttribute('shared-tooltip-text') ||
            img.getAttribute('alt') ||
            img.title;

        let src = img.src || img.getAttribute('src') || img.getAttribute('thumbnail') || img.getAttribute('data-src');

        if (shortcut && shortcut.startsWith(':') && shortcut.endsWith(':') && src) {
            const url = normalizeUrl(src);
            if (url && (
                url.includes('yt3.ggpht.com') ||
                url.includes('googleusercontent.com') ||
                url.includes('www.gstatic.com/youtube/img/emoji')
            )) {
                // Exclude some common icons that look like emojis
                if (url.includes('fonts.gstatic.com')) return;
                emojis[shortcut] = url;
            }
        }
    });

    // --- Channel ID Detection (Prioritized) ---
    // 1. YouTube Player Response (Most reliable for video pages)
    if (window.ytInitialPlayerResponse &&
        window.ytInitialPlayerResponse.videoDetails) {
        if (window.ytInitialPlayerResponse.videoDetails.channelId) {
            channelId = window.ytInitialPlayerResponse.videoDetails.channelId;
        }
        if (window.ytInitialPlayerResponse.videoDetails.author) {
            channelName = window.ytInitialPlayerResponse.videoDetails.author;
        }
    }

    // 2. Meta Tag (Reliable for channel/video pages)
    if (!channelId || !channelName) {
        const metaId = document.querySelector('meta[itemprop="channelId"]');
        const metaName = document.querySelector('meta[itemprop="name"]');
        if (metaId && !channelId) channelId = metaId.content;
        if (metaName && !channelName) channelName = metaName.content;
    }

    // 3. Canonical Link (Very Reliable for Channel Pages)
    if (!channelId) {
        const canonical = document.querySelector('link[rel="canonical"]');
        if (canonical) {
            const href = canonical.href;
            if (href.includes('/channel/')) {
                const match = href.match(/\/channel\/(UC[\w-]{22})/);
                if (match) channelId = match[1];
            }
        }
    }

    // 4. Handheld Alternate Link (Fallback)
    if (!channelId) {
        const alternate = document.querySelector('link[rel="alternate"][media="handheld"]');
        if (alternate) {
            const href = alternate.href;
            if (href.includes('/channel/')) {
                const match = href.match(/\/channel\/(UC[\w-]{22})/);
                if (match) channelId = match[1];
            }
        }
    }

    // 5. Channel Metadata Renderer (Channel pages)
    if ((!channelId || !channelName) && window.ytInitialData && window.ytInitialData.metadata &&
        window.ytInitialData.metadata.channelMetadataRenderer) {
        if (!channelId) channelId = window.ytInitialData.metadata.channelMetadataRenderer.externalId;
        if (!channelName) channelName = window.ytInitialData.metadata.channelMetadataRenderer.title;
    }

    // 6. Subscribe Button Check (Video pages - very robust)
    if (!channelId && window.ytInitialData) {
        try {
            // Find valid subscribe button in secondary info or overlay
            const traverseForSubscribe = (obj) => {
                if (!obj || typeof obj !== 'object') return null;
                if (obj.subscribeButtonRenderer && obj.subscribeButtonRenderer.channelId) {
                    return obj.subscribeButtonRenderer.channelId;
                }
                for (const k in obj) {
                    const res = traverseForSubscribe(obj[k]);
                    if (res) return res;
                }
                return null;
            };
            const foundId = traverseForSubscribe(window.ytInitialData);
            if (foundId) channelId = foundId;
        } catch (e) { }
    }

    // 7. Robust Regex Search (Global Fallback)
    if (!channelId) {
        const html = document.documentElement.outerHTML;
        // Search patterns categorized by reliability
        const patterns = [
            // User-identified pattern: /channel/UC.../videos followed by webPageType
            // Accounts for single escapes (\/channel\/) and multiple escapes
            { name: "Tab URL Pattern", re: /[\/\\u002f]channel[\/\\u002f](UC[\w-]{22})[\/\\u002f]videos["'],\s*["']webPageType["']/ },
            // browseId in JSON blobs
            { name: "browseId JSON", re: /["']browseId["']\s*:\s*["'](UC[\w-]{22})["']/ },
            // externalId (often in channel metadata)
            { name: "externalId JSON", re: /["']externalId["']\s*:\s*["'](UC[\w-]{22})["']/ },
            // channelId keyword
            { name: "channelId JSON", re: /["']channelId["']\s*:\s*["'](UC[\w-]{22})["']/ },
            // ownerProfileUrl
            { name: "ownerProfileUrl", re: /[\/\\u002f]channel[\/\\u002f](UC[\w-]{22})["']/ }
        ];

        for (const p of patterns) {
            const match = html.match(p.re);
            if (match && match[1]) {
                console.log(`[ID Discovery] Found via ${p.name}: ${match[1]}`);
                channelId = match[1];
                break;
            }
        }
    }

    // 4. Owner Link in Video Header (DOM Fallback)
    if (!channelId) {
        const ownerLink = document.querySelector('#owner-name a') ||
            document.querySelector('ytd-video-owner-renderer a.ytd-channel-name') ||
            document.querySelector('#upload-info a.ytd-channel-name');
        if (ownerLink) {
            const href = ownerLink.getAttribute('href');
            if (href && href.includes('/channel/')) {
                const match = href.match(/\/channel\/(UC[\w-]{22})/);
                if (match) channelId = match[1];
            }
        }
    }

    const result = {
        channelId: channelId || "UNKNOWN_CHANNEL",
        channelName: channelName || "UNKNOWN_NAME",
        emojis: emojis
    };

    const count = Object.keys(emojis).length;
    if (count < 10) {
        console.warn("%c[Notice] Only found " + count + " emojis. If you are a member, try opening the emoji picker or 'Join' dialog and run the script again.", "color: #ccac00;");
    }

    if (count > 0) {
        console.log("%c[Success] Found " + count + " emojis for channel: " + result.channelId, "color: #00aa00; font-weight: bold;");
        console.log("------------------- COPY JSON BELOW -------------------");
        console.log(JSON.stringify(result, null, 2));
        console.log("------------------- COPY JSON ABOVE -------------------");

        if (result.channelId === "UNKNOWN_CHANNEL") {
            console.warn("!!! Channel ID could not be detected. Please find it in the URL (UC...) and enter it manually.");
        }
    } else {
        console.error("[Error] No membership emojis found. Make sure you are on a channel page and the emoji data is loaded.");
    }
})();
