import React, { useState, useEffect, useRef, useMemo } from 'react';

const DANMAKU_DURATION = 5.0; // Seconds to cross the screen
const DANMAKU_LANES = 12; // Number of vertical lanes
const FONT_SIZE_RATIO = 48 / 1080; // Same ratio as backend (48px at 1080p)

export default function DanmakuLayer({ comments, currentTime, enabled = true, density = 100, videoHeight = 1080 }) {
    const [offsets, setOffsets] = useState({}); // Tracking extra offsets for smoothness
    const requestRef = useRef();
    const lastTimeRef = useRef();

    // Filter active comments based on broad range and density
    const activeComments = useMemo(() => {
        if (!comments || comments.length === 0) return [];
        return comments.filter(c => {
            // Check time range
            const isInTime = c.timestamp <= currentTime && currentTime < c.timestamp + DANMAKU_DURATION;
            if (!isInTime) return false;

            // Check density (deterministic sampling)
            // Use a simple hash of timestamp and text length to keep it consistent
            const hash = Math.floor(c.timestamp * 1000) % 100;
            return hash < (density || 100);
        });
    }, [comments, currentTime, density]);

    if (!enabled || !comments || comments.length === 0) return null;

    // Calculate font size based on video height (same ratio as backend)
    const fontSize = Math.round(videoHeight * FONT_SIZE_RATIO);

    return (
        <div
            className="absolute inset-0 pointer-events-none overflow-hidden"
            style={{ zIndex: 9999 }} // Ensure it's on top of everything
        >
            {activeComments.map((comment) => {
                const elapsed = currentTime - comment.timestamp;
                const progress = elapsed / DANMAKU_DURATION;

                // Keep lane consistent for a specific comment
                const lane = Math.floor(comment.timestamp * 1000) % DANMAKU_LANES;
                const topPercent = (lane / DANMAKU_LANES) * 85 + 5;

                return (
                    <div
                        key={`${comment.timestamp}-${comment.text}`}
                        className="absolute whitespace-nowrap text-white font-bold pointer-events-none"
                        style={{
                            top: `${topPercent}%`,
                            left: `${100 - (progress * 140)}%`, // Move 140% distance
                            fontSize: `${fontSize}px`,
                            textShadow: '2px 2px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 0px 0px 4px rgba(0,0,0,0.8)',
                            opacity: 0.9,
                            transition: 'left 0.1s linear', // Smooth out the jumps between timeupdates
                            willChange: 'left',
                        }}
                    >
                        {comment.text}
                    </div>
                );
            })}
        </div>
    );
}
