import React, { useState, useEffect, useRef, useMemo } from 'react';

const DANMAKU_DURATION = 7.0; // Seconds to cross the screen (increased from 5 for readability)
const DANMAKU_LANES = 12; // Number of vertical lanes
const FONT_SIZE_RATIO = 48 / 1080; // Same ratio as backend (48px at 1080p)

export default function DanmakuLayer({ comments, currentTime, enabled = true, density = 100, videoHeight = 1080, channelId }) {
    const [emojiMap, setEmojiMap] = useState({});

    // Fetch emoji map when channelId changes or comments update (as backend might have discovered new emojis)
    useEffect(() => {
        if (channelId) {
            fetch(`/static/emojis/${channelId}/map.json`)
                .then(res => {
                    if (res.ok) return res.json();
                    return {};
                })
                .then(data => setEmojiMap(data))
                .catch(err => {
                    console.warn('No emoji map found for channel:', channelId);
                    setEmojiMap({});
                });
        }
    }, [channelId, comments]);

    // Filter active comments based on broad range and density
    const activeComments = useMemo(() => {
        if (!comments || comments.length === 0) return [];
        return comments.filter(c => {
            // Check time range
            const isInTime = c.timestamp <= currentTime && currentTime < c.timestamp + DANMAKU_DURATION;
            if (!isInTime) return false;

            // Check density (deterministic sampling)
            const hash = Math.floor(c.timestamp * 1000) % 100;
            return hash < (density || 100);
        });
    }, [comments, currentTime, density]);

    if (!enabled || !comments || comments.length === 0) return null;

    // Calculate font size based on video height (same ratio as backend)
    const fontSize = Math.round(videoHeight * FONT_SIZE_RATIO);

    // Function to render text with emojis
    const renderCommentContent = (text) => {
        if (!Object.keys(emojiMap).length) {
            return text;
        }

        // Split by emoji patterns (e.g. :_mioハトタウロス: or :miko_kusa:)
        // Matches anything between colons that doesn't contain a colon or space
        const parts = text.split(/(:[^:\s]+:)/);

        return parts.map((part, i) => {
            if (part.startsWith(':') && part.endsWith(':')) {
                // Direct lookup in the emoji map
                const imgName = emojiMap[part];
                if (imgName) {
                    return (
                        <img
                            key={i}
                            src={`/static/emojis/${channelId}/${imgName}`}
                            alt={part}
                            className="inline-block align-middle"
                            style={{ height: `${fontSize * 1.4}px`, margin: '0 2px' }}
                        />
                    );
                }
            }
            return part;
        });
    };

    return (
        <div
            className="absolute inset-0 pointer-events-none overflow-hidden"
            style={{ zIndex: 9999 }}
        >
            {activeComments.map((comment) => {
                const elapsed = currentTime - comment.timestamp;
                const progress = elapsed / DANMAKU_DURATION;

                // Keep lane consistent for a specific comment
                const lane = Math.floor(comment.timestamp * 1000) % DANMAKU_LANES;
                const topPercent = (lane / DANMAKU_LANES) * 85 + 5;

                return (
                    <div
                        key={comment.id || `${comment.timestamp}-${comment.text}`}
                        className="absolute whitespace-nowrap text-white font-bold pointer-events-none"
                        style={{
                            top: `${topPercent}%`,
                            left: `${100 - (progress * 170)}%`,
                            fontSize: `${fontSize}px`,
                            textShadow: '3px 3px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 0px 0px 6px rgba(0,0,0,0.8)',
                            opacity: 1.0,
                            transition: 'left 0.1s linear',
                            willChange: 'left',
                            display: 'flex',
                            alignItems: 'center'
                        }}
                    >
                        {renderCommentContent(comment.text)}
                    </div>
                );
            })}
        </div>
    );
}
