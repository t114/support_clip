import React, { useRef, useEffect } from 'react';

export default function VideoPlayer({ videoUrl, subtitles, styles, onTimeUpdate }) {
    const videoRef = useRef(null);

    // Find current subtitle based on local state passed from parent
    // Note: In a real optimized app, we might want to throttle this or handle it differently
    // but for now, finding it on render or passing current time is fine.
    // Actually, let's rely on the parent passing the active subtitle text or we find it here.
    // Let's find it here for the overlay to keep it synced with the video frame as much as possible.

    const [currentText, setCurrentText] = React.useState('');
    const [scale, setScale] = React.useState(1); // Scale factor relative to 1080p

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            const time = videoRef.current.currentTime;
            onTimeUpdate(time);

            const activeSub = subtitles.find(sub => time >= sub.start && time <= sub.end);
            setCurrentText(activeSub ? activeSub.text : '');
        }
    };

    // Helper to check if background is transparent
    const isTransparent = (color) => {
        if (!color) return true;
        if (color.length === 9) { // #RRGGBBAA
            const alpha = parseInt(color.slice(7, 9), 16);
            return alpha === 0;
        }
        return false; // Assume opaque if #RRGGBB
    };

    const hasBackground = !isTransparent(styles.backgroundColor);

    useEffect(() => {
        if (videoRef.current) {
            videoRef.current.load();
        }
    }, [videoUrl]);

    // Update scale based on video player height (Backend uses 1080p reference)
    useEffect(() => {
        if (!videoRef.current) return;

        const updateScale = () => {
            if (videoRef.current) {
                const height = videoRef.current.clientHeight;
                // Backend uses PlayResY = 1080
                setScale(height / 1080);
            }
        };

        const observer = new ResizeObserver(updateScale);
        observer.observe(videoRef.current);

        // Initial calculation
        videoRef.current.addEventListener('loadedmetadata', updateScale);
        updateScale();

        return () => {
            observer.disconnect();
            if (videoRef.current) {
                videoRef.current.removeEventListener('loadedmetadata', updateScale);
            }
        };
    }, []);

    // Build text shadow for double outline and drop shadow
    const buildTextShadow = () => {
        const shadows = [];

        // Inner outline (using text-shadow to create outline effect)
        const innerWidth = (styles.outlineWidth || 0) * scale;
        const innerColor = styles.outlineColor || '#000000';
        if (innerWidth > 0) {
            // Create outline using multiple shadows
            for (let angle = 0; angle < 360; angle += 45) {
                const rad = (angle * Math.PI) / 180;
                const x = Math.cos(rad) * innerWidth;
                const y = Math.sin(rad) * innerWidth;
                shadows.push(`${x}px ${y}px 0 ${innerColor}`);
            }
        }

        // Outer outline
        const outerWidth = (styles.outerOutlineWidth || 0) * scale;
        const outerColor = styles.outerOutlineColor || '#FFFFFF';
        if (outerWidth > 0) {
            const totalWidth = innerWidth + outerWidth;
            for (let angle = 0; angle < 360; angle += 45) {
                const rad = (angle * Math.PI) / 180;
                const x = Math.cos(rad) * totalWidth;
                const y = Math.sin(rad) * totalWidth;
                shadows.push(`${x}px ${y}px 0 ${outerColor}`);
            }
        }

        // Drop shadow
        const shadowBlur = (styles.shadowBlur || 0) * scale;
        const shadowX = (styles.shadowOffsetX || 0) * scale;
        const shadowY = (styles.shadowOffsetY || 0) * scale;
        const shadowColor = styles.shadowColor || '#000000';
        if (shadowBlur > 0 || shadowX !== 0 || shadowY !== 0) {
            shadows.push(`${shadowX}px ${shadowY}px ${shadowBlur}px ${shadowColor}`);
        }

        return shadows.length > 0 ? shadows.join(', ') : 'none';
    };

    return (
        <div className="relative w-full max-w-4xl mx-auto bg-black rounded-lg overflow-hidden shadow-xl group">
            <video
                ref={videoRef}
                className="w-full aspect-video"
                controls
                crossOrigin="anonymous"
                onTimeUpdate={handleTimeUpdate}
            >
                <source src={`${videoUrl}`} type="video/mp4" />
                お使いのブラウザは動画タグをサポートしていません。
            </video>

            {/* Custom Subtitle Overlay */}
            {currentText && (
                <div
                    className="absolute left-0 right-0 text-center pointer-events-none transition-all duration-200"
                    style={{
                        bottom: `${styles.bottom}%`,
                    }}
                >
                    <span
                        style={{
                            fontFamily: styles.fontFamily || 'Noto Sans JP',
                            fontSize: `${styles.fontSize * scale}px`,
                            color: styles.color,
                            backgroundColor: styles.backgroundColor,
                            textShadow: buildTextShadow(),
                            fontWeight: styles.fontWeight || 'normal',
                            padding: `${4 * scale}px ${12 * scale}px`,
                            borderRadius: `${4 * scale}px`,
                            whiteSpace: 'pre-wrap',
                        }}
                    >
                        {currentText}
                    </span>
                </div>
            )}
        </div>
    );
}
